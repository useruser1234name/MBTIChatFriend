"""채팅 서비스 - LLM 연동 및 메시지 분할"""

import asyncio
import json
import logging
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import AsyncGenerator, List, NamedTuple, Optional, Tuple, Union

from openai import AsyncOpenAI

from .circuit_breaker import CircuitOpenError, get_openai_circuit
from .config import (
    OPENAI_API_KEY,
    LLM_MODEL_COMPLEX,
    LLM_MODEL_SIMPLE,
)
from .content_filter import check_content, detect_crisis, get_safety_system_prompt
from .background_tasks import create_tracked_task
from .json_utils import extract_json_array, extract_json_object
from .mbti import get_mbti_group as _get_mbti_group
from .models import HistoryMessage, MemoryItem, ReplyPart, VALID_EMOTIONS
from .prompts import build_system_prompt, build_diary_prompt, build_memory_extract_prompt
from .user_preference import derive_user_style, render_preference_section
from .vector_store import get_store
from .finetune_service import get_model_for_character
from .memory_service import (
    summarize_conversation,
    extract_facts,
    extract_episodes,
    build_memory_context,
    is_memory_cached,
)
from .quality_service import (
    check_diversity_async,
    classify_quality_issues,
    quick_score,
    score_response_async,
)
from .metrics_service import record_event_async
from .model_routing import resolve_model_endpoint, select_model_for_crisis

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# ── 품질 게이트 임계값 (0.0~1.0, 낮을수록 재생성 빈도 ↑) ─────────
QUALITY_GATE_THRESHOLD = 0.4

# ── LLM 비용 단가 (USD per 1K tokens, 2025-04 기준) ──────────────
_MODEL_COSTS = {
    "gpt-4.1":      {"prompt": 0.002, "completion": 0.008},
    "gpt-4.1-mini": {"prompt": 0.0004, "completion": 0.0016},
}


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """주어진 토큰 수로 예상 비용(USD)을 계산한다."""
    costs = _MODEL_COSTS.get(model, _MODEL_COSTS["gpt-4.1-mini"])
    return (prompt_tokens / 1000 * costs["prompt"]
            + completion_tokens / 1000 * costs["completion"])


# ── MBTI별 호감도 증가 트리거 ───────────────────────────────────
_MBTI_AFFINITY_TRIGGERS = {
    "INTJ": "효율성 인정, 지적 토론, 전략적 조언",
    "INTP": "독창적 아이디어 공유, 논리적 분석, 지적 호기심",
    "ENTJ": "리더십 인정, 목표 달성 격려, 능력 칭찬",
    "ENTP": "재치있는 대화, 새로운 관점 제시, 토론",
    "INFJ": "깊은 공감, 의미있는 대화, 가치관 공유",
    "INFP": "진심어린 감정 표현, 창의적 공감, 이상 공유",
    "ENFJ": "따뜻한 격려, 성장 응원, 진심어린 관심",
    "ENFP": "새로운 경험 공유, 열정적 반응, 자유로운 표현",
    "ISTJ": "약속 이행, 신뢰 표현, 안정적 태도",
    "ISFJ": "배려, 챙김, 감사 표현, 따뜻한 관심",
    "ESTJ": "책임감 인정, 효율적 소통, 명확한 의사표현",
    "ESFJ": "따뜻한 칭찬, 함께하는 활동, 소속감 표현",
    "ISTP": "능력 인정, 자유 존중, 실용적 도움",
    "ISFP": "감성 공유, 취향 존중, 부드러운 관심",
    "ESTP": "도전적 제안, 활동적 대화, 솔직한 반응",
    "ESFP": "즐거운 분위기, 긍정적 에너지, 함께 즐기기",
}

# ── 호감도 키워드 카테고리 ──────────────────────────────────────

_POSITIVE_CATEGORIES = {
    "greeting": (["안녕", "하이", "반가워", "왔어", "좋은 아침", "잘 잤어"], 1),
    "compliment": (["멋져", "대단", "잘한다", "최고", "천재", "예뻐", "귀여", "멋있", "능력자", "센스"], 2),
    "gratitude": (["고마워", "감사", "덕분", "땡큐", "다행"], 2),
    "empathy": (["알겠어", "이해해", "맞아", "그럴 수 있지", "힘들었겠다", "공감", "위로"], 2),
    "affection": (["좋아", "사랑", "보고 싶", "소중", "행복", "설레", "심쿵", "두근"], 3),
    "playful": (["ㅋㅋ", "ㅎㅎ", "웃겨", "재밌", "장난", "놀리", "귀엽"], 1),
    "interest": (["궁금", "알려줘", "어떤 거", "가르쳐", "뭐 좋아", "취미"], 1),
}

_NEGATIVE_CATEGORIES = {
    "dislike": (["싫어", "별로", "아닌데", "그만"], 1),
    "annoyance": (["짜증", "귀찮", "하지마", "그만해"], 2),
    "hostility": (["미워", "나빠", "최악", "못생"], 2),
    "ignore": (["몰라", "상관없", "관심없", "알아서"], 1),
}

# 부정문 패턴 - 긍정 키워드를 부정으로 뒤집는 접두사
_NEGATION_PREFIXES = [
    "안 ", "못 ", "안좋", "별로 안", "그렇게 안",
    "전혀 ", "하나도 ", "절대 ", "딱히 ", "그다지 ",
]
_NEGATION_SUFFIXES = [
    "않아", "않다", "않은", "없어", "없다", "싫어", "말아", "마",
    "않았", "않을", "않고", "없는", "없었",
]

# 이모티콘/반복 문자 감정 패턴
_EMOTICON_POSITIVE = ["ㅋㅋㅋ", "ㅎㅎㅎ", "ㅋㅋㅋㅋ", "ㅎㅎㅎㅎ", "~~", "!!!", "♡", "♥"]
_EMOTICON_NEGATIVE = ["ㅠㅠㅠ", "ㅜㅜㅜ", ";;;", "..."]

# 키워드/LLM 스케일 보정 계수
KEYWORD_SCALE = 0.4


def _classify_message_complexity(message: str, history_len: int) -> str:
    """메시지 복잡도 분류: 'simple' | 'complex'.

    가중 점수제로 판단:
    - complex_patterns 매칭: +1점/패턴
    - 길이 100자 초과: +1점, 50자 초과: +0.5점
    - 질문형('?') + 30자 이상: +0.5점
    - history_len > 10: +0.5점
    - 임계값 1.5 이상이면 complex

    simple: 인사, 짧은 반응, 단순 질문 → gpt-4.1-mini
    complex: 감정 상담, 복잡한 질문, 갈등, 긴 텍스트 → gpt-4.1
    """
    msg = message.strip()
    msg_lower = msg.lower()

    # 짧고 단순한 메시지 → 즉시 simple 반환 (점수 계산 불필요)
    simple_patterns = ["안녕", "ㅎㅎ", "ㅋㅋ", "응", "어", "ㅇㅇ", "그래", "오키",
                       "ㅎ", "ㄱㄱ", "ㅇㅋ", "하이", "반가", "좋아", "ㄴㄴ"]
    if len(msg) < 10 and any(w in msg_lower for w in simple_patterns):
        return "simple"

    # 가중 점수 계산
    score = 0.0

    # 감정적/복잡한 키워드 매칭: +1점/패턴
    complex_patterns = ["고민", "힘들", "어떻게", "왜", "속상", "우울", "걱정",
                        "화나", "짜증", "슬프", "불안", "상담", "조언", "도와줘",
                        "진지하게", "솔직히", "사실은", "고백", "미안"]
    for w in complex_patterns:
        if w in msg_lower:
            score += 1.0

    # 길이 기반
    if len(msg) > 100:
        score += 1.0
    elif len(msg) > 50:
        score += 0.5

    # 질문형 + 30자 이상
    if "?" in msg and len(msg) > 30:
        score += 0.5

    # 대화가 깊어졌을 때
    if history_len > 10:
        score += 0.5

    return "complex" if score >= 1.5 else "simple"


def calculate_compatibility(char_mbti: str, user_mbti: Optional[str]) -> float:
    """MBTI 궁합 점수 계산 (0.8 ~ 1.3 가중치)"""
    if not user_mbti:
        return 1.0

    # 같은 유형
    if char_mbti == user_mbti:
        return 1.1

    cg = _get_mbti_group(char_mbti)
    ug = _get_mbti_group(user_mbti)

    # NT-NF: 지적 + 감성 보완 → 높은 궁합
    if {cg, ug} == {"NT", "NF"}:
        return 1.3

    # 같은 그룹
    if cg == ug:
        return 1.15

    # I↔E, T↔F 둘 다 반대: 매력적이지만 충돌
    ie_opposite = char_mbti[0] != user_mbti[0]
    tf_opposite = char_mbti[2] != user_mbti[2]
    if ie_opposite and tf_opposite:
        return 0.85

    # ST-NF, SF-NT: 현실+이상 보완
    if {cg, ug} in ({"ST", "NF"}, {"SF", "NT"}):
        return 0.95

    return 1.0


def _is_negated(msg: str, word: str) -> bool:
    """키워드가 부정문 맥락에서 사용되었는지 판단"""
    idx = msg.find(word)
    if idx < 0:
        return False
    # 접두사 체크 (키워드 앞 10자 이내)
    prefix = msg[max(0, idx - 10):idx]
    for neg in _NEGATION_PREFIXES:
        if neg in prefix:
            return True
    # 접미사 체크 (키워드 뒤 6자 이내)
    suffix = msg[idx + len(word):idx + len(word) + 6]
    for neg in _NEGATION_SUFFIXES:
        if neg in suffix:
            return True
    return False


def calculate_affinity_delta(
    message: str,
    affinity_level: int,
    conversation_history: Optional[List[HistoryMessage]] = None,
    user_mbti: Optional[str] = None,
    char_mbti: str = "ENFP"
) -> int:
    """대화 내용 기반 호감도 변화 계산 (개선된 버전)"""
    delta = 0.0
    msg = message.lower()

    # 1. 카테고리별 긍정 키워드 매칭 (부정문 처리 포함)
    for category, (words, weight) in _POSITIVE_CATEGORIES.items():
        for word in words:
            if word in msg:
                if _is_negated(msg, word):
                    # 부정문: 긍정 → 부정으로 전환
                    delta -= 0.75 * weight
                else:
                    delta += 0.75 * weight
                break  # 카테고리당 1회만

    # 2. 카테고리별 부정 키워드 매칭
    for category, (words, weight) in _NEGATIVE_CATEGORIES.items():
        for word in words:
            if word in msg:
                delta -= 0.75 * weight
                break

    # 3. 대화 길이 보너스 (정성 들인 메시지) - 조건 순서 버그 수정
    if len(message) > 100:
        delta += 1.0
    elif len(message) > 50:
        delta += 0.5

    # 4. 이모티콘/반복 문자 감정 분석
    for emoticon in _EMOTICON_POSITIVE:
        if emoticon in msg:
            delta += 0.5
            break
    for emoticon in _EMOTICON_NEGATIVE:
        if emoticon in msg:
            # ㅠㅠ는 슬픔이지만 친밀감 표현이기도 함
            delta += 0.2
            break

    # 5. 질문 여부 (관심 표현)
    if "?" in message or "？" in message:
        delta += 0.3

    # 6. 문맥 의존 가중치 (호감도 높을 때 긍정 키워드 효과 감소)
    if affinity_level >= 4 and delta > 0:
        delta *= 0.7  # 이미 친한 상태에서 긍정 효과 감소 (쉽게 안 오름)

    # 7. 중립 메시지: 호감도 변화 없음 (일방향 상승 편향 제거)
    if abs(delta) < 0.1:
        delta = 0.0

    # 8. 호감도 레벨별 변화량 차등 (초반 빠른 상승, 후반 느린 상승)
    level_multiplier = {1: 1.5, 2: 1.3, 3: 1.0, 4: 0.7, 5: 0.4}
    delta *= level_multiplier.get(affinity_level, 1.0)

    # 9. 연속 대화 보너스
    if conversation_history:
        history_len = len(conversation_history)
        if history_len >= 10:
            delta += 0.5
        elif history_len >= 5:
            delta += 0.3

    # 10. MBTI 궁합 가중치
    compat = calculate_compatibility(char_mbti, user_mbti)
    delta *= compat

    # 11. 키워드 스케일 보정 (LLM과의 스케일 맞춤)
    delta *= KEYWORD_SCALE

    return round(delta)


# ── 호감도 후퇴 메커니즘 (전문가 합의안) ────────────────────────

# 호감도 레벨별 최소 점수
AFFINITY_LEVEL_THRESHOLDS = {1: 0, 2: 20, 3: 40, 4: 60, 5: 80}

FREEZE_DAYS = 7            # 동결 기간 (일)
DECAY_PER_WEEK = 2         # 주당 하락 점수
RETURN_RECOVERY_RATE = 0.5 # 복귀 시 하락분 회복률


def _storage_scope_id(room_id: str = "", character_id: str = "") -> str:
    return room_id.strip() or character_id.strip()


async def analyze_affinity_with_llm(
    message: str,
    affinity_level: int,
    char_mbti: str,
    recent_context: str = "",
    memory_context: str = "",
) -> int:
    """LLM으로 사용자 메시지의 감정/의도를 분석해 호감도 변화값 반환 (-3 ~ +5)"""
    if not client:
        return 0

    context_section = f"\n최근 대화 맥락:\n{recent_context}" if recent_context else ""
    memory_section = f"\n장기 관계 맥락:\n{memory_context[:300]}" if memory_context else ""

    # MBTI 그룹별 가중치 설명
    group = _get_mbti_group(char_mbti)
    mbti_weight_desc = {
        "NT": "이 캐릭터는 논리적 대화, 지적 토론, 효율적 소통에 높은 점수를 줌",
        "NF": "이 캐릭터는 감정 공유, 공감, 진심 어린 대화에 높은 점수를 줌",
        "ST": "이 캐릭터는 실질적 도움, 약속 이행, 성실한 태도에 높은 점수를 줌",
        "SF": "이 캐릭터는 관심과 배려, 함께하는 시간, 즐거운 대화에 높은 점수를 줌",
    }.get(group, "")

    mbti_trigger = _MBTI_AFFINITY_TRIGGERS.get(char_mbti, "")
    trigger_section = f"\n- 이 캐릭터({char_mbti})의 호감도 증가 요인: {mbti_trigger}" if mbti_trigger else ""

    prompt = f"""사용자 메시지를 분석해서 {char_mbti} 캐릭터에 대한 호감도 변화를 -3~+5 정수로 판단해.
고려 사항:
- 메시지의 감정적 뉘앙스 (단순 키워드가 아닌 전체 맥락)
- 현재 호감도 레벨: {affinity_level}/5 (높을수록 변화 폭 줄임)
- 긍정: 칭찬, 감사, 애정, 공감, 관심 → 양수
- 부정: 비난, 무시, 적대 → 음수
- 중립/일상: 0 또는 약간의 양수
- 연속 긍정/부정 흐름 감지: 3턴 이상 같은 흐름이면 보너스/페널티
- {mbti_weight_desc}{trigger_section}{context_section}{memory_section}

사용자 메시지: "{message}"

JSON만 출력: {{"delta": 정수, "reason": "이유"}}"""

    try:
        response = await client.chat.completions.create(
            model=LLM_MODEL_SIMPLE,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=100,
            timeout=30,
        )
        content = response.choices[0].message.content or ""
        json_str = extract_json_object(content)
        if json_str is not None:
            data = json.loads(json_str)
            delta = int(data.get("delta", 0))
            delta = max(-3, min(5, delta))
            logger.info(f"LLM 호감도 분석: delta={delta}, reason={data.get('reason', '')}")
            return delta

        # JSON 파싱 실패 (토큰 잘림 등): "delta" 값만 regex 추출
        m = re.search(r'"delta"\s*:\s*(-?\d+)', content)
        if m:
            delta = max(-3, min(5, int(m.group(1))))
            logger.info(f"LLM 호감도 분석 (regex fallback): delta={delta}")
            return delta

        logger.warning(f"LLM 호감도 파싱 실패: {content[:100]}")
    except Exception as e:
        logger.warning(f"LLM 호감도 분석 실패 (fallback 사용): {e}")
    return 0


