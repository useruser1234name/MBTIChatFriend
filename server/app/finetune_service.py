"""GPT Fine-tuning 파이프라인 - 대화 데이터 수집 및 모델 커스터마이징"""

import json
import logging
import os
import re
import tempfile
from typing import Dict, List, Optional, Set

from openai import AsyncOpenAI

from .config import OPENAI_API_KEY
from .prompts import build_system_prompt, AFFINITY_BEHAVIORS

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# 캐릭터별 파인튜닝 모델 저장 (character_id → model_id)
_MODELS_FILE = "./finetune_models.json"

# 인메모리 캐시 (매 요청 파일 읽기 제거)
_models_cache: Optional[Dict[str, str]] = None
_models_cache_mtime: float = 0.0


def _load_models() -> Dict[str, str]:
    global _models_cache, _models_cache_mtime
    if not os.path.exists(_MODELS_FILE):
        _models_cache = {}
        return _models_cache

    mtime = os.path.getmtime(_MODELS_FILE)
    if _models_cache is not None and mtime == _models_cache_mtime:
        return _models_cache

    try:
        with open(_MODELS_FILE, encoding="utf-8") as f:
            _models_cache = json.load(f)
            _models_cache_mtime = mtime
    except Exception:
        _models_cache = {}
    return _models_cache


def _save_models(models: Dict[str, str]) -> None:
    global _models_cache, _models_cache_mtime
    with open(_MODELS_FILE, "w", encoding="utf-8") as f:
        json.dump(models, f, ensure_ascii=False, indent=2)
    _models_cache = models
    _models_cache_mtime = os.path.getmtime(_MODELS_FILE)


def _validate_model_id(model_id: str) -> bool:
    """model_id 형식 검증: ft: 또는 gpt- prefix"""
    return bool(re.match(r'^(ft:|gpt-)', model_id))


def get_model_for_character(character_id: str) -> str:
    """캐릭터에 파인튜닝 모델이 있으면 반환, 없으면 기본 gpt-4o"""
    if not character_id:
        return "gpt-4o"
    return _load_models().get(character_id, "gpt-4o")


def activate_model(character_id: str, model_id: str) -> None:
    """캐릭터에 파인튜닝 모델 활성화"""
    if not _validate_model_id(model_id):
        raise ValueError(f"유효하지 않은 model_id 형식: {model_id}")
    models = _load_models()
    models[character_id] = model_id
    _save_models(models)


def _build_training_examples(
    conversations: list,
    system_prompt: str,
    quality_scores: Optional[Dict[str, float]] = None,
    min_quality: float = 0.6,
    excluded_message_ids: Optional[set] = None,
) -> List[dict]:
    """
    대화 히스토리에서 OpenAI fine-tuning 훈련 예시 생성.
    각 assistant 발화 시점까지의 대화가 하나의 훈련 예시가 됨.

    quality_scores: {message_id: score} 형태. 전달 시 min_quality 미만은 제외.
    excluded_message_ids: thumbs_down 등으로 제외할 메시지 ID 집합.
    """
    examples = []
    messages = [{"role": "system", "content": system_prompt}]

    for msg in conversations:
        role = msg.get("role", "user")
        content = msg.get("content", "").strip()
        if not content or role not in ("user", "assistant"):
            continue

        msg_id = msg.get("message_id", "")

        # 품질 필터: thumbs_down 제외
        if excluded_message_ids and msg_id in excluded_message_ids:
            continue

        # 품질 필터: 저품질 제외
        if quality_scores and msg_id and msg_id in quality_scores:
            if quality_scores[msg_id] < min_quality:
                continue

        messages.append({"role": role, "content": content})
        # user→assistant 쌍이 갖춰지면 훈련 예시 추가
        if role == "assistant" and len(messages) >= 3:
            examples.append({"messages": list(messages)})

    return examples


