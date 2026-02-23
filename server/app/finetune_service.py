"""GPT Fine-tuning 파이프라인 - 대화 데이터 수집 및 모델 커스터마이징"""

import json
import logging
import os
import tempfile
from typing import Dict, List

from openai import AsyncOpenAI

from .config import OPENAI_API_KEY
from .prompts import build_system_prompt

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# 캐릭터별 파인튜닝 모델 저장 (character_id → model_id)
_MODELS_FILE = "./finetune_models.json"


def _load_models() -> Dict[str, str]:
    if os.path.exists(_MODELS_FILE):
        try:
            with open(_MODELS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_models(models: Dict[str, str]) -> None:
    with open(_MODELS_FILE, "w", encoding="utf-8") as f:
        json.dump(models, f, ensure_ascii=False, indent=2)


def get_model_for_character(character_id: str) -> str:
    """캐릭터에 파인튜닝 모델이 있으면 반환, 없으면 기본 gpt-4o"""
    if not character_id:
        return "gpt-4o"
    return _load_models().get(character_id, "gpt-4o")


def activate_model(character_id: str, model_id: str) -> None:
    """캐릭터에 파인튜닝 모델 활성화"""
    models = _load_models()
    models[character_id] = model_id
    _save_models(models)


def _build_training_examples(conversations: list, system_prompt: str) -> List[dict]:
    """
    대화 히스토리에서 OpenAI fine-tuning 훈련 예시 생성.
    각 assistant 발화 시점까지의 대화가 하나의 훈련 예시가 됨.
    """
    examples = []
    messages = [{"role": "system", "content": system_prompt}]

    for msg in conversations:
        role = msg.get("role", "user")
        content = msg.get("content", "").strip()
        if not content or role not in ("user", "assistant"):
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

    examples = _build_training_examples(conversations, system_prompt)

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