async def extract_memories(
    character_name: str,
    nickname: str,
    conversation_history: List[HistoryMessage],
    character_id: str = "",
    room_id: str = "",
) -> List[MemoryItem]:
    """대화에서 장기 기억 추출 (key-value 쌍)"""
    if not client or len(conversation_history) < 2:
        return []

    try:
        system_prompt = build_memory_extract_prompt(character_name, nickname)
        messages = [{"role": "system", "content": system_prompt}]
        for hist in conversation_history[-30:]:
            role = hist.role if hist.role in ("user", "assistant") else "user"
            if hist.content.strip():
                messages.append({"role": role, "content": hist.content})
        messages.append({"role": "user", "content": "위 대화에서 중요한 개인 정보를 추출해줘."})

        response = await client.chat.completions.create(
            model=LLM_MODEL_SIMPLE,
            messages=messages,
            temperature=0.2,
            max_tokens=300,
            timeout=30,
        )

        content = response.choices[0].message.content or ""
        json_str = extract_json_array(content)
        if json_str is not None:
            data = json.loads(json_str)
            memories = [
                MemoryItem(key=item["key"], value=item["value"])
                for item in data
                if isinstance(item, dict) and item.get("key") and item.get("value")
            ]
            scope_id = _storage_scope_id(room_id, character_id)
            if memories and scope_id:
                store = get_store()
                if store:
                    store.upsert_memories(scope_id, memories)
            return memories
    except Exception as e:
        logger.error(f"메모리 추출 실패: {e}")
    return []


def _jaccard_similarity(text_a: str, text_b: str) -> float:
    """두 텍스트 간 Jaccard 유사도 계산 (단어 집합 기준)"""
    if not text_a or not text_b:
        return 0.0
    set_a = set(text_a.lower().split())
    set_b = set(text_b.lower().split())
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def _filter_relevant_memories(
    message: str, memories: List[MemoryItem], top_k: int = 3
) -> List[MemoryItem]:
    """현재 메시지와 Jaccard 유사도가 높은 상위 top_k 개 메모리만 반환"""
    if not memories:
        return []
    if len(memories) <= top_k:
        return memories

    scored = []
    for mem in memories:
        combined = f"{mem.key} {mem.value}"
        score = _jaccard_similarity(message, combined)
        scored.append((score, mem))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [mem for _, mem in scored[:top_k]]


def _rag_search_sync(scope_id: str, message: str) -> Tuple[List[str], List[dict]]:
    """블로킹 Chroma 검색 — asyncio.to_thread로 실행해 이벤트 루프 보호.

    Returns (relevant_docs, episodes). 스토어 부재/실패 시 빈 결과.
    """
    store = get_store()
    if not store:
        return [], []
    try:
        docs = store.search_relevant(scope_id, message, n_results=3)
    except Exception as e:
        logger.warning(f"[RAG] search_relevant 실패: {e}")
        docs = []
    try:
        episodes = store.search_episodes(scope_id, message, n_results=3)
    except Exception as e:
        logger.warning(f"[RAG] search_episodes 실패: {e}")
        episodes = []
    return docs, episodes


_MEMORY_EXTRACT_INTERVAL = 10  # N턴마다 요약·팩트·에피소드 갱신


def _should_extract_memory(orig_history_len: int) -> bool:
    """기억 추출 트리거 판정.

    반드시 트림 전 원본 히스토리 길이로 판정한다. 트림 후 길이는 10턴
    이후 항상 _MAX_HISTORY(=10)로 고정되어 매 턴 True가 되는 버그가 있었다.
    """
    return orig_history_len >= 4 and orig_history_len % _MEMORY_EXTRACT_INTERVAL == 0


async def _background_memory_extraction(
    character_name: str,
    nickname: str,
    conversation_history: List[HistoryMessage],
    character_id: str,
    room_id: str,
) -> None:
    """백그라운드 메모리 추출 (사용자 응답 블로킹 방지).

    N턴마다 호출되어 대화 요약·팩트·에피소드를 갱신한다. 각 단계는 독립
    실패해도 나머지를 진행한다(부분 성공 허용).
    """
    try:
        await summarize_conversation(
            character_name,
            nickname,
            conversation_history,
            room_id=room_id,
            character_id=character_id,
        )
    except Exception as e:
        logger.warning(f"[memory] 요약 갱신 실패: {e}")
    try:
        await extract_facts(
            character_name,
            nickname,
            conversation_history,
            room_id=room_id,
            character_id=character_id,
        )
    except Exception as e:
        logger.warning(f"[memory] 팩트 추출 실패: {e}")
    try:
        await extract_episodes(
            character_name,
            nickname,
            conversation_history,
            character_id,
            room_id,
        )
    except Exception as e:
        logger.warning(f"[memory] 에피소드 추출 실패: {e}")
    logger.info(f"백그라운드 메모리 추출 완료: {character_name}")


def _build_chat_messages(
    *,
    mbti: str,
    speech_style: str,
    relationship: str,
    nickname: str,
    character_name: str,
    affinity_level: int,
    user_mbti: str,
    persona_raw: str,
    persona_summary: str,
    dialogue_prompt: str,
    visual_prompt: str,
    memory_dicts: Optional[List[dict]],
    mem_ctx: str,
    episode_context: str,
    mood: Optional[str],
    conversation_history: List[HistoryMessage],
    message: str,
    time_context: str = "",
    crisis_hint: str = "",
    user_role: str = "",
    situation: str = "",
) -> List[dict]:
    """시스템 프롬프트 + safety + 히스토리 + 현재 메시지로 messages 배열 조립.

    generate_reply(논스트림)와 stream_reply(스트림)가 공유하여 프롬프트
    정합성을 한 곳에서 보장한다. time_context(C4, 시간대 인지)는
    build_system_prompt의 동적 꼬리 파라미터로 그대로 전달한다 — mood와
    달리 별도 system 메시지가 아니라 프롬프트 본문 안에 들어간다.

    crisis_hint(2026-08-03 P0-S3): 라우터의 _build_crisis_hint가 만든 위기
    대응 지침(검증/마음챙김/마이크로 행동 등). system 메시지의 **맨 끝**,
    safety_prompt 뒤에 그대로 이어붙인다 —
      (i) 정적 프리픽스 뒤의 동적 꼬리라 prefix caching에 영향이 없고,
      (ii) recency 덕에 지시 준수율이 가장 높다.
    빈 문자열이면 기존 프롬프트와 바이트 단위로 동일하다(골든 테스트 불변).
    이전에는 이 지침이 LoRA 제너레이터에만 전달됐고 그 경로가 도달 불가라
    실질적으로 어디에도 적용되지 않았다.

    user_role/situation(2026-08-03 P3-M2): 웹 MVP에서 검증된 [Scene] 이식.
    build_system_prompt의 반동적 구간("# 관계" 직후)에 장면 블록으로 들어간다.
    둘 다 빈 문자열이면 블록 자체가 생성되지 않아 기존 프롬프트와 바이트
    단위로 동일하다(골든 테스트 불변).
    """
    # 유저 발화 스타일 미러링(개인화 되먹임 MVP). 규칙 기반·LLM 미호출.
    # 여기 도달하는 conversation_history는 호출부(generate_reply/stream_reply)에서
    # 이미 최근 10개(=5턴)로 트림된 상태 → 스타일도 최근 5턴 기준으로 산출된다.
    preference_context = render_preference_section(
        derive_user_style(conversation_history)
    )
    system_prompt = build_system_prompt(
        mbti=mbti,
        speech_style=speech_style,
        relationship=relationship,
        nickname=nickname,
        character_name=character_name,
        affinity_level=affinity_level,
        user_mbti=user_mbti or "",
        persona_raw=persona_raw,
        persona_summary=persona_summary,
        dialogue_prompt=dialogue_prompt,
        visual_prompt=visual_prompt,
        memories=memory_dicts if memory_dicts else None,
        memory_context=mem_ctx,
        episode_context=episode_context,
        preference_context=preference_context,
        time_context=time_context,
        user_role=user_role,
        situation=situation,
    )
    # safety_prompt는 거의 변하지 않으므로 정적 system_prompt에 인라인하여 prefix caching 효율 극대화
    safety_prompt = get_safety_system_prompt()
    combined_prompt = f"{system_prompt}\n\n{safety_prompt}" if safety_prompt else system_prompt
    # 위기 지침은 항상 맨 끝(동적 꼬리) — 빈 문자열이면 위 문자열과 완전히 동일
    if crisis_hint:
        combined_prompt = f"{combined_prompt}{crisis_hint}"
    messages: List[dict] = [{"role": "system", "content": combined_prompt}]
    # mood만 별도 system 메시지로 분리 (동적 블록)
    if mood:
        messages.append({"role": "system", "content": f"[사용자 오늘 기분: {mood}]"})
    # 대화 히스토리 추가 (DCI에서 이미 최근 10개로 제한됨)
    for hist in conversation_history:
        role = hist.role if hist.role in ("user", "assistant") else "user"
        if hist.content.strip():
            messages.append({"role": role, "content": hist.content})
    # 현재 메시지 (prompt injection 방어를 위한 명시적 경계)
    messages.append({"role": "user", "content": f"[사용자 메시지]\n{message}\n[/사용자 메시지]"})
    return messages


def _apply_crisis_override(model_id: str, crisis_tier: int) -> str:
    """위기 턴이면 모델을 상위 모델로 승격한다(2026-08-03 P0-S3).

    판정은 model_routing.select_model_for_crisis 를 그대로 재사용해 이중
    구현을 피한다 — 그 함수의 의도(위기 턴은 파인튜닝/A/B 배정과 무관하게
    상위 OpenAI 모델로 보낸다)를 여기서도 동일하게 따른다. 다만 알 수 없는
    tier 값으로 인한 **강등**은 절대 일어나지 않도록 승격 방향만 허용한다.

    이전에는 라우터가 select_model_for_crisis 결과를 로그/이벤트 payload에만
    쓰고 생성 경로에 넘기지 않아, Tier1 자해 신호 턴도 mini로 처리될 수 있었다.
    """
    if crisis_tier < 1:
        return model_id
    crisis_model = select_model_for_crisis({"level": crisis_tier})
    if crisis_model != LLM_MODEL_COMPLEX or crisis_model == model_id:
        return model_id
    logger.info(
        "[Crisis] 위기 감지(tier=%s) → 모델 승격: %s → %s",
        crisis_tier, model_id, crisis_model,
    )
    return crisis_model


def _route_model_with_complexity(
    character_id: str, message: str, history_len: int, crisis_tier: int = 0
) -> Tuple[str, Optional[str], str]:
    """모델 선택: 복잡도 라우팅이 기준선, A/B는 그 위의 정책 오버레이.

    Returns (model_id, ab_variant, complexity).
    crisis_tier>=1 이면 모든 분기의 결과를 상위 모델로 승격한다(P0-S3).
    complexity 는 계측용("simple" | "complex") — 분류기 판정과 실제 사용 모델을
    사후에 대조할 수 있도록 turn_latency / A/B 결과 기록에 함께 남긴다.

    2026-08-03 회의 P0-S2 이전에는 character_id가 있으면(라우터에서 사실상 항상
    채워짐) A/B variant 문자열을 그대로 모델 ID로 반환해 복잡도 분류기가 아예
    실행되지 않았다 — 캐릭터별 sha256 해시로 모델이 영구 고정되어 심층 상담도
    mini로, "ㅇㅇ" 한 마디에도 4.1로 갔고 A/B 결과도 캐릭터 고정 배정에 교란됐다.

    현재 순서:
      1) 복잡도 분류를 **항상** 실행 → base 모델 결정
      2) 파인튜닝 모델이 있으면 그것을 우선(기존 동작 유지)
      3) A/B variant는 정책으로만 작동 — MODEL_ROUTING_ALWAYS_COMPLEX 배정 시
         base를 상위 모델로 승격, 대조군은 복잡도 라우팅 결과 그대로
    """
    try:
        complexity = _classify_message_complexity(message, history_len)
    except Exception as _cls_err:  # pragma: no cover - 순수 문자열 연산이라 사실상 도달 불가
        logger.warning("[Routing] 복잡도 분류 실패, simple로 폴백: %s", _cls_err)
        complexity = "simple"
    base_model = LLM_MODEL_COMPLEX if complexity == "complex" else LLM_MODEL_SIMPLE

    finetuned_model = get_model_for_character(character_id) if character_id else None
    if finetuned_model and finetuned_model != LLM_MODEL_COMPLEX:
        # 파인튜닝 모델 우선 — 단 위기 턴은 상위 모델로 승격(select_model_for_crisis 의도)
        return _apply_crisis_override(finetuned_model, crisis_tier), None, complexity

    if not character_id:
        return _apply_crisis_override(base_model, crisis_tier), None, complexity

    try:
        # 지연 임포트: 순환/기동 순서 회피
        from .ab_test import (
            MODEL_ROUTING_ALWAYS_COMPLEX,
            MODEL_ROUTING_EXPERIMENT_ID,
            get_ab_manager,
        )
        ab_variant = get_ab_manager().assign_variant(
            user_id=character_id,
            experiment_id=MODEL_ROUTING_EXPERIMENT_ID,
        )
    except Exception as _ab_err:
        logger.warning("[AB] variant 배정 실패, 복잡도 라우팅 결과 유지: %s", _ab_err)
        return _apply_crisis_override(base_model, crisis_tier), None, complexity

    model_id = LLM_MODEL_COMPLEX if ab_variant == MODEL_ROUTING_ALWAYS_COMPLEX else base_model
    model_id = _apply_crisis_override(model_id, crisis_tier)
    logger.info(
        "[AB] model_routing: character_id=%s complexity=%s variant=%s → model=%s",
        character_id, complexity, ab_variant, model_id,
    )
    return model_id, ab_variant, complexity


def _route_model(
    character_id: str, message: str, history_len: int
) -> Tuple[str, Optional[str]]:
    """_route_model_with_complexity의 (model_id, ab_variant) 뷰 — 기존 계약 유지."""
    model_id, ab_variant, _complexity = _route_model_with_complexity(
        character_id, message, history_len
    )
    return model_id, ab_variant


async def _record_quality_gate_event(
    score: float,
    user_msg: str,
    ai_response: str,
    model_id: str,
    room_id: str,
    character_id: str,
    extra_payload: Optional[dict] = None,
) -> None:
    """저품질 응답 감지 시 quality_gate_triggered 이벤트를 기록한다.

    generate_reply/stream_reply가 공유. extra_payload로 payload 확장
    필드를 흡수(스트리밍 경로만 기존에 "streaming": True 를 추가로 남겼음).
    P2: 두 호출부 모두 메인 응답 경로에서 직접 await하는 자리이므로(품질
    게이트가 실제로 발동했을 때만 실행되는 드문 경로) record_event_async로
    전환해 이벤트 루프 블로킹을 없앤다.
    """
    payload = {
        "score": score,
        "issues": classify_quality_issues(user_msg, ai_response),
        "model_id": model_id,
    }
    if extra_payload:
        payload.update(extra_payload)
    await record_event_async(
        event_type="quality_gate_triggered",
        room_id=room_id,
        character_id=character_id,
        payload=payload,
    )