async def prepare_and_start_finetune(
    character_id: str,
    character_name: str,
    mbti: str,
    speech_style: str,
    relationship: str,
    nickname: str,
    affinity_level: int,
    conversations: list,
    quality_scores: Optional[Dict[str, float]] = None,
    excluded_message_ids: Optional[Set[str]] = None,
    synthetic_file: Optional[str] = None,
) -> dict:
    """훈련 데이터 준비 → OpenAI 업로드 → Fine-tuning 잡 생성"""
    if not client:
        return {
            "job_id": "",
            "status": "failed",
            "training_count": 0,
            "model": "",
            "error": "OpenAI API 키가 설정되지 않았습니다."
        }

    system_prompt = build_system_prompt(
        mbti=mbti,
        speech_style=speech_style,
        relationship=relationship,
        nickname=nickname,
        character_name=character_name,
        affinity_level=affinity_level,
    )

    # affinity_level별 행동 지침을 학습 데이터에 포함
    affinity = AFFINITY_BEHAVIORS.get(affinity_level, AFFINITY_BEHAVIORS[1])
    affinity_note = (
        f"\n[학습 맥락: 현재 호감도 {affinity_level}/5 ({affinity['description']}). "
        f"분위기: {affinity['tone']}]"
    )
    system_prompt += affinity_note

    examples = _build_training_examples(
        conversations,
        system_prompt,
        quality_scores=quality_scores,
        excluded_message_ids=excluded_message_ids,
    )

    # 합성 데이터 병합
    if synthetic_file and os.path.exists(synthetic_file):
        try:
            with open(synthetic_file, "r", encoding="utf-8") as sf:
                for line in sf:
                    line = line.strip()
                    if line:
                        synthetic_example = json.loads(line)
                        examples.append(synthetic_example)
            logger.info(f"합성 데이터 병합: {synthetic_file} → 총 {len(examples)}개")
            import random as _rnd
            _rnd.shuffle(examples)
        except Exception as e:
            logger.warning(f"합성 데이터 로드 실패 ({synthetic_file}): {e}")

    if len(examples) < 10:
        return {
            "job_id": "",
            "status": "insufficient_data",
            "training_count": len(examples),
            "model": "",
            "error": (
                f"훈련 데이터 부족 (현재 {len(examples)}개, 최소 10개 필요). "
                "대화를 더 나눈 후 시도해주세요."
            )
        }

    # JSONL 임시 파일 작성
    fd, tmp_path = tempfile.mkstemp(suffix=".jsonl")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for ex in examples:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")

        # OpenAI Files API 업로드
        with open(tmp_path, "rb") as f:
            file_obj = await client.files.create(file=f, purpose="fine-tune")

        # Fine-tuning 잡 생성
        suffix = f"mbti-{character_id[:8]}"
        job = await client.fine_tuning.jobs.create(
            training_file=file_obj.id,
            model="gpt-4o-mini-2024-07-18",
            suffix=suffix,
            hyperparameters={"n_epochs": 3}
        )

        logger.info(f"Fine-tuning 시작: {job.id} / 캐릭터: {character_id}")
        return {
            "job_id": job.id,
            "status": job.status,
            "training_count": len(examples),
            "model": job.model,
            "error": ""
        }

    except Exception as e:
        logger.error(f"Fine-tuning 시작 실패: {e}")
        return {
            "job_id": "",
            "status": "failed",
            "training_count": len(examples),
            "model": "",
            "error": str(e)
        }
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


async def check_finetune_status(job_id: str) -> dict:
    """Fine-tuning 잡 상태 조회"""
    if not client:
        return {"job_id": job_id, "status": "failed", "fine_tuned_model": "", "error": "API 키 없음"}
    try:
        job = await client.fine_tuning.jobs.retrieve(job_id)
        return {
            "job_id": job.id,
            "status": job.status,
            "fine_tuned_model": job.fine_tuned_model or "",
            "error": str(job.error) if job.error else ""
        }
    except Exception as e:
        logger.error(f"상태 조회 실패: {e}")
        return {"job_id": job_id, "status": "failed", "fine_tuned_model": "", "error": str(e)}