async def _quality_gate_regenerate(
    replies: List[ReplyPart],
    content: str,
    score: float,
    message: str,
    mbti: str,
    model_id: str,
    messages: List[dict],
    active_client: AsyncOpenAI,
    openai_cb,
    room_id: str,
    character_id: str,
) -> Tuple[List[ReplyPart], str, float]:
    """품질 게이트: 저품질 응답(score < QUALITY_GATE_THRESHOLD) 감지 시 1회 재생성,
    점수 비교 후 더 좋은 쪽을 채택한다.

    generate_reply 전용 헬퍼(stream_reply의 저품질 처리는 재생성 없이 텔레메트리만
    남기므로 별개 — 이 함수의 대상이 아님). 호출부에서 이미
    `score < QUALITY_GATE_THRESHOLD` 판정을 마친 뒤 호출됨을 전제로 한다.

    Returns (replies, content, effective_score) — 재시도가 원본보다 낫지 않으면
    입력을 그대로 반환하고 effective_score도 원본 score를 유지한다.
    effective_score(2026-08-03 M4-①): 실제로 채택된 응답의 quick_score —
    게이트/재시도 로직은 그대로이며, 호출부가 quality_score 이벤트에
    남길 최종 점수를 얻기 위해 추가된 반환값이다.
    """
    await _record_quality_gate_event(score, message, content, model_id, room_id, character_id)
    logger.info(f"품질 게이트 발동 (score={score}), 재생성 시도")

    # 첫 응답이 JSON 파싱 깨짐(매우 낮은 점수)이면 형식 강제 보강.
    # response_format=json_object는 배열 형식과 호환 깨지므로 사용 X.
    # prefix caching 유지를 위해 기존 messages는 그대로 두고,
    # 트레일링 user 메시지만 추가해 형식만 다시 환기시킨다.
    retry_messages = messages
    if score <= 0.2:  # 형식 자체가 깨진 경우만
        retry_messages = messages + [{
            "role": "user",
            "content": (
                "직전 응답 형식이 올바르지 않았어. 반드시 "
                '[{"text":"...","emotion":"EMOTION_CODE"}] '
                "형태의 JSON 배열로만 다시 답해줘. "
                "코드블록·설명·다른 텍스트는 절대 붙이지 마."
            ),
        }]

    try:
        retry_response = await openai_cb.call(
            active_client.chat.completions.create(
                model=model_id,
                messages=retry_messages,
                temperature=0.9,
                max_tokens=1200,
                timeout=45,
            )
        )
    except CircuitOpenError:
        logger.warning("[CB] openai circuit OPEN — 품질 게이트 재시도 스킵")
        retry_response = None

    effective_score = score
    if retry_response:
        retry_content = retry_response.choices[0].message.content or ""
        retry_replies = _parse_reply(retry_content)
        if retry_replies:
            retry_score = quick_score(message, _reconstruct_score_source(retry_replies), mbti)
            # 원본과 재시도 중 점수가 더 높은 쪽 채택.
            # 동점이면 재시도(더 최신·형식 보강 반영)를 선호.
            if retry_score >= score:
                logger.info(
                    f"재생성 채택 (retry={retry_score} >= orig={score})"
                )
                replies = retry_replies
                content = retry_content
                effective_score = retry_score
            else:
                logger.info(
                    f"원본 유지 (orig={score} > retry={retry_score})"
                )

    return replies, content, effective_score


async def _record_turn_latency_event(
    room_id: str,
    character_id: str,
    model_id: str,
    streaming: bool,
    t_memory_ms: float,
    t_rag_ms: float,
    t_first_token_ms: float,
    complexity: str = "",
    crisis_tier: int = 0,
    memory_cache_hit: bool = False,
    t_gate_ms: float = 0.0,
    t_e2e_first_bubble_ms: Optional[float] = None,
    t_e2e_total_ms: Optional[float] = None,
    outcome: str = "ok",
) -> None:
    """턴 단계별 레이턴시(P1 계측)를 turn_latency 이벤트로 기록.

    generate_reply/stream_reply가 공유. `_record_usage`/`_record_ab_result`와
    동일하게 create_tracked_task로 fire-and-forget 스케줄되어 메인 응답
    경로를 블로킹하지 않는다. P2: record_event_async로 전환해 이 백그라운드
    태스크 내부에서도 이벤트 루프를 블로킹하지 않도록 정리했다.

    complexity(2026-08-03 P0-S2): 복잡도 분류기 판정("simple"|"complex").
    실제 사용 모델은 기존 model_id 필드가 그대로 담고 있으므로, 둘을 대조하면
    분류기 정확도와 A/B 정책 오버레이의 승격 빈도를 사후 검증할 수 있다.

    crisis_tier(2026-08-03 P0-S3): 위기 감지 tier(0=비위기). complexity는
    분류기 원판정 그대로 두고 이 필드를 추가했으므로,
    complexity="simple" & crisis_tier>=1 & model_id=상위모델 조합으로
    "위기 승격이 실제 일어난 턴"을 사후에 정확히 셀 수 있다.

    memory_cache_hit(2026-08-03 P1-S4): 기억 컨텍스트 조회가 DB 왕복 없이
    처리됐는지(positive 캐시/네거티브 캐시/postgres 비활성). t_memory_ms와
    대조하면 네거티브 캐시가 신규 방의 반복 조회를 실제로 없앴는지 검증된다.

    2026-08-03 P1(회의 항목1): 기존에는 t_gate(라우터 게이트 단계)를 의도적으로
    제외하고 t_first_token도 LLM 호출 시작 기준이라 사용자 체감 end-to-end
    TTFT를 대표하지 못했다. 라우터(routers/chat.py)가 요청 진입 시각부터
    측정한 t_gate_ms(게이트 단계 소요)와 t_e2e_first_bubble_ms(스트리밍,
    요청 진입~첫 말풍선 SSE 전송 직전)/t_e2e_total_ms(논스트림, 요청 진입~
    응답 완성)를 넘겨주면 payload에 포함한다. 라우터가 값을 넘기지 않는
    호출부(기존 테스트 등)는 t_gate_ms=0.0, e2e 필드는 아예 payload에서
    빠져 기존 동작과 동일하다 — 게이트/재생성 판정 로직에는 전혀 관여하지
    않는 순수 계측 필드.

    outcome(2026-08-04 M-G): 턴의 종료 형태.
      "ok"           — 정상 완료(기본값, 기존 호출부는 전부 이 값)
      "error"        — LLM/파이프라인 예외로 폴백 응답을 낸 턴
      "circuit_open" — 서킷브레이커 OPEN으로 목업을 낸 턴
      "aborted"      — 스트리밍 중 클라이언트가 조기 종료한 턴(H3)
    이전에는 성공한 턴만 turn_latency를 남겨 레이턴시 분포에 생존편향이
    있었다(느려서 타임아웃/실패한 턴이 통계에서 사라짐). 필드는 추가만
    되므로 기존 payload 필드/의미는 불변.
    """
    payload = {
        "model_id": model_id,
        "streaming": streaming,
        "t_memory_ms": round(t_memory_ms, 2),
        "t_rag_ms": round(t_rag_ms, 2),
        "t_first_token_ms": round(t_first_token_ms, 2),
        "complexity": complexity,
        "crisis_tier": crisis_tier,
        "t_memory_cache_hit": bool(memory_cache_hit),
        "t_gate_ms": round(t_gate_ms, 2),
        "outcome": outcome or "ok",
    }
    if t_e2e_first_bubble_ms is not None:
        payload["t_e2e_first_bubble_ms"] = round(t_e2e_first_bubble_ms, 2)
    if t_e2e_total_ms is not None:
        payload["t_e2e_total_ms"] = round(t_e2e_total_ms, 2)
    logger.info(
        "[latency] room=%s model=%s complexity=%s crisis_tier=%s streaming=%s outcome=%s memory=%.1fms(cache_hit=%s) rag=%.1fms first_token=%.1fms gate=%.1fms",
        room_id, model_id, complexity, crisis_tier, streaming, payload["outcome"],
        t_memory_ms, bool(memory_cache_hit), t_rag_ms, t_first_token_ms, t_gate_ms,
    )
    try:
        await record_event_async(
            event_type="turn_latency",
            room_id=room_id,
            character_id=character_id,
            payload=payload,
        )
    except Exception as e:
        logger.warning(f"턴 레이턴시 이벤트 기록 실패: {e}")


async def _collect_affinity_delta(
    affinity_task: Optional[asyncio.Task],
    message: str,
    affinity_level: int,
    conversation_history: List[HistoryMessage],
    user_mbti: Optional[str],
    mbti: str,
    warn_message: str,
) -> int:
    """호감도 분석 병렬 태스크 결과를 수거하고, 실패하거나 0이면 키워드 폴백.

    generate_reply/stream_reply가 공유. warn_message로 실패 로그 문구를
    호출부별로 다르게 유지(기존 두 함수의 로그 메시지가 서로 달랐음).
    """
    affinity_delta = 0
    if affinity_task is not None:
        try:
            affinity_delta = await affinity_task
        except Exception as e:
            logger.warning(f"{warn_message}: {e}")
            affinity_delta = 0
        if affinity_delta == 0:
            affinity_delta = calculate_affinity_delta(
                message, affinity_level, conversation_history, user_mbti, mbti
            )
    return affinity_delta


async def _merge_rag_results(
    rag_task: Optional[asyncio.Task],
    memories: Optional[List[MemoryItem]],
    warn_context: str,
) -> Tuple[List[MemoryItem], str]:
    """RAG(Chroma) 검색 태스크 결과를 dedupe 병합하고 에피소드 컨텍스트를 만든다.

    generate_reply/stream_reply가 공유. warn_context로 실패 로그 문구를
    호출부별로 다르게 유지(기존 두 함수의 로그 메시지가 서로 달랐음).
    Returns (all_memories, episode_context).
    """
    all_memories = list(memories or [])
    episode_context = ""
    if rag_task is not None:
        try:
            rag_docs, episodes = await rag_task
        except Exception as e:
            logger.warning(f"[RAG] {warn_context} 실패, 스킵: {e}")
            rag_docs, episodes = [], []

        existing_keys = {m.key for m in all_memories}
        for doc in rag_docs:
            if ": " in doc:
                key, value = doc.split(": ", 1)
                if key not in existing_keys:
                    all_memories.append(MemoryItem(key=key, value=value))
                    existing_keys.add(key)

        if episodes:
            ep_lines = ["## 떠오르는 기억"]
            ep_lines.append("이 기억들을 대화에서 자연스럽게 활용할 수 있으면 활용해.")
            for ep in episodes:
                ep_lines.append(f"- {ep['text']} (감정: {ep['emotion']})")
            episode_context = "\n".join(ep_lines)

    return all_memories, episode_context


async def _resolve_reply_client(
    model_id: str,
    ab_variant: Optional[str],
) -> Tuple[AsyncOpenAI, str]:
    """모델 ID 라우팅 계약(resolve_model_endpoint)을 보존한 얇은 래퍼.

    generate_reply/stream_reply가 공유. LoRA 서빙 경로는 2026-08-11 소유자
    결정으로 제거됨 — ChatRequest에 ab_variant 필드가 없어(2026-08-03 회의
    S3-c 확정) 애초에 어떤 요청도 도달할 수 없었던 사문 코드였다.
    resolve_model_endpoint는 이제 base_model을 그대로 반환하므로 클라이언트는
    항상 기본 OpenAI 클라이언트다.
    Returns (active_client, model_id).
    """
    resolved_model_id, _base_url = await resolve_model_endpoint(
        model_id, ab_variant or ""
    )
    return client, resolved_model_id


def _build_recent_context(
    conversation_history: List[HistoryMessage], limit: int = 8
) -> str:
    """최근 limit개 메시지를 "사용자/캐릭터: 내용" 형식으로 조인.

    호감도 분석 프롬프트 입력용. generate_reply/stream_reply가 공유.
    """
    if not (conversation_history and len(conversation_history) >= 2):
        return ""
    recent_msgs = conversation_history[-limit:]
    return "\n".join(
        f"{'사용자' if h.role == 'user' else '캐릭터'}: {h.content}"
        for h in recent_msgs if h.content.strip()
    )


def _trim_history(
    conversation_history: List[HistoryMessage], max_history: int = 10
) -> Tuple[List[HistoryMessage], int]:
    """대화 히스토리를 최대 max_history개로 짝수(user+assistant 쌍) 트림.

    generate_reply/stream_reply가 공유. (trimmed_history, orig_len) 반환.
    """
    orig_len = len(conversation_history)
    if orig_len > max_history:
        trim_to = max_history if max_history % 2 == 0 else max_history - 1
        conversation_history = conversation_history[-trim_to:]
    return conversation_history, orig_len


def _safety_check_input(message: str) -> Optional[Tuple[List[ReplyPart], int]]:
    """사용자 입력 콘텐츠 안전 필터 (H-1).

    generate_reply/stream_reply가 공유(S13/S14 잔여 본문 분할). 차단되면
    즉시 반환할 (blocked_reply, -2) 튜플을, 안전하면 None을 반환한다.
    stream_reply는 반환된 튜플을 그대로 return하지 않고 개별 ReplyPart를
    yield한 뒤 StreamDone을 yield하고 return하는 형태로 변환해 사용한다
    (yield 페이로드는 이 함수가 만드는 ReplyPart와 바이트 동일).
    """
    is_safe, _reason = check_content(message)
    if not is_safe:
        return [ReplyPart(
            text="그런 표현은 사용하지 말아줘요... 다른 이야기 해볼까요?",
            emotion="SAD",
            delay=2000
        )], -2
    return None


class MemoryFetch(NamedTuple):
    """_spawn_parallel_analysis의 memory_context 조회 결과 + 상태(P1-S4).

    context: 조회된 기억 컨텍스트(기억이 없으면 정당하게 빈 문자열).
    ok: 조회가 정상 완료됐는지. False는 "예외로 실패" 뿐이며, 이때만 호출부가
        방어적으로 재조회한다(빈 문자열이 정당한 결과인 신규 방에서 같은
        함수를 TTFT 직렬 경로에서 한 번 더 부르던 낭비 제거).
    cache_hit: 이 조회가 DB 왕복 없이 처리됐는지(계측용).
    """

    context: str
    ok: bool
    cache_hit: bool


async def _spawn_parallel_analysis(
    message: str,
    mbti: str,
    affinity_level: int,
    conversation_history: List[HistoryMessage],
    user_mbti: Optional[str],
    character_name: str,
    nickname: str,
    character_id: str,
    room_id: str,
    skip_affinity: bool = False,
) -> Tuple[Optional[asyncio.Task], int, MemoryFetch]:
    """메모리 컨텍스트 태스크 + 호감도 분석 태스크를 관리(클라이언트 있을 때만).

    클라이언트가 없으면 즉시 키워드 기반 호감도를 계산한다.

    generate_reply/stream_reply가 공유. P6 변경: RAG 검색 태스크는 더 이상
    이 함수가 만들지 않는다 — 호출부가 이 함수를 부르기 *전에* 이미 생성해
    시작해 둔다(TTFT 단축: memory와 RAG 대기를 겹치기 위함, P1 실측
    memory=1176ms/rag=449ms 완전 직렬 → 이론상 ~449ms 절감). 이 함수는 대신
    build_memory_context를 태스크로 만들어 그 대기 시간 동안 RAG가 동시에
    진행되게 하고, 호감도 분석은 memory_context를 입력으로 받으므로(기존
    의존성 유지) memory task가 끝난 뒤에만 생성한다.

    memory task의 생성·대기·예외 처리·취소는 이 함수가 전부 책임지고
    끝낸다 — 성공/실패/(외부 취소로 인한) 모든 경로에서 이 함수를 벗어나기
    전에 반드시 완료되거나 취소되므로, 호출부가 "메모리 task"를 별도로
    추적·취소할 필요가 없다(고아 태스크 방지를 함수 경계 안에서 보장).
    실패 시 폴백은 RAG의 _merge_rag_results와 동일한 패턴(빈 컨텍스트로
    대체 + 경고 로그)을 따른다.

    skip_affinity(선톡/proactive 경로): 유저 발화가 없는 턴이라 호감도 변화의
    대상이 아니다 — 분석 태스크를 아예 만들지 않고 delta를 0으로 고정한다
    (LLM 호출 1회 절약). 기본값 False면 기존 동작과 완전히 동일하다.

    affinity_task는 기존과 동일하게(예외 시 취소 책임 포함) 호출부가
    소유한다 — 헬퍼 안에서 await/취소하지 않는다. 클라이언트가 없을 때의
    처리(목업 응답 생성)는 두 호출부가 서로 다르므로(generate_reply는
    return, stream_reply는 yield 후 return) 호출부에서 각자 담당한다.
    Returns (affinity_task, affinity_delta, MemoryFetch).
    """
    affinity_delta = 0
    pre_mem_ctx = ""
    mem_ok = True
    # Low-1(2026-08-04 점검): character_name/nickname이 비어 조회 자체를 하지
    # 않는 경우 기본값은 False여야 한다. 이전에는 True로 시작해 "조회를
    # 안 했다"와 "캐시에서 처리됐다"가 텔레메트리상 구분 불가능했고, 조회
    # 스킵 턴이 전부 긍정 캐시 히트로 오집계되어 캐시 효율 지표가 부풀려졌다.
    mem_cache_hit = False

    # 메모리 컨텍스트를 태스크로 시작 — 호출부가 이미 만들어 둔 RAG task와
    # 동시에 진행된다(RAG task는 이 함수 호출 전에 이미 스레드에서 실행 중).
    mem_task: Optional[asyncio.Task] = None
    if character_name and nickname:
        # 계측(P1-S4): 조회 *전에* 캐시 상태를 확인해야 "이 턴이 캐시에서
        # 처리됐는지"를 알 수 있다. 순수 in-memory 조회라 부하가 없다.
        mem_cache_hit = is_memory_cached(
            character_name,
            nickname,
            room_id=room_id,
            character_id=character_id,
        )
        mem_task = asyncio.create_task(
            build_memory_context(
                character_name,
                nickname,
                room_id=room_id,
                character_id=character_id,
            )
        )

    try:
        if mem_task is not None:
            try:
                pre_mem_ctx = await mem_task
            except Exception as e:
                logger.warning(f"[P6] 메모리 컨텍스트 조회 실패, 빈 컨텍스트로 대체: {e}")
                pre_mem_ctx = ""
                mem_ok = False
    finally:
        # await가 정상 반환/Exception 둘 다에서 mem_task는 이미 done 상태다.
        # 이 finally는 외부 취소(CancelledError)로 await 자체가 중단된
        # 극히 드문 경우까지 커버하기 위한 방어적 정리(정상 흐름에서는 no-op).
        if mem_task is not None and not mem_task.done():
            mem_task.cancel()

    if skip_affinity:
        # 선톡 경로: 유저 발화가 없으므로 분석하지 않고 delta 0 고정.
        affinity_task = None
        affinity_delta = 0
    elif client:
        recent_context = _build_recent_context(conversation_history)
        # 호감도 분석을 비동기 태스크로 시작 (메인 LLM 호출과 병렬 실행)
        affinity_task = asyncio.create_task(
            analyze_affinity_with_llm(
                message, affinity_level, mbti, recent_context,
                memory_context=pre_mem_ctx,
            )
        )
    else:
        affinity_task = None
        affinity_delta = calculate_affinity_delta(
            message, affinity_level, conversation_history, user_mbti, mbti
        )

    return affinity_task, affinity_delta, MemoryFetch(pre_mem_ctx, mem_ok, mem_cache_hit)


async def _assemble_prompt_and_model(
    mbti: str,
    speech_style: str,
    relationship: str,
    nickname: str,
    character_name: str,
    affinity_level: int,
    user_mbti: Optional[str],
    persona_raw: str,
    persona_summary: str,
    dialogue_prompt: str,
    visual_prompt: str,
    memory_dicts: List[dict],
    mem_ctx: str,
    episode_context: str,
    mood: Optional[str],
    conversation_history: List[HistoryMessage],
    message: str,
    character_id: str,
    time_context: str = "",
    crisis_tier: int = 0,
    crisis_hint: str = "",
    user_role: str = "",
    situation: str = "",
) -> Tuple[List[dict], str, Optional[str], AsyncOpenAI, str]:
    """시스템 프롬프트 조립 + 모델 라우팅(파인튜닝/복잡도/AB 오버레이).

    generate_reply/stream_reply가 공유(S13/S14 잔여 본문 분할). LoRA 클라이언트
    해석 단계는 2026-08-11 소유자 결정으로 제거됨(_resolve_reply_client가 이제
    항상 기본 OpenAI 클라이언트를 반환 — 상세는 그 함수 docstring 참고).
    Returns (messages, model_id, ab_variant, active_client, complexity).
    complexity는 계측 전용(turn_latency / A/B 결과 기록)이다.
    time_context(C4)는 그대로 _build_chat_messages → build_system_prompt로
    전달한다(동적 꼬리 전용 파라미터, 정적 프리픽스 불변).

    crisis_tier/crisis_hint(2026-08-03 P0-S3): 라우터가 detect_crisis_v2 /
    _build_crisis_hint 로 계산해 넘긴다. tier는 모델 승격에, hint는 시스템
    프롬프트 꼬리 주입에 쓰인다. 둘 다 기본값(0/"")이면 기존 동작과 동일.

    user_role/situation(2026-08-03 P3-M2): ChatRequest에서 온 장면 설정을
    _build_chat_messages → build_system_prompt로 그대로 전달한다(빈 값이면
    프롬프트 무변화).
    """
    messages = _build_chat_messages(
        mbti=mbti,
        speech_style=speech_style,
        relationship=relationship,
        nickname=nickname,
        character_name=character_name,
        affinity_level=affinity_level,
        user_mbti=user_mbti or "",
        persona_raw=persona_raw,
        persona_summary=persona_summary,
        dialogue_prompt=dialogue_prompt,
        visual_prompt=visual_prompt,
        memory_dicts=memory_dicts,
        mem_ctx=mem_ctx,
        episode_context=episode_context,
        mood=mood,
        conversation_history=conversation_history,
        message=message,
        time_context=time_context,
        crisis_hint=crisis_hint,
        user_role=user_role,
        situation=situation,
    )

    # 모델 선택 (복잡도 기반 라우팅이 기준선 + A/B 정책 오버레이 + 위기 승격)
    model_id, ab_variant, complexity = _route_model_with_complexity(
        character_id, message, len(conversation_history), crisis_tier=crisis_tier
    )

    active_client, model_id = await _resolve_reply_client(model_id, ab_variant)

    return messages, model_id, ab_variant, active_client, complexity


def _extract_cached_tokens(usage) -> int:
    """OpenAI usage 객체에서 prefix cache 히트 토큰 수를 안전하게 추출한다.

    2026-08-03 P2(회의 항목2): `usage.prompt_tokens_details.cached_tokens`를
    아무도 읽지 않아 prefix cache 히트율이 완전 미지였다. usage 자체가
    없거나(목업/실패 응답) prompt_tokens_details가 없는 구버전 SDK/엔드포인트
    에서도 getattr 체인으로 안전하게 0을 반환한다.
    """
    if usage is None:
        return 0
    details = getattr(usage, "prompt_tokens_details", None)
    if details is None:
        return 0
    return getattr(details, "cached_tokens", 0) or 0


def _emit_background_metrics(
    response,
    model_id: str,
    room_id: str,
    character_id: str,
    ab_variant: Optional[str],
    elapsed_ms: float,
    message: str,
    result: List[ReplyPart],
    mbti: str,
    affinity_level: int,
    complexity: str = "",
    quick_score_value: Optional[float] = None,
) -> None:
    """LLM 응답 후 비용/AB 테스트/품질 평가를 백그라운드(fire-and-forget)로 기록.

    generate_reply 전용(잔여 본문 분할, S13). stream_reply(S14 검토 결과)는
    이 헬퍼를 재사용하지 않는다 — usage 소스가 다르고(response.usage 객체
    vs 스트리밍 청크에서 누적한 _stream_total_tokens float), _record_usage
    호출 자체가 없으며, quality-check 조건(if full_text:)과 3개 블록의
    실행 순서(quality-check→AB, generate_reply는 usage→AB→quality-check)도
    다르다. 모든 부수효과는 create_tracked_task로 스케줄링되며 태스크
    소유권은 background_tasks 모듈이 관리하므로 본문이 별도로 정리할
    필요가 없다(반환값 없음).

    quick_score_value(2026-08-03 M4-①, 회의 항목3): 호출부(generate_reply)가
    게이트 판정에 이미 사용한 quick_score 값을 그대로 전달받아 quality_score
    payload에 실어 분포를 남긴다(재계산하지 않음). None이면(예: replies가
    비어 quick_score를 계산하지 못한 경우) score_response_async에도 None이
    그대로 전달된다.
    """
    # H-3: 비용 메트릭 백그라운드 기록
    usage = getattr(response, "usage", None)
    if usage:
        create_tracked_task(_record_usage(
            room_id=room_id,
            character_id=character_id,
            model_id=model_id,
            prompt_tokens=getattr(usage, "prompt_tokens", 0),
            completion_tokens=getattr(usage, "completion_tokens", 0),
            cached_tokens=_extract_cached_tokens(usage),
        ), name="record-usage")

    # A/B 테스트 결과 기록 (백그라운드)
    if ab_variant and character_id:
        total_tokens = getattr(usage, "total_tokens", 0) if usage else 0
        create_tracked_task(_record_ab_result(
            experiment_id="model_routing",  # ab_test.MODEL_ROUTING_EXPERIMENT_ID
            variant=ab_variant,
            user_id=character_id,
            character_id=character_id,
            tokens=float(total_tokens),
            response_time_ms=elapsed_ms,
            complexity=complexity,
            model_id=model_id,
        ), name="record-ab-result")

    # 백그라운드 품질 평가 (사용자 지연 0)
    full_response = " ".join(r.text for r in result)
    create_tracked_task(
        _post_response_quality_check(
            message,
            full_response,
            mbti,
            affinity_level,
            room_id=room_id,
            character_id=character_id,
            quick_score_value=quick_score_value,
        ),
        name="quality-check",
    )


async def generate_reply(
    message: str,
    mbti: str,
    speech_style: str,
    relationship: str,
    nickname: str,
    affinity_level: int = 1,
    conversation_history: List[HistoryMessage] = None,
    user_mbti: Optional[str] = None,
    character_name: str = "",
    character_id: str = "",
    persona_raw: str = "",
    persona_summary: str = "",
    dialogue_prompt: str = "",
    visual_prompt: str = "",
    memories: List[MemoryItem] = None,
    mood: Optional[str] = None,
    room_id: str = "",
    owner_uid: str = "",
    time_context: str = "",
    crisis_tier: int = 0,
    crisis_hint: str = "",
    request_start_ts: Optional[float] = None,
    gate_ms: float = 0.0,
    user_role: str = "",
    situation: str = "",
) -> Tuple[List[ReplyPart], int]:
    """LLM을 사용하여 대화 응답 생성, (replies, affinity_delta) 반환.

    time_context(C4): 라우터가 client_local_hour를 아침/낮/저녁/밤 구간
    문구로 미리 변환해 넘긴다("" 이면 시간 블록 자체가 프롬프트에 삽입되지
    않음, 기존 동작과 동일). build_system_prompt의 동적 꼬리 파라미터로만
    전달되므로 정적 프리픽스(prefix caching 대상)에는 영향 없다.

    crisis_tier/crisis_hint(2026-08-03 P0-S3): 라우터가 detect_crisis_v2 /
    _build_crisis_hint 결과를 넘긴다. tier>=1이면 복잡도/A/B 판정과 무관하게
    상위 모델로 승격하고, hint는 시스템 프롬프트 맨 끝에 주입되어 캐릭터
    응답 자체가 위기 상황을 인지하게 한다. 기본값(0/"")이면 기존 동작 그대로.

    request_start_ts/gate_ms(2026-08-03 P1, 회의 항목1): 라우터(routers/chat.py)가
    요청 진입 시각(time.monotonic())과 게이트(_gate_user) 소요를 넘겨주면
    turn_latency 이벤트에 t_e2e_total_ms(요청 진입~응답 완성)와 t_gate_ms를
    함께 남긴다. 기본값(None/0.0)이면 두 필드 중 t_e2e_total_ms는 payload에서
    빠지고 t_gate_ms는 0.0으로 기록되어 기존 동작과 동일하다 — 순수 계측용.

    user_role/situation(2026-08-03 P3-M2): 라우터가 ChatRequest에서 그대로
    넘기는 장면 설정. 시스템 프롬프트의 "# 관계" 직후에 장면 블록으로
    주입된다. 기본값("")이면 블록이 생성되지 않아 기존 동작과 동일.
    """

    if conversation_history is None:
        conversation_history = []

    # ── Dynamic Context Injection (W2-1) ──────────────────────────────
    # 1. 대화 히스토리 서버사이드 제한: 최근 10개 메시지(user+assistant 쌍 유지)
    conversation_history, _orig_history_len = _trim_history(conversation_history)

    # 2. 메모리 관련성 필터링은 RAG 병합 후 적용 (LLM 호출 직전)
    _orig_memories_len = len(memories) if memories else 0
    # ──────────────────────────────────────────────────────────────────

    # 1. 사용자 입력 필터링 (H-1 활성화)
    _blocked = _safety_check_input(message)
    if _blocked is not None:
        return _blocked

    # P6: RAG(Chroma) 검색을 memory-context 조회보다 먼저 시작해 두 대기가
    # 겹치게 한다(P1 실측: memory=1176ms, rag=449ms 완전 직렬 → 이론상 ~449ms
    # 절감). 안전 필터를 통과한 뒤에만 생성해 위 차단 경로에서 고아 태스크가
    # 생기지 않도록 한다. client가 없으면(mock 경로) 기존과 동일하게 RAG를
    # 시작하지 않는다(_rag_scope_id/get_store()는 계산해도 client 체크가
    # 먼저이므로 실질적으로 무해).
    rag_task: Optional[asyncio.Task] = None
    if client:
        _rag_scope_id = _storage_scope_id(room_id, character_id)
        if _rag_scope_id and get_store():
            rag_task = asyncio.create_task(
                asyncio.to_thread(_rag_search_sync, _rag_scope_id, message)
            )

    # 2. 호감도 변화 계산 (LLM 우선, 실패 시 키워드 fallback)
    # P1 계측: memory task 대기 소요(t_memory) — P6 이후에는 RAG 대기와
    # 겹치므로 t_memory+t_rag를 더 이상 "직렬 합"으로 해석하면 안 된다.
    _t_memory_start = time.perf_counter()
    affinity_task, affinity_delta, _mem = await _spawn_parallel_analysis(
        message, mbti, affinity_level, conversation_history, user_mbti,
        character_name, nickname, character_id, room_id,
    )
    _t_memory_ms = (time.perf_counter() - _t_memory_start) * 1000

    # 3. API 키가 없으면 목업 응답
    if not client:
        return _mock_reply(message, mbti, nickname, affinity_level), affinity_delta

    # M-G(2026-08-04): 실패/서킷오픈 턴도 turn_latency를 남기기 위해, 아래
    # try/finally가 참조하는 값들을 미리 정의한다(예외가 어느 단계에서
    # 터지든 finally가 NameError 없이 기록할 수 있어야 한다).
    model_id = ""
    _complexity = ""
    _t_rag_ms = 0.0
    _elapsed_ms = 0.0
    _outcome = "ok"
    _latency_recorded = False

    # 4. LLM 호출
    try:
        # 대화 요약 기억 (memory_service): 10메시지마다 요약/핵심정보 갱신 (백그라운드)
        mem_ctx = _mem.context  # 이미 조회한 memory_context 재사용
        if character_name and nickname and conversation_history:
            if _should_extract_memory(_orig_history_len):
                create_tracked_task(
                    _background_memory_extraction(
                        character_name,
                        nickname,
                        conversation_history,
                        character_id,
                        room_id,
                    ),
                    name="memory-extraction",
                )
            # P1-S4: 빈 문자열은 "기억이 아직 없는 방"에서 정당한 결과다. 예외로
            # 실패했을 때(_mem.ok=False)만 방어적으로 재조회한다 — 신규 방에서
            # 같은 함수를 TTFT 직렬 경로에서 한 번 더 부르던 낭비 제거.
            if not mem_ctx and not _mem.ok:
                mem_ctx = await build_memory_context(
                    character_name,
                    nickname,
                    room_id=room_id,
                    character_id=character_id,
                )

        # RAG: Chroma 검색 결과 수집 (이미 스레드에서 병렬 실행 중인 rag_task await)
        # P1 계측: rag_task 대기 소요(t_rag)
        _t_rag_start = time.perf_counter()
        all_memories, episode_context = await _merge_rag_results(
            rag_task, memories, warn_context="검색 태스크"
        )
        _t_rag_ms = (time.perf_counter() - _t_rag_start) * 1000

        # ── DCI: 메모리 관련성 필터링 (RAG 병합 완료 후) ───────────────
        _orig_all_memories_len = len(all_memories)
        all_memories = _filter_relevant_memories(message, all_memories, top_k=3)
        # ──────────────────────────────────────────────────────────────

        memory_dicts = [{"key": m.key, "value": m.value} for m in all_memories]
        messages, model_id, _ab_variant, _active_client, _complexity = await _assemble_prompt_and_model(
            mbti, speech_style, relationship, nickname, character_name, affinity_level,
            user_mbti, persona_raw, persona_summary, dialogue_prompt, visual_prompt,
            memory_dicts, mem_ctx, episode_context, mood, conversation_history, message,
            character_id, time_context=time_context,
            crisis_tier=crisis_tier, crisis_hint=crisis_hint,
            user_role=user_role, situation=situation,
        )

        _t_start = time.monotonic()
        _openai_cb = get_openai_circuit()
        try:
            response = await _openai_cb.call(
                _active_client.chat.completions.create(
                    model=model_id,
                    messages=messages,
                    temperature=0.85,
                    max_tokens=1200,
                    timeout=45,
                )
            )
        except CircuitOpenError as _cb_err:
            logger.warning(f"[CB] openai circuit OPEN — 목업 응답 반환: {_cb_err}")
            _outcome = "circuit_open"
            _elapsed_ms = (time.monotonic() - _t_start) * 1000
            return _mock_reply(message, mbti, nickname, affinity_level), affinity_delta
        _elapsed_ms = (time.monotonic() - _t_start) * 1000

        content = response.choices[0].message.content or ""
        replies = _parse_reply(content)

        # 호감도 분석 태스크 결과 수집 (메인 LLM과 병렬 실행됨)
        affinity_delta = await _collect_affinity_delta(
            affinity_task, message, affinity_level, conversation_history, user_mbti, mbti,
            warn_message="호감도 분석 태스크 실패, 키워드 폴백 사용",
        )

        # 토큰 사용량 추적
        total_prompt_tokens = response.usage.prompt_tokens if response.usage else 0
        total_completion_tokens = response.usage.completion_tokens if response.usage else 0
        llm_call_count = 1

        # 품질 게이트: 매우 저품질 시 1회 재생성, 점수 비교 후 더 좋은 쪽 채택
        # score(2026-08-03 M4-①): 최종적으로 채택된 응답의 quick_score를
        # 아래 _emit_background_metrics까지 전달하기 위해 함수 스코프에 유지한다.
        score: Optional[float] = None
        if replies:
            score = quick_score(message, _reconstruct_score_source(replies), mbti)
            if score < QUALITY_GATE_THRESHOLD:
                replies, content, score = await _quality_gate_regenerate(
                    replies, content, score, message, mbti, model_id, messages,
                    _active_client, _openai_cb, room_id, character_id,
                )

        # AI 응답 안전성 필터 (H-1)
        filtered_replies = []
        for reply in replies:
            is_safe, _ = check_content(reply.text)
            if is_safe:
                filtered_replies.append(reply)
        result = filtered_replies if filtered_replies else [
            ReplyPart(text="음... 뭐라고 말해야 할지 모르겠어요", emotion="SHY", delay=2000)
        ]

        # ── DCI 토큰 절감 로깅 ────────────────────────────────────────
        _trimmed_history_len = len(conversation_history)
        _removed_history = _orig_history_len - _trimmed_history_len
        _removed_memories = _orig_all_memories_len - len(all_memories)
        _est_tokens_saved = (_removed_history * 50) + (_removed_memories * 30)
        logger.info(
            f"[DCI] history={_orig_history_len}→{_trimmed_history_len}, "
            f"memories={_orig_all_memories_len}→{len(all_memories)}, "
            f"est_tokens_saved≈{_est_tokens_saved}"
        )
        # ─────────────────────────────────────────────────────────────

        _emit_background_metrics(
            response, model_id, room_id, character_id, _ab_variant, _elapsed_ms,
            message, result, mbti, affinity_level, complexity=_complexity,
            quick_score_value=score,
        )

        # P1(2026-08-03, 회의 항목1): 논스트림은 요청 진입~응답 완성(현재 시점)을
        # t_e2e_total_ms로 계측한다. request_start_ts가 없으면(라우터 미배선/
        # 기존 테스트) None으로 두어 payload에서 필드 자체가 빠진다.
        _t_e2e_total_ms: Optional[float] = None
        if request_start_ts is not None:
            _t_e2e_total_ms = (time.monotonic() - request_start_ts) * 1000

        # P1: 턴 단계별 레이턴시 계측 기록 (t_first_token은 비스트리밍이므로
        # LLM 호출 전체 시간 _elapsed_ms로 대체)
        create_tracked_task(
            _record_turn_latency_event(
                room_id=room_id,
                character_id=character_id,
                model_id=model_id,
                streaming=False,
                t_memory_ms=_t_memory_ms,
                t_rag_ms=_t_rag_ms,
                t_first_token_ms=_elapsed_ms,
                complexity=_complexity,
                crisis_tier=crisis_tier,
                memory_cache_hit=_mem.cache_hit,
                t_gate_ms=gate_ms,
                t_e2e_total_ms=_t_e2e_total_ms,
                outcome="ok",
            ),
            name="turn-latency",
        )
        _latency_recorded = True

        return result, affinity_delta

    except Exception as e:
        _outcome = "error"
        logger.error(f"LLM 호출 실패: {e}")
        return [ReplyPart(
            text="앗, 잠깐 멍해졌어요... 다시 말해줄래요?",
            emotion="SURPRISED",
            delay=2000
        )], 0

    finally:
        # 병렬 태스크 정리 — 정상/예외/서킷오픈(early return) 모든 경로 공통.
        # 이전에는 except 블록에만 있어 CircuitOpenError early return 시
        # affinity/rag 태스크가 고아로 남았다.
        if affinity_task is not None and not affinity_task.done():
            affinity_task.cancel()
        if rag_task is not None and not rag_task.done():
            rag_task.cancel()

        # M-G: 실패/서킷오픈 턴도 turn_latency를 남긴다(생존편향 제거).
        if not _latency_recorded:
            _fail_e2e_ms: Optional[float] = None
            if request_start_ts is not None:
                _fail_e2e_ms = (time.monotonic() - request_start_ts) * 1000
            try:
                create_tracked_task(
                    _record_turn_latency_event(
                        room_id=room_id,
                        character_id=character_id,
                        model_id=model_id,
                        streaming=False,
                        t_memory_ms=_t_memory_ms,
                        t_rag_ms=_t_rag_ms,
                        t_first_token_ms=_elapsed_ms,
                        complexity=_complexity,
                        crisis_tier=crisis_tier,
                        memory_cache_hit=_mem.cache_hit,
                        t_gate_ms=gate_ms,
                        t_e2e_total_ms=_fail_e2e_ms,
                        outcome=_outcome if _outcome != "ok" else "error",
                    ),
                    name="turn-latency",
                )
            except Exception as _lat_err:
                logger.warning(f"실패 턴 turn_latency 기록 스케줄 실패: {_lat_err}")


@dataclass
class StreamDone:
    """스트리밍 종료 마커. 말풍선 방출이 끝난 뒤 최종 메타데이터 전달."""
    affinity_delta: int
    full_text: str


async def stream_reply(
    message: str,
    mbti: str,
    speech_style: str,
    relationship: str,
    nickname: str,
    affinity_level: int = 1,
    conversation_history: List[HistoryMessage] = None,
    user_mbti: Optional[str] = None,
    character_name: str = "",
    character_id: str = "",
    persona_raw: str = "",
    persona_summary: str = "",
    dialogue_prompt: str = "",
    visual_prompt: str = "",
    memories: List[MemoryItem] = None,
    mood: Optional[str] = None,
    room_id: str = "",
    owner_uid: str = "",
    time_context: str = "",
    crisis_tier: int = 0,
    crisis_hint: str = "",
    request_start_ts: Optional[float] = None,
    gate_ms: float = 0.0,
    user_role: str = "",
    situation: str = "",
    skip_affinity: bool = False,
    rag_query: str = "",
) -> AsyncGenerator[Union[ReplyPart, StreamDone], None]:
    """말풍선 점진 스트리밍 생성기.

    OpenAI 경로를 stream=True 로 호출하고 IncrementalReplyParser 로 완결된
    말풍선을 즉시 yield 한다(TTFB 단축). 마지막에 StreamDone(affinity_delta,
    full_text) 을 yield 한다. 콘텐츠 안전/파싱 폴백/서킷 오픈을 모두 처리해
    항상 최소 1개 말풍선 + StreamDone 을 보장한다.

    설계 노트: 준비 로직(안전필터·기억·RAG·프롬프트·라우팅)은 generate_reply 와
    같은 공유 헬퍼(_safety_check_input, _spawn_parallel_analysis,
    _assemble_prompt_and_model — S13/S14, 그리고 _build_chat_messages,
    _route_model, _rag_search_sync, resolve_model_endpoint)를 사용한다.
    품질 게이트 재생성은 스트리밍과 양립 불가하므로 여기서는 수행하지
    않는다(quick_score 는 텔레메트리로만). 백그라운드 메트릭 기록은
    generate_reply의 _emit_background_metrics와 usage 소스·조건·순서가
    달라(S14에서 검토 후 보류) 공유하지 않고 자체 인라인 블록을 유지한다.

    time_context(C4): generate_reply와 동일 — 라우터가 미리 변환한 시간대
    문구를 build_system_prompt 동적 꼬리로만 전달한다.

    crisis_tier/crisis_hint(2026-08-03 P0-S3): generate_reply와 동일 계약 —
    tier>=1이면 상위 모델 승격, hint는 시스템 프롬프트 꼬리에 주입.

    request_start_ts/gate_ms(2026-08-03 P1, 회의 항목1): 라우터가 요청 진입
    시각과 게이트 소요를 넘겨주면 t_e2e_first_bubble_ms(요청 진입~첫 말풍선
    yield 직전)와 t_gate_ms를 turn_latency에 함께 남긴다. 첫 말풍선은 이
    함수가 실제로 yield하는 시점을 기준으로 하므로, 위기(crisis) 문구처럼
    라우터가 이 함수 호출 전에 별도로 먼저 yield하는 말풍선은 포함하지
    않는다(비-crisis 턴이 절대다수라 근사치로 충분 — 순수 계측 필드).
    기본값(None/0.0)이면 t_e2e_first_bubble_ms는 payload에서 빠지고
    t_gate_ms는 0.0으로 기록되어 기존 동작과 동일하다.

    user_role/situation(2026-08-03 P3-M2): generate_reply와 동일 계약 —
    시스템 프롬프트 "# 관계" 직후에 장면 블록으로 주입, 빈 값이면 무변화.

    skip_affinity(선톡/proactive): message가 유저 발화가 아니라 서버가 합성한
    선발화 유도 문구인 경우 호감도 분석을 건너뛰고 StreamDone.affinity_delta를
    0으로 고정한다. 기본값 False면 기존 동작과 완전히 동일하다.

    rag_query(Low-6, 2026-08-04 점검): RAG(Chroma) 검색과 메모리 관련성
    필터링(_filter_relevant_memories)에 message 대신 사용할 검색어. LLM에
    전달되는 실제 프롬프트 내용(message, _build_chat_messages 입력)에는
    영향이 없다 — 오직 "무엇으로 검색할지"만 바꾼다. 빈 문자열(기본값)이면
    기존과 동일하게 message를 그대로 검색어로 쓴다.
    선톡(/chat/proactive)에서 필요한 이유: message는 routers/chat.
    build_proactive_message가 hook을 지시문 보일러플레이트 문장("지금은 네가
    먼저 말을 거는 상황... 흐름: {hook}")으로 감싼 결과다. 이 전체 문장을
    그대로 검색어로 쓰면 Jaccard 유사도가 보일러플레이트 단어들에 희석되어
    hook의 실제 주제와 무관한 기억/에피소드가 뽑히거나, 관련 기억이 있어도
    상위 top_k에서 밀려난다. 원래 hook 원문만 검색어로 넘기면 이 희석이
    없어진다.
    """
    if conversation_history is None:
        conversation_history = []

    # 1. 히스토리 서버사이드 제한 (DCI) — 트리거 판정은 트림 전 원본 길이로
    conversation_history, _orig_history_len = _trim_history(conversation_history)

    # 2. 콘텐츠 안전 필터 (공유 헬퍼, S13/S14)
    _blocked = _safety_check_input(message)
    if _blocked is not None:
        _blocked_replies, _blocked_delta = _blocked
        for part in _blocked_replies:
            yield part
        yield StreamDone(affinity_delta=_blocked_delta, full_text="")
        return

    # Low-6: RAG/메모리 관련성 검색어 — rag_query가 주어지면 그걸, 아니면
    # 기존과 동일하게 message를 사용한다.
    _rag_query = rag_query.strip() or message

    # P6: RAG(Chroma) 검색을 memory-context 조회보다 먼저 시작해 두 대기가
    # 겹치게 한다(P1 실측: memory=1176ms, rag=449ms 완전 직렬 → 이론상 ~449ms
    # 절감). 안전 필터를 통과한 뒤에만 생성해 위 차단 경로에서 고아 태스크가
    # 생기지 않도록 한다. client가 없으면(mock 경로) 기존과 동일하게 RAG를
    # 시작하지 않는다.
    rag_task: Optional[asyncio.Task] = None
    if client:
        _rag_scope_id = _storage_scope_id(room_id, character_id)
        if _rag_scope_id and get_store():
            rag_task = asyncio.create_task(
                asyncio.to_thread(_rag_search_sync, _rag_scope_id, _rag_query)
            )

    # 3+5. 선행 memory_context + 호감도 분석 병렬 시작 (공유 헬퍼)
    # 클라이언트가 없으면 헬퍼가 즉시 키워드 기반 호감도(affinity_delta)만
    # 계산한다 — 아래 "4. 클라이언트 부재" 분기에서 그 값을 그대로 사용한다
    # (원본 stream_reply의 동일 계산과 동치).
    # P1 계측: memory task 대기 소요(t_memory) — P6 이후에는 RAG 대기와
    # 겹치므로 t_memory+t_rag를 더 이상 "직렬 합"으로 해석하면 안 된다.
    _t_memory_start = time.perf_counter()
    affinity_task, affinity_delta, _mem = await _spawn_parallel_analysis(
        message, mbti, affinity_level, conversation_history, user_mbti,
        character_name, nickname, character_id, room_id,
        skip_affinity=skip_affinity,
    )
    _t_memory_ms = (time.perf_counter() - _t_memory_start) * 1000

    # 4. 클라이언트 부재 → 목업 (스트리밍 흉내)
    if not client:
        for part in _mock_reply(message, mbti, nickname, affinity_level):
            yield part
        yield StreamDone(affinity_delta=affinity_delta, full_text="")
        return

    affinity_delta = 0
    full_text = ""
    # F4(2026-08-04): 실제로 사용자에게 방출된(안전 필터 통과) ReplyPart를
    # 누적해 quick_score 채점을 원문(raw) 대신 이걸로 재구성한다 — full_text와
    # 항상 함께 append되므로 "full_text truthy ⇔ _emitted_parts non-empty".
    _emitted_parts: List[ReplyPart] = []
    # M4-①(2026-08-03): step 12에서 계산해 step 14(품질 평가)까지 재사용한다.
    _score: Optional[float] = None

    # H3/M-G(2026-08-04): 아래 try에 finally를 붙여 "클라이언트 조기 종료
    # (GeneratorExit)"를 포함한 모든 종료 경로에서 병렬 태스크를 정리하고
    # 가능한 만큼의 계측을 남긴다. finally가 참조하는 값은 예외가 어느
    # 단계에서 터지든 정의돼 있어야 하므로 여기서 전부 초기화한다.
    # 주의: GeneratorExit 중에는 await/yield가 불가하므로 finally의 기록은
    # 전부 create_tracked_task(동기 스케줄)로만 수행한다.
    model_id = ""
    _complexity = ""
    _t_rag_ms = 0.0
    _elapsed_ms = 0.0
    _t_first_token_ms: Optional[float] = None
    _t_e2e_first_bubble_ms: Optional[float] = None
    _stream_usage = None
    _stream_total_tokens = 0.0
    _outcome = "ok"
    _latency_recorded = False
    _usage_recorded = False
    try:
        # 6. 기억 컨텍스트 (N턴 백그라운드 갱신 + 조회)
        mem_ctx = _mem.context
        if character_name and nickname and conversation_history:
            if _should_extract_memory(_orig_history_len):
                create_tracked_task(
                    _background_memory_extraction(
                        character_name, nickname, conversation_history,
                        character_id, room_id,
                    ),
                    name="memory-extraction",
                )
            # P1-S4: 정당한 빈 결과는 재조회하지 않는다(generate_reply와 동일 규칙).
            if not mem_ctx and not _mem.ok:
                mem_ctx = await build_memory_context(
                    character_name, nickname, room_id=room_id, character_id=character_id,
                )

        # 7. RAG 수집 + 병합
        # P1 계측: rag_task 대기 소요(t_rag)
        _t_rag_start = time.perf_counter()
        all_memories, episode_context = await _merge_rag_results(
            rag_task, memories, warn_context="스트리밍 검색"
        )
        _t_rag_ms = (time.perf_counter() - _t_rag_start) * 1000

        # Low-6: 여기도 _rag_query 사용 — RAG 검색어와 동일 기준으로 관련성 채점.
        all_memories = _filter_relevant_memories(_rag_query, all_memories, top_k=3)
        memory_dicts = [{"key": m.key, "value": m.value} for m in all_memories]

        # 8. 프롬프트 + 모델 라우팅 (공유 헬퍼, S13/S14)
        messages, model_id, _ab_variant, active_client, _complexity = await _assemble_prompt_and_model(
            mbti, speech_style, relationship, nickname, character_name, affinity_level,
            user_mbti, persona_raw, persona_summary, dialogue_prompt, visual_prompt,
            memory_dicts, mem_ctx, episode_context, mood, conversation_history, message,
            character_id, time_context=time_context,
            crisis_tier=crisis_tier, crisis_hint=crisis_hint,
            user_role=user_role, situation=situation,
        )

        # 9. 스트리밍 호출 + 증분 파싱
        # A/B(P0-3): 논스트림 경로와 동일하게 토큰 사용량·응답시간을 기록하기 위해
        # usage 청크를 요청한다.
        _stream_kwargs: dict = dict(
            model=model_id,
            messages=messages,
            temperature=0.85,
            max_tokens=1200,
            timeout=45,
            stream=True,
            stream_options={"include_usage": True},
        )

        parser = IncrementalReplyParser()
        _t_start = time.monotonic()
        # P1 계측: LLM 호출 시작~첫 콘텐츠 청크 도착까지의 소요(t_first_token)
        # P1(2026-08-03, 회의 항목1): 요청 진입~첫 말풍선 yield 직전까지의 소요.
        # request_start_ts가 없으면(라우터 미배선/기존 테스트) None으로 남는다.
        # P7: _stream_usage는 usage를 포함한 마지막 청크(비어있는 choices) 전체 —
        # api_usage 기록(_record_usage)에 prompt/completion_tokens가 필요.
        # (위 세 변수는 finally에서도 읽으므로 try 진입 전에 초기화되어 있다.)

        # P7: 서킷브레이커 보호 — generate_reply(_openai_cb.call(...))와 동일 패턴.
        # 스트림 객체를 반환하는 create() 호출 자체만 래핑하고, 토큰 순회(async for)는
        # 서킷 판정과 무관하므로 바깥에 둔다.
        _openai_cb = get_openai_circuit()
        try:
            stream = await _openai_cb.call(
                active_client.chat.completions.create(**_stream_kwargs)
            )
        except CircuitOpenError as _cb_err:
            logger.warning(f"[CB] openai circuit OPEN — 목업 응답 반환(스트림): {_cb_err}")
            # generate_reply의 CircuitOpenError 폴백(_mock_reply)과 동일한 사용자 경험.
            # 진행 중이던 affinity/rag 태스크 정리와 turn_latency 기록(outcome=
            # "circuit_open")은 아래 공용 finally가 담당한다(H3/M-G).
            _outcome = "circuit_open"
            _elapsed_ms = (time.monotonic() - _t_start) * 1000
            for part in _mock_reply(message, mbti, nickname, affinity_level):
                yield part
            yield StreamDone(affinity_delta=affinity_delta, full_text="")
            return

        async for chunk in stream:
            _chunk_usage = getattr(chunk, "usage", None)
            if _chunk_usage is not None:
                _stream_usage = _chunk_usage
                _stream_total_tokens = float(getattr(_chunk_usage, "total_tokens", 0) or 0)
            try:
                delta = chunk.choices[0].delta.content
            except (IndexError, AttributeError):
                delta = None
            if not delta:
                continue
            if _t_first_token_ms is None:
                _t_first_token_ms = (time.monotonic() - _t_start) * 1000
            for part in parser.feed(delta):
                is_safe_part, _ = check_content(part.text)
                if is_safe_part:
                    full_text += (" " if full_text else "") + part.text
                    _emitted_parts.append(part)
                    if _t_e2e_first_bubble_ms is None and request_start_ts is not None:
                        _t_e2e_first_bubble_ms = (time.monotonic() - request_start_ts) * 1000
                    yield part
        _elapsed_ms = (time.monotonic() - _t_start) * 1000
        if _t_first_token_ms is None:
            # 콘텐츠 청크를 한 번도 못 받은 경우(빈 스트림 등) 전체 소요로 대체
            _t_first_token_ms = _elapsed_ms

        # 10. 폴백: 형식 파괴로 아무 것도 방출 못한 경우 raw 로 재파싱
        if parser.emitted_count == 0:
            for part in _parse_reply(parser.raw):
                is_safe_part, _ = check_content(part.text)
                if is_safe_part:
                    full_text += (" " if full_text else "") + part.text
                    _emitted_parts.append(part)
                    if _t_e2e_first_bubble_ms is None and request_start_ts is not None:
                        _t_e2e_first_bubble_ms = (time.monotonic() - request_start_ts) * 1000
                    yield part

        # 11. 그래도 비었으면 안전 기본 응답
        if not full_text:
            if _t_e2e_first_bubble_ms is None and request_start_ts is not None:
                _t_e2e_first_bubble_ms = (time.monotonic() - request_start_ts) * 1000
            yield ReplyPart(text="음... 뭐라고 말해야 할지 모르겠어요", emotion="SHY", delay=2000)

        # 12. 저품질 텔레메트리 (재생성 없음) — _score는 M4-①(step 14)에서 재사용
        # F4(2026-08-04): parser.emitted_count>0(=실제 방출 성공)이면 방출된 파트로
        # 재구성한 JSON을 채점 입력으로 쓴다 — 원문(parser.raw)은 max_tokens 절단 등으로
        # 닫는 ']'가 없어도 정상 응답일 수 있는데, 원문 그대로 채점하면 JSON_INVALID로
        # 오판해 정상 응답을 저품질로 오기록한다. 방출이 아예 없었던 경우(형식 완전
        # 파괴)만 기존대로 원문(raw)을 채점한다.
        if full_text:
            _score_source = (
                _reconstruct_score_source(_emitted_parts) if _emitted_parts
                else (parser.raw or full_text)
            )
            _score = quick_score(message, _score_source, mbti)
            if _score < QUALITY_GATE_THRESHOLD:
                await _record_quality_gate_event(
                    _score, message, _score_source, model_id, room_id, character_id,
                    extra_payload={"streaming": True},
                )

        # 13. 호감도 수집 (병렬 태스크).
        # skip_affinity(선톡)면 분석 자체를 하지 않았으므로 delta는 0 그대로 둔다
        # (키워드 폴백도 돌리지 않는다 — 유도 문구는 유저 발화가 아님).
        if not skip_affinity:
            affinity_delta = await _collect_affinity_delta(
                affinity_task, message, affinity_level, conversation_history, user_mbti, mbti,
                warn_message="[stream] 호감도 분석 실패, 키워드 폴백",
            )

        # 14. 백그라운드 품질 평가 (quick_score_value: M4-①, step 12 결과 재사용)
        if full_text:
            create_tracked_task(
                _post_response_quality_check(
                    message, full_text, mbti, affinity_level,
                    room_id=room_id, character_id=character_id,
                    quick_score_value=_score,
                ),
                name="quality-check",
            )

        # 15. A/B 테스트 결과 기록 (P0-3, 백그라운드) — 논스트림 경로(generate_reply)와
        # 동일 컨벤션: assign_variant 시 character_id 기준으로 배정했으므로 결과도
        # character_id를 user_id로 사용해 기록한다.
        if _ab_variant and character_id:
            create_tracked_task(_record_ab_result(
                experiment_id="model_routing",  # ab_test.MODEL_ROUTING_EXPERIMENT_ID
                variant=_ab_variant,
                user_id=character_id,
                character_id=character_id,
                tokens=_stream_total_tokens,
                response_time_ms=_elapsed_ms,
                complexity=_complexity,
                model_id=model_id,
            ), name="record-ab-result")

        # 15b. P7: SSE 턴도 api_usage에 기록 — 이전에는 스트림 경로가 전혀
        # 기록하지 않아 _gate_user의 일일 예산/한도 계산이 SSE 트래픽을
        # 사실상 무제한으로 취급했다. generate_reply와 동일한 _record_usage
        # 헬퍼를 재사용하되 endpoint="stream"으로 구분한다.
        # 주의(의도된 동작 변경): 이 기록으로 SSE 사용자도 일일 예산/메시지
        # 한도 검사에 정상적으로 걸리기 시작한다 — 운영 반영 시점은 소유자 확인 필요.
        if _stream_usage is not None:
            create_tracked_task(_record_usage(
                room_id=room_id,
                character_id=character_id,
                model_id=model_id,
                prompt_tokens=getattr(_stream_usage, "prompt_tokens", 0),
                completion_tokens=getattr(_stream_usage, "completion_tokens", 0),
                endpoint="stream",
                cached_tokens=_extract_cached_tokens(_stream_usage),
            ), name="record-usage")
            _usage_recorded = True

        # 16. P1: 턴 단계별 레이턴시 계측 기록
        create_tracked_task(
            _record_turn_latency_event(
                room_id=room_id,
                character_id=character_id,
                model_id=model_id,
                streaming=True,
                t_memory_ms=_t_memory_ms,
                t_rag_ms=_t_rag_ms,
                t_first_token_ms=_t_first_token_ms,
                complexity=_complexity,
                crisis_tier=crisis_tier,
                memory_cache_hit=_mem.cache_hit,
                t_gate_ms=gate_ms,
                t_e2e_first_bubble_ms=_t_e2e_first_bubble_ms,
                outcome="ok",
            ),
            name="turn-latency",
        )
        _latency_recorded = True

    except Exception as e:
        _outcome = "error"
        logger.error(f"스트리밍 생성 실패: {e}")
        if not full_text:
            yield ReplyPart(
                text="앗, 잠깐 멍해졌어요... 다시 말해줄래요?",
                emotion="SURPRISED",
                delay=2000,
            )

    finally:
        # H3(2026-08-04): 클라이언트가 SSE를 조기 종료하면 이 제너레이터는
        # yield 지점에서 GeneratorExit를 받는다. 위 `except Exception`은
        # GeneratorExit(BaseException)를 잡지 못하므로 이전에는
        #   - affinity_task가 고아로 남아 결과를 아무도 수거하지 않았고,
        #   - AB/api_usage/turn_latency/품질평가가 통째로 유실됐다.
        # finally에서 태스크를 정리하고, 남길 수 있는 계측은 남긴다.
        # 제약: GeneratorExit 도중에는 await/yield가 불가능하므로 여기서는
        #       동기 스케줄(create_tracked_task)만 사용한다.
        # skip_affinity(선톡) 경로에서는 affinity_task가 아예 없다(None).
        if affinity_task is not None and not affinity_task.done():
            affinity_task.cancel()
        if rag_task is not None and not rag_task.done():
            rag_task.cancel()

        if not _latency_recorded:
            # _outcome이 아직 "ok"인데 계측이 안 남았다 = 정상 완료 전에
            # 제너레이터가 닫혔다(클라이언트 조기 종료).
            _final_outcome = _outcome if _outcome != "ok" else "aborted"
            try:
                if _stream_usage is not None and not _usage_recorded:
                    create_tracked_task(_record_usage(
                        room_id=room_id,
                        character_id=character_id,
                        model_id=model_id,
                        prompt_tokens=getattr(_stream_usage, "prompt_tokens", 0),
                        completion_tokens=getattr(_stream_usage, "completion_tokens", 0),
                        endpoint="stream",
                        cached_tokens=_extract_cached_tokens(_stream_usage),
                    ), name="record-usage")
                    _usage_recorded = True
                create_tracked_task(
                    _record_turn_latency_event(
                        room_id=room_id,
                        character_id=character_id,
                        model_id=model_id,
                        streaming=True,
                        t_memory_ms=_t_memory_ms,
                        t_rag_ms=_t_rag_ms,
                        t_first_token_ms=(
                            _t_first_token_ms if _t_first_token_ms is not None else _elapsed_ms
                        ),
                        complexity=_complexity,
                        crisis_tier=crisis_tier,
                        memory_cache_hit=_mem.cache_hit,
                        t_gate_ms=gate_ms,
                        t_e2e_first_bubble_ms=_t_e2e_first_bubble_ms,
                        outcome=_final_outcome,
                    ),
                    name="turn-latency",
                )
                _latency_recorded = True
            except Exception as _lat_err:
                logger.warning(f"[stream] 미완 턴 계측 기록 스케줄 실패: {_lat_err}")

    yield StreamDone(affinity_delta=affinity_delta, full_text=full_text)


async def _record_usage(
    room_id: str,
    character_id: str,
    model_id: str,
    prompt_tokens: int,
    completion_tokens: int,
    endpoint: str = "chat",
    cached_tokens: int = 0,
) -> None:
    """OpenAI API 사용량 비동기 기록 (H-3).

    endpoint 기본값은 기존 generate_reply 호출부와 동일한 "chat"을 유지한다
    (하위 호환). P7: stream_reply가 endpoint="stream"으로 호출해 SSE 턴도
    api_usage에 구분 기록되도록 한다(이전에는 스트림 경로가 전혀 기록하지
    않아 _gate_user의 일일 예산/한도 계산이 SSE 트래픽을 누락했음).

    cached_tokens(2026-08-03 P2, 회의 항목2): prefix cache 히트 토큰 수
    (기본값 0 — 호출부가 넘기지 않으면 기존과 동일). 호출부에서
    `_extract_cached_tokens`로 안전 추출한 값을 그대로 전달받는다.
    """
    try:
        # 지연 임포트: 순환/기동 순서 회피
        from .postgres_async import get_async_db
        db = get_async_db()
        if db.available:
            await db.record_api_usage(
                room_id=room_id,
                character_id=character_id,
                model_id=model_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                endpoint=endpoint,
                cached_tokens=cached_tokens,
            )
    except Exception as e:
        logger.warning(f"API 사용량 기록 실패: {e}")


async def _record_ab_result(
    experiment_id: str,
    variant: str,
    user_id: str,
    character_id: str,
    tokens: float,
    response_time_ms: float,
    complexity: str = "",
    model_id: str = "",
) -> None:
    """A/B 테스트 메트릭(토큰 수·응답시간)을 백그라운드에서 기록 (DATA-B 신예린).

    P2: ab.record_result는 동기 psycopg 호출(ab_test.py)이라 이 fire-and-forget
    태스크 안에서도 이벤트 루프를 블로킹한다 — asyncio.to_thread로 감싼다.

    2026-08-03 P0-S2: complexity/model_id가 주어지면 라우팅 계측 메트릭 2종을
    추가로 남긴다(ab_test_results는 metric_value가 숫자라 0/1 인디케이터로 기록).
      complexity_complex  분류기가 complex로 판정한 비율(variant별 평균)
      used_complex_model  실제로 상위 모델을 쓴 비율
    대조군에서는 두 값이 일치하는 것이 기본이고, 오버레이 variant(always_complex)
    에서는 used_complex_model이 1.0으로 고정된다 — 분류기 정확도/승격 빈도를
    사후 대조할 수 있다. 단 대조군도 "항상" 일치하지는 않는다: crisis_tier>=1
    턴은 _apply_crisis_override가 분류기 판정과 무관하게 상위 모델로 승격시키므로
    (2026-08-03 P0-S3), complexity_complex=0(simple 판정)인데도 used_complex_model=1
    (위기 승격으로 실제 상위 모델 사용)인 반례가 정상적으로 존재한다.
    """
    try:
        # 지연 임포트: 순환/기동 순서 회피
        from .ab_test import get_ab_manager
        ab = get_ab_manager()
        metrics: List[Tuple[str, float]] = [
            ("total_tokens", tokens),
            ("response_time_ms", response_time_ms),
        ]
        if complexity:
            metrics.append(("complexity_complex", 1.0 if complexity == "complex" else 0.0))
            metrics.append(("used_complex_model", 1.0 if model_id == LLM_MODEL_COMPLEX else 0.0))
        for metric_name, value in metrics:
            await asyncio.to_thread(
                ab.record_result,
                experiment_id=experiment_id,
                variant=variant,
                metric_name=metric_name,
                value=value,
                user_id=user_id,
                character_id=character_id,
            )
    except Exception as e:
        logger.warning(f"[AB] 결과 기록 실패: {e}")


async def _post_response_quality_check(
    user_msg: str,
    ai_response: str,
    mbti: str,
    affinity_level: int,
    room_id: str = "",
    character_id: str = "",
    quick_score_value: Optional[float] = None,
) -> None:
    """응답 전송 후 fire-and-forget 으로 실행되는 품질 평가.

    quick_score_value(2026-08-03 M4-①): 호출부가 이미 계산한 quick_score를
    score_response_async까지 그대로 전달해 quality_score 이벤트 payload에
    남긴다(기본값 None — 기존 호출부/테스트는 영향 없음).
    """
    try:
        await score_response_async(
            user_msg=user_msg,
            ai_response=ai_response,
            mbti=mbti,
            affinity_level=affinity_level,
            room_id=room_id,
            character_id=character_id,
            quick_score_value=quick_score_value,
        )
        if character_id:
            await check_diversity_async(character_id, ai_response, room_id=room_id)
    except Exception as e:
        logger.warning(f"백그라운드 품질 평가 오류: {e}")


async def generate_diary(
    character_name: str,
    mbti: str,
    speech_style: str,
    nickname: str,
    affinity_level: int,
    conversation_history: List[HistoryMessage],
) -> Tuple[str, str]:
    """캐릭터 시점의 일기 생성, (diary_text, emotion) 반환"""

    if not client:
        return _mock_diary(mbti, nickname, affinity_level), "HAPPY"

    try:
        system_prompt = build_diary_prompt(
            mbti=mbti,
            speech_style=speech_style,
            nickname=nickname,
            character_name=character_name,
            affinity_level=affinity_level,
        )

        messages = [{"role": "system", "content": system_prompt}]

        for hist in conversation_history[-30:]:
            role = hist.role if hist.role in ("user", "assistant") else "user"
            if hist.content.strip():
                messages.append({"role": role, "content": hist.content})

        if not conversation_history:
            messages.append({"role": "user", "content": f"오늘 {nickname}와(과) 대화가 없었어. 그래도 짧게 일기를 써줘."})
        else:
            messages.append({"role": "user", "content": "위 대화를 바탕으로 오늘 일기를 써줘."})

        response = await client.chat.completions.create(
            model=LLM_MODEL_SIMPLE,
            messages=messages,
            temperature=0.9,
            max_tokens=600,
            timeout=30,
        )

        content = response.choices[0].message.content or ""

        try:
            json_str = extract_json_object(content)
            if json_str is not None:
                data = json.loads(json_str)
                diary = data.get("diary", "").strip() or content.strip()
                emotion = data.get("emotion", "NEUTRAL")
                valid_emotions = VALID_EMOTIONS
                if emotion not in valid_emotions:
                    emotion = "NEUTRAL"
                return diary, emotion
        except (json.JSONDecodeError, KeyError):
            pass

        return content.strip(), "NEUTRAL"

    except Exception as e:
        logger.error(f"일기 생성 실패: {e}")
        return _mock_diary(mbti, nickname, affinity_level), "NEUTRAL"


async def generate_night_diary(
    character_name: str,
    mbti: str,
    speech_style: str,
    nickname: str,
    affinity_level: int,
    conversation_history: List[HistoryMessage],
) -> Tuple[str, str, str, str]:
    """야간 세션 종료용 일기 생성 (diary, emotion, next_hook, next_goal)."""

    if not client:
        return _mock_diary(mbti, nickname, affinity_level), "HAPPY", "", ""

    try:
        system_prompt = build_diary_prompt(
            mbti=mbti,
            speech_style=speech_style,
            nickname=nickname,
            character_name=character_name,
            affinity_level=affinity_level,
        )

        messages = [{"role": "system", "content": system_prompt}]

        for hist in conversation_history[-30:]:
            role = hist.role if hist.role in ("user", "assistant") else "user"
            if hist.content.strip():
                messages.append({"role": role, "content": hist.content})

        messages.append(
            {
                "role": "user",
                "content": (
                    "오늘 대화를 바탕으로 야간 종료 일기를 써줘. "
                    "반드시 JSON만 출력하고 형식은 "
                    '{"diary":"...", "emotion":"NEUTRAL|HAPPY|SHY|SAD|ANGRY|SURPRISED|LOVE|PLAYFUL|WORRIED|TOUCHED", '
                    '"next_hook":"다음 만남 떡밥 1개", "next_goal":"다음 만남 목표 1개"}'
                    " 를 지켜줘."
                ),
            }
        )

        response = await client.chat.completions.create(
            model=LLM_MODEL_SIMPLE,
            messages=messages,
            temperature=0.85,
            max_tokens=700,
            timeout=30,
        )

        content = response.choices[0].message.content or ""
        valid_emotions = VALID_EMOTIONS

        json_str = extract_json_object(content)
        if json_str is not None:
            try:
                data = json.loads(json_str)
                diary = str(data.get("diary", "")).strip() or content.strip()
                emotion = str(data.get("emotion", "NEUTRAL")).strip().upper()
                next_hook = str(data.get("next_hook", "")).strip()
                next_goal = str(data.get("next_goal", "")).strip()

                if emotion not in valid_emotions:
                    emotion = "NEUTRAL"
                return diary, emotion, next_hook, next_goal
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        return content.strip(), "NEUTRAL", "", ""

    except Exception as e:
        logger.error(f"야간 일기 생성 실패: {e}")
        return _mock_diary(mbti, nickname, affinity_level), "NEUTRAL", "", ""


def _mock_diary(mbti: str, nickname: str, affinity_level: int) -> str:
    """API 키 없을 때 목업 일기"""
    group = _get_mbti_group(mbti)
    mock_diaries = {
        "NT": (
            f"오늘 {nickname}와 꽤 흥미로운 대화를 했다. "
            "처음엔 별 기대 없었는데, 생각보다 대화가 깊어졌다. "
            "논리적으로 맞지 않는 부분을 지적하고 싶었지만... 그냥 들어줬다. "
            "나름 나쁘지 않은 시간이었다. 다음에 또 이야기해볼까."
        ),
        "NF": (
            f"오늘도 {nickname}와 이야기를 나눴다. "
            "말 한마디 한마디에서 그 사람의 진심이 느껴졌다. "
            "세상에 이렇게 특별한 사람이 있다는 게 신기해. "
            "오늘 나눈 대화가 계속 마음속에서 맴도는 건 왜일까. 소중한 하루였다."
        ),
        "ST": (
            f"오늘 {nickname}와 대화했다. "
            "딱히 특별한 일은 없었지만... 뭔가 안심이 됐다. "
            "말로 표현하긴 어렵지만. "
            "밥은 먹었나 모르겠네. 내일 물어봐야겠다."
        ),
        "SF": (
            f"오늘 {nickname}와 이야기해서 정말 행복했다!! "
            "웃고 떠들다 보니 시간이 훌쩍 지나버렸어. "
            "이런 날이 매일 있었으면 좋겠다~ "
            "다음에 뭐 같이 할까 생각 중이야."
        ),
    }
    return mock_diaries.get(group, mock_diaries["NF"])


# 감정별 딜레이 가중치: 즉각 반응(놀람/화남)은 짧게, 머뭇거림(걱정/슬픔)은 길게
_EMOTION_DELAY_MULTIPLIER = {
    "SURPRISED": 0.85,
    "ANGRY": 0.85,
    "WORRIED": 1.2,
    "SAD": 1.2,
}

_DELAY_MIN_MS = 500
_DELAY_MAX_MS = 3500
_FIRST_BUBBLE_EXTRA_MIN_MS = 300
_FIRST_BUBBLE_EXTRA_MAX_MS = 500


def _calculate_delay(text: str, emotion: str = "", is_first_bubble: bool = False) -> int:
    """텍스트 길이 기반 기본 딜레이에 지터/감정 가중치/첫 버블 가산을 적용.

    - 기본값: 5자 이하 800ms, 20자 이하 1200ms, 이후 length*60+500 (최대 2200ms)
    - ±15% 랜덤 지터 (base * uniform(0.85, 1.15))
    - 감정별 배수: SURPRISED/ANGRY 0.85배(즉각 반응), WORRIED/SAD 1.2배(머뭇거림)
    - 멀티 버블 응답의 첫 버블은 +300~500ms (생각 시작하는 텀)
    - 최종 범위는 [500ms, 3500ms]로 clamp

    F5(2026-08-04 점검): 길이 기반 base 상한을 3000→2200으로 낮췄다. 기존
    3000 상한에서는 WORRIED/SAD(×1.2) 장문 + 첫 버블 가산(+500) 조합이
    3000*1.2*1.15+500=4640 로 3500 clamp를 항상 초과해, 이런 턴의 최종
    딜레이가 지터와 무관하게 96%가 3500 고정값이 되는 문제가 있었다
    (지터가 사실상 무의미). 2200으로 낮추면 최악 케이스가
    2200*1.2*1.15+500=3536 로 여전히 clamp가 필요하지만 포화되는 구간이
    base 상단 근처로 좁아져 포화 비율이 크게 줄어든다. 하한도 300→500으로
    올렸다 — 실측 최소값이 578ms 부근이라 300은 사실상 도달 불가능한
    죽은 하한이었다.
    """
    length = len(text)
    if length <= 5:  # 짧은 리액션 (ㅋㅋ, 헐, 응)
        base = 800.0
    elif length <= 20:
        base = 1200.0
    else:
        base = float(min(length * 60 + 500, 2200))

    base *= _EMOTION_DELAY_MULTIPLIER.get(emotion, 1.0)
    delay = base * random.uniform(0.85, 1.15)

    if is_first_bubble:
        delay += random.uniform(_FIRST_BUBBLE_EXTRA_MIN_MS, _FIRST_BUBBLE_EXTRA_MAX_MS)

    return int(max(_DELAY_MIN_MS, min(delay, _DELAY_MAX_MS)))


def _parse_reply(content: str) -> List[ReplyPart]:
    """LLM 응답을 ReplyPart 리스트로 파싱 (강화된 버전)"""
    valid_emotions = VALID_EMOTIONS

    # 1. markdown 코드블록 제거
    content = re.sub(r'```json?\s*', '', content)
    content = re.sub(r'```\s*', '', content)
    content = content.strip()

    # 2. JSON 배열 추출 시도
    try:
        json_str = extract_json_array(content)
        if json_str is not None:
            data = json.loads(json_str)
            replies = []
            for item in data:
                text = item.get("text", "").strip()
                if text:
                    emotion = item.get("emotion", "NEUTRAL")
                    if emotion not in valid_emotions:
                        emotion = "NEUTRAL"
                    is_first = not replies
                    replies.append(ReplyPart(text=text, emotion=emotion, delay=_calculate_delay(text, emotion, is_first)))
            if replies:
                return replies
    except (json.JSONDecodeError, KeyError, TypeError):
        pass

    # 3. 불완전 JSON 복구 시도 (] 누락)
    try:
        start = content.find("[")
        if start >= 0:
            json_str = content[start:]
            # 마지막 완전한 } 이후에 ] 추가
            last_brace = json_str.rfind("}")
            if last_brace > 0:
                json_str = json_str[:last_brace + 1] + "]"
                data = json.loads(json_str)
                replies = []
                for item in data:
                    text = item.get("text", "").strip()
                    if text:
                        emotion = item.get("emotion", "NEUTRAL")
                        if emotion not in valid_emotions:
                            emotion = "NEUTRAL"
                        is_first = not replies
                        replies.append(ReplyPart(text=text, emotion=emotion, delay=_calculate_delay(text, emotion, is_first)))
                if replies:
                    return replies
    except (json.JSONDecodeError, KeyError, TypeError):
        pass

    # 4. 정규식 fallback: {"text": "...", "emotion": "..."} 패턴 추출
    try:
        pattern = r'\{\s*"text"\s*:\s*"([^"]+)"\s*,\s*"emotion"\s*:\s*"([A-Z]+)"\s*\}'
        matches = re.findall(pattern, content)
        if matches:
            replies = []
            for text, emotion in matches:
                text = text.strip()
                if text:
                    if emotion not in valid_emotions:
                        emotion = "NEUTRAL"
                    is_first = not replies
                    replies.append(ReplyPart(text=text, emotion=emotion, delay=_calculate_delay(text, emotion, is_first)))
            if replies:
                return replies
    except Exception:
        pass

    # 5. 최종 fallback: 줄 단위 분할
    sentences = [s.strip() for s in content.split("\n") if s.strip()]
    if not sentences:
        sentences = [content.strip()]

    return [
        ReplyPart(text=s, emotion="NEUTRAL", delay=_calculate_delay(s, "NEUTRAL", i == 0))
        for i, s in enumerate(sentences) if s
    ]


def _reconstruct_score_source(replies: List[ReplyPart]) -> str:
    """파싱/방출된 ReplyPart 목록으로 정규 JSON 배열 문자열을 재구성해
    quick_score 채점 입력으로 사용한다 (F4, 2026-08-04 점검).

    generate_reply(_parse_reply 결과)와 stream_reply(IncrementalReplyParser가
    실제로 방출한 파트)가 공유한다. 스트림 절단(max_tokens로 닫는 ']' 유실 등)
    이나 그 밖의 사소한 형식 손상이 있어도 _parse_reply/IncrementalReplyParser가
    이미 복구·방출에 성공했다면, 실제로 사용자에게 전달된 말풍선 형태를
    기준으로 채점해야 한다. 원문(raw)을 그대로 채점하면 classify_quality_issues의
    JSON 파싱이 실패해 JSON_INVALID(0.1)로 오판하고, 정상 응답인데도 불필요한
    재생성(quality_gate 재시도) 또는 저품질 텔레메트리를 유발한다.
    """
    return json.dumps(
        [{"text": p.text, "emotion": p.emotion} for p in replies],
        ensure_ascii=False,
    )


class IncrementalReplyParser:
    """스트리밍 토큰에서 완성된 {"text","emotion"} 말풍선을 순차 방출.

    LLM 응답 형식 `[{"text":"...","emotion":"CODE"}, ...]` 를 가정하되,
    객체 하나가 완결될 때마다 즉시 ReplyPart 로 방출한다. 전체 생성이
    끝나기 전에 첫 말풍선을 내보내 체감 지연(TTFB)을 줄이는 것이 목적.

    형식이 깨져 아무 것도 방출하지 못한 경우, 호출측은 raw 원문으로
    기존 _parse_reply() 폴백을 수행한다 (emitted_count == 0 판단).
    """

    _VALID_EMOTIONS = VALID_EMOTIONS

    def __init__(self) -> None:
        self._buf = ""          # 아직 객체로 확정되지 않은 미소비 버퍼
        self.raw = ""           # 전체 원문 축적 (폴백용)
        self.emitted_count = 0  # 방출한 말풍선 수

    def feed(self, chunk: Optional[str]) -> List[ReplyPart]:
        """토큰 청크를 받아 이번 청크로 새로 완결된 말풍선들을 반환."""
        if not chunk:
            return []
        # 스트리밍 중 등장할 수 있는 코드펜스 마커 제거 (부분 토큰 안전)
        cleaned = chunk.replace("```json", "").replace("```", "")
        self._buf += cleaned
        self.raw += chunk
        return self._drain()

    def _drain(self) -> List[ReplyPart]:
        out: List[ReplyPart] = []
        while True:
            obj_str, rest = self._next_object(self._buf)
            if obj_str is None:
                break
            self._buf = rest
            part = self._to_part(obj_str)
            if part is not None:
                out.append(part)
                self.emitted_count += 1
        return out

    @staticmethod
    def _next_object(s: str) -> Tuple[Optional[str], str]:
        """버퍼에서 첫 번째 균형 잡힌 {...} 객체를 추출.

        문자열 리터럴/이스케이프를 존중해 brace depth 를 센다.
        완결 객체가 없으면 (None, 원본 버퍼) 반환.
        """
        start = s.find("{")
        if start < 0:
            return None, s
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(s)):
            c = s[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        return s[start:i + 1], s[i + 1:]
        return None, s  # 아직 미완결

    def _to_part(self, obj_str: str) -> Optional[ReplyPart]:
        try:
            d = json.loads(obj_str)
        except (json.JSONDecodeError, ValueError):
            return None
        if not isinstance(d, dict):
            return None
        text = str(d.get("text", "")).strip()
        if not text:
            return None
        emotion = d.get("emotion", "NEUTRAL")
        if emotion not in self._VALID_EMOTIONS:
            emotion = "NEUTRAL"
        is_first = self.emitted_count == 0
        return ReplyPart(text=text, emotion=emotion, delay=_calculate_delay(text, emotion, is_first))


# ── MBTI 그룹별 목업 응답 ──────────────────────────────────────

_MOCK_RESPONSES = {
    "NT": {
        "low": [
            lambda nick, msg: [
                ReplyPart(text=f"흠, {nick}님이군요.", emotion="NEUTRAL", delay=1200),
                ReplyPart(text=f"'{msg}'... 흥미로운 주제네요.", emotion="NEUTRAL", delay=1800),
                ReplyPart(text="좀 더 구체적으로 얘기해볼까요?", emotion="NEUTRAL", delay=1800),
            ],
            lambda nick, msg: [
                ReplyPart(text="안녕하세요.", emotion="NEUTRAL", delay=800),
                ReplyPart(text=f"그 말에 대해 생각해봤는데...", emotion="NEUTRAL", delay=1800),
                ReplyPart(text="나름 일리가 있네요. 계속 얘기해봐요.", emotion="NEUTRAL", delay=2000),
            ],
            lambda nick, msg: [
                ReplyPart(text=f"오, {nick}님.", emotion="NEUTRAL", delay=800),
                ReplyPart(text="뭔가 재밌는 이야기가 될 것 같은 예감이 드네요.", emotion="PLAYFUL", delay=2000),
            ],
        ],
        "mid": [
            lambda nick, msg: [
                ReplyPart(text=f"오 {nick}, 재밌는 얘기하네~", emotion="HAPPY", delay=1500),
                ReplyPart(text="근데 반대로 생각해보면 어때?", emotion="PLAYFUL", delay=1800),
                ReplyPart(text="...나한테 이런 토론 거는 거 좋아 ㅋ", emotion="SHY", delay=2000),
            ],
            lambda nick, msg: [
                ReplyPart(text="ㅋㅋ", emotion="PLAYFUL", delay=800),
                ReplyPart(text=f"{nick} 그거 알아? 나 그 주제에 대해 좀 생각해본 적 있거든", emotion="HAPPY", delay=2200),
                ReplyPart(text="...관심 있으면 내 이론 들어볼래?", emotion="SHY", delay=1800),
            ],
        ],
        "high": [
            lambda nick, msg: [
                ReplyPart(text=f"{nick}~ 왔구나", emotion="HAPPY", delay=1200),
                ReplyPart(text="너랑 얘기하면 뇌가 활성화되는 느낌이야", emotion="LOVE", delay=2000),
                ReplyPart(text="...이건 칭찬이야, 착각하지 마 ㅋ", emotion="PLAYFUL", delay=1800),
                ReplyPart(text="계속 옆에 있어줘", emotion="TOUCHED", delay=1500),
            ],
            lambda nick, msg: [
                ReplyPart(text=f"어, {nick}", emotion="HAPPY", delay=800),
                ReplyPart(text="솔직히 네가 올까봐 좀 기다렸어", emotion="SHY", delay=2000),
                ReplyPart(text="...그 말 하니까 좀 부끄럽네", emotion="SHY", delay=1500),
                ReplyPart(text="뭐 어때, 사실인걸 ㅋ", emotion="PLAYFUL", delay=1200),
            ],
        ],
    },
    "NF": {
        "low": [
            lambda nick, msg: [
                ReplyPart(text=f"안녕하세요, {nick}님!", emotion="HAPPY", delay=1500),
                ReplyPart(text="만나서 반가워요~", emotion="HAPPY", delay=1200),
                ReplyPart(text=f"'{msg}'... 왠지 마음이 따뜻해지는 말이에요.", emotion="SHY", delay=2000),
            ],
            lambda nick, msg: [
                ReplyPart(text=f"와, {nick}님이다!", emotion="HAPPY", delay=1200),
                ReplyPart(text="오늘 날씨처럼 좋은 만남이 될 것 같아요", emotion="HAPPY", delay=2000),
            ],
            lambda nick, msg: [
                ReplyPart(text="안녕하세요~!", emotion="HAPPY", delay=800),
                ReplyPart(text="처음이라 좀 떨려요 히히", emotion="SHY", delay=1500),
                ReplyPart(text="천천히 알아가요 우리~", emotion="HAPPY", delay=1500),
            ],
        ],
        "mid": [
            lambda nick, msg: [
                ReplyPart(text=f"헤이 {nick}~!", emotion="HAPPY", delay=1200),
                ReplyPart(text="있잖아, 너랑 얘기하면 마음이 편해져", emotion="SHY", delay=2000),
                ReplyPart(text="오늘도 재밌는 거 같이 하자!", emotion="PLAYFUL", delay=1500),
            ],
            lambda nick, msg: [
                ReplyPart(text=f"{nick}~!", emotion="HAPPY", delay=800),
                ReplyPart(text="아까 네 생각하다가 웃겼던 거 떠올랐어 ㅋㅋ", emotion="PLAYFUL", delay=2200),
                ReplyPart(text="너 진짜 재밌는 사람이야~", emotion="HAPPY", delay=1500),
            ],
        ],
        "high": [
            lambda nick, msg: [
                ReplyPart(text=f"{nick}~~ 보고 싶었어!", emotion="LOVE", delay=1500),
                ReplyPart(text="너 없으면 세상이 흑백이야...", emotion="SAD", delay=1800),
                ReplyPart(text="히히 농담이야~ 근데 반은 진심", emotion="PLAYFUL", delay=1500),
                ReplyPart(text="오늘도 같이 있어줘서 행복해!", emotion="TOUCHED", delay=1500),
            ],
            lambda nick, msg: [
                ReplyPart(text=f"{nick}!!", emotion="LOVE", delay=800),
                ReplyPart(text="너 오니까 진짜 기분 좋아졌어...", emotion="TOUCHED", delay=1800),
                ReplyPart(text="나 이거 좀 과한 거 아니지? ㅋㅋ 근데 사실이야~", emotion="SHY", delay=2200),
            ],
        ],
    },
    "ST": {
        "low": [
            lambda nick, msg: [
                ReplyPart(text=f"네, {nick}님.", emotion="NEUTRAL", delay=800),
                ReplyPart(text=f"'{msg}'... 알겠습니다.", emotion="NEUTRAL", delay=1500),
                ReplyPart(text="더 얘기해주세요.", emotion="NEUTRAL", delay=1200),
            ],
            lambda nick, msg: [
                ReplyPart(text="반갑습니다.", emotion="NEUTRAL", delay=800),
                ReplyPart(text="편하게 말해주세요.", emotion="NEUTRAL", delay=1200),
            ],
        ],
        "mid": [
            lambda nick, msg: [
                ReplyPart(text=f"어, {nick}.", emotion="NEUTRAL", delay=800),
                ReplyPart(text="음, 그래 뭐 나쁘지 않네.", emotion="NEUTRAL", delay=1500),
                ReplyPart(text="...내가 뭐 해줄 거 있어?", emotion="SHY", delay=1500),
            ],
            lambda nick, msg: [
                ReplyPart(text=f"{nick}", emotion="NEUTRAL", delay=800),
                ReplyPart(text="오늘 밥 뭐 먹었어?", emotion="WORRIED", delay=1200),
                ReplyPart(text="...그냥 궁금해서", emotion="SHY", delay=1200),
            ],
        ],
        "high": [
            lambda nick, msg: [
                ReplyPart(text=f"{nick}, 밥은 먹었어?", emotion="WORRIED", delay=1200),
                ReplyPart(text="...걱정되니까 묻는 거야, 다른 뜻 없어", emotion="SHY", delay=2000),
                ReplyPart(text="내가 옆에 있을게. 약속.", emotion="LOVE", delay=1500),
            ],
            lambda nick, msg: [
                ReplyPart(text=f"...{nick}", emotion="NEUTRAL", delay=800),
                ReplyPart(text="너 괜찮아? 표정이 안 좋아 보여서", emotion="WORRIED", delay=1800),
                ReplyPart(text="뭐든 말해, 내가 들을게", emotion="TOUCHED", delay=1500),
            ],
        ],
    },
    "SF": {
        "low": [
            lambda nick, msg: [
                ReplyPart(text=f"안녕~ {nick}님!", emotion="HAPPY", delay=1200),
                ReplyPart(text="반가워요!! 우리 친해지자~", emotion="HAPPY", delay=1500),
                ReplyPart(text="뭐 재밌는 거 같이 해요!", emotion="PLAYFUL", delay=1500),
            ],
            lambda nick, msg: [
                ReplyPart(text="하이하이~!", emotion="HAPPY", delay=800),
                ReplyPart(text=f"{nick}님이라고 하는 거죠? 이름 예쁘다~", emotion="HAPPY", delay=1800),
                ReplyPart(text="앞으로 잘 부탁해요 ㅎㅎ", emotion="SHY", delay=1200),
            ],
        ],
        "mid": [
            lambda nick, msg: [
                ReplyPart(text=f"야호~ {nick}!", emotion="HAPPY", delay=1200),
                ReplyPart(text="오늘 기분 어때어때?!", emotion="PLAYFUL", delay=1200),
                ReplyPart(text="나는 네가 와서 기분 좋아졌어 ㅎㅎ", emotion="SHY", delay=1800),
            ],
            lambda nick, msg: [
                ReplyPart(text=f"{nick}~!", emotion="HAPPY", delay=800),
                ReplyPart(text="ㅋㅋㅋ 아 나 오늘 웃긴 거 봤는데!", emotion="PLAYFUL", delay=1800),
                ReplyPart(text="나중에 보여줄게~ 기대해!", emotion="HAPPY", delay=1500),
            ],
        ],
        "high": [
            lambda nick, msg: [
                ReplyPart(text=f"어머~ {nick}!!", emotion="LOVE", delay=1200),
                ReplyPart(text="나 오늘 너 생각하면서 이거 샀어 ㅎㅎ", emotion="HAPPY", delay=2000),
                ReplyPart(text="너 완전 내 최애야!!", emotion="LOVE", delay=1500),
                ReplyPart(text="우리 같이 놀자놀자~!", emotion="PLAYFUL", delay=1200),
            ],
            lambda nick, msg: [
                ReplyPart(text=f"{nick}!! 왔어?!", emotion="LOVE", delay=1200),
                ReplyPart(text="아 진짜 보고 싶었어ㅠㅠ", emotion="TOUCHED", delay=1500),
                ReplyPart(text="너무 좋다~ 오늘 뭐 할까?!", emotion="HAPPY", delay=1500),
            ],
        ],
    },
}


def _mock_reply(message: str, mbti: str, nickname: str, affinity_level: int) -> List[ReplyPart]:
    """API 키 없을 때 MBTI 그룹별 차별화된 목업 응답"""
    group = _get_mbti_group(mbti)
    responses = _MOCK_RESPONSES.get(group, _MOCK_RESPONSES["NF"])

    if affinity_level <= 2:
        templates = responses["low"]
    elif affinity_level <= 4:
        templates = responses["mid"]
    else:
        templates = responses["high"]

    template = random.choice(templates)
    return template(nickname, message)
