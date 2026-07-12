"""채팅 서비스 - LLM 연동 및 메시지 분할"""

import asyncio
import json
import logging
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import AsyncGenerator, List, Optional, Tuple, Union

from openai import AsyncOpenAI

from .circuit_breaker import CircuitOpenError, get_openai_circuit
from .config import (
    OPENAI_API_KEY,
    TOGETHER_API_KEY,
    MAX_TOKENS,
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
from .memory_service import summarize_conversation, extract_facts, extract_episodes, build_memory_context
from .quality_service import (
    check_diversity,
    classify_quality_issues,
    quick_score,
    score_response_async,
)
from .metrics_service import record_event
from .model_routing import resolve_model_endpoint

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
) -> List[dict]:
    """시스템 프롬프트 + safety + 히스토리 + 현재 메시지로 messages 배열 조립.

    generate_reply(논스트림)와 stream_reply(스트림)가 공유하여 프롬프트
    정합성을 한 곳에서 보장한다.
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
    )
    # safety_prompt는 거의 변하지 않으므로 정적 system_prompt에 인라인하여 prefix caching 효율 극대화
    safety_prompt = get_safety_system_prompt()
    combined_prompt = f"{system_prompt}\n\n{safety_prompt}" if safety_prompt else system_prompt
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


def _route_model(
    character_id: str, message: str, history_len: int
) -> Tuple[str, Optional[str]]:
    """모델 선택: 파인튜닝 우선 → A/B variant → 복잡도 라우팅.

    Returns (model_id, ab_variant). ab_variant 는 결과 기록용(없으면 None).
    """
    finetuned_model = get_model_for_character(character_id) if character_id else None
    if finetuned_model and finetuned_model != LLM_MODEL_COMPLEX:
        return finetuned_model, None  # 파인튜닝 모델 우선

    try:
        if character_id:
            # 지연 임포트: 순환/기동 순서 회피
            from .ab_test import get_ab_manager
            ab_variant = get_ab_manager().assign_variant(
                user_id=character_id,
                experiment_id="model_routing",
            )
            logger.info(
                "[AB] model_routing: character_id=%s → variant=%s",
                character_id, ab_variant,
            )
            return ab_variant, ab_variant
        complexity = _classify_message_complexity(message, history_len)
        return (LLM_MODEL_COMPLEX if complexity == "complex" else LLM_MODEL_SIMPLE), None
    except Exception as _ab_err:
        logger.warning("[AB] variant 배정 실패, 복잡도 라우팅으로 fallback: %s", _ab_err)
        complexity = _classify_message_complexity(message, history_len)
        return (LLM_MODEL_COMPLEX if complexity == "complex" else LLM_MODEL_SIMPLE), None


def _record_quality_gate_event(
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
    """
    payload = {
        "score": score,
        "issues": classify_quality_issues(user_msg, ai_response),
        "model_id": model_id,
    }
    if extra_payload:
        payload.update(extra_payload)
    record_event(
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
) -> Tuple[List[ReplyPart], str]:
    """품질 게이트: 저품질 응답(score < QUALITY_GATE_THRESHOLD) 감지 시 1회 재생성,
    점수 비교 후 더 좋은 쪽을 채택한다.

    generate_reply 전용 헬퍼(stream_reply의 저품질 처리는 재생성 없이 텔레메트리만
    남기므로 별개 — 이 함수의 대상이 아님). 호출부에서 이미
    `score < QUALITY_GATE_THRESHOLD` 판정을 마친 뒤 호출됨을 전제로 한다.

    Returns (replies, content) — 재시도가 원본보다 낫지 않으면 입력을 그대로 반환.
    """
    _record_quality_gate_event(score, message, content, model_id, room_id, character_id)
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

    if retry_response:
        retry_content = retry_response.choices[0].message.content or ""
        retry_replies = _parse_reply(retry_content)
        if retry_replies:
            retry_score = quick_score(message, retry_content, mbti)
            # 원본과 재시도 중 점수가 더 높은 쪽 채택.
            # 동점이면 재시도(더 최신·형식 보강 반영)를 선호.
            if retry_score >= score:
                logger.info(
                    f"재생성 채택 (retry={retry_score} >= orig={score})"
                )
                replies = retry_replies
                content = retry_content
            else:
                logger.info(
                    f"원본 유지 (orig={score} > retry={retry_score})"
                )

    return replies, content


async def _record_turn_latency_event(
    room_id: str,
    character_id: str,
    model_id: str,
    streaming: bool,
    t_memory_ms: float,
    t_rag_ms: float,
    t_first_token_ms: float,
) -> None:
    """턴 단계별 레이턴시(P1 계측)를 turn_latency 이벤트로 기록.

    generate_reply/stream_reply가 공유. `_record_usage`/`_record_ab_result`와
    동일하게 create_tracked_task로 fire-and-forget 스케줄되어 메인 응답
    경로를 블로킹하지 않는다(record_event 자체는 아직 동기 — P2에서
    async 전환 예정, 이 이벤트도 그때 같이 정리).
    t_gate(라우터 게이트 단계)는 이번 계측에 포함하지 않음 — 라우터
    호출부까지 시그니처를 확장하는 대신 최소 변경으로 3구간만 계측.
    """
    payload = {
        "model_id": model_id,
        "streaming": streaming,
        "t_memory_ms": round(t_memory_ms, 2),
        "t_rag_ms": round(t_rag_ms, 2),
        "t_first_token_ms": round(t_first_token_ms, 2),
    }
    logger.info(
        "[latency] room=%s model=%s streaming=%s memory=%.1fms rag=%.1fms first_token=%.1fms",
        room_id, model_id, streaming, t_memory_ms, t_rag_ms, t_first_token_ms,
    )
    try:
        record_event(
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
    log_lora_routing: bool = False,
) -> Tuple[AsyncOpenAI, str, Optional[str]]:
    """LoRA 서빙이면 Together AI 클라이언트로 전환.

    generate_reply/stream_reply가 공유. log_lora_routing으로 라우팅 성공
    시 info 로그 여부를 제어(논스트림 경로만 기존에 로그를 남겼음).
    Returns (active_client, model_id, lora_base_url).
    """
    resolved_model_id, lora_base_url = await resolve_model_endpoint(
        model_id, ab_variant or ""
    )
    if lora_base_url and TOGETHER_API_KEY:
        active_client = AsyncOpenAI(
            api_key=TOGETHER_API_KEY,
            base_url=lora_base_url,
        )
        model_id = resolved_model_id
        if log_lora_routing:
            logger.info("[LoRA] Together AI 라우팅: model=%s base_url=%s", model_id, lora_base_url)
    else:
        active_client = client
    return active_client, model_id, lora_base_url


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
) -> Tuple[Optional[asyncio.Task], Optional[asyncio.Task], int, str]:
    """호감도 분석 태스크 + RAG 검색 태스크를 병렬로 시작(클라이언트 있을 때만).

    클라이언트가 없으면 즉시 키워드 기반 호감도를 계산한다.

    generate_reply/stream_reply가 공유(S13/S14 잔여 본문 분할). 태스크
    소유권은 호출부가 유지해야 하므로(예외 시 취소 처리) 생성한 Task
    객체를 그대로 반환한다 — 헬퍼 안에서 await/취소하지 않는다.
    클라이언트가 없을 때의 처리(목업 응답 생성)는 두 호출부가 서로 다르므로
    (generate_reply는 return, stream_reply는 yield 후 return) 호출부에서
    각자 담당한다 — 이 헬퍼는 pre_mem_ctx 계산과 task 생성/폴백 delta
    계산까지만 책임진다.
    Returns (affinity_task, rag_task, affinity_delta, pre_mem_ctx).
    """
    affinity_delta = 0
    # 선행 memory_context 조회 (호감도 분석에 활용)
    pre_mem_ctx = ""
    if character_name and nickname:
        pre_mem_ctx = await build_memory_context(
            character_name,
            nickname,
            room_id=room_id,
            character_id=character_id,
        )

    if client:
        recent_context = _build_recent_context(conversation_history)
        # 호감도 분석을 비동기 태스크로 시작 (메인 LLM 호출과 병렬 실행)
        affinity_task = asyncio.create_task(
            analyze_affinity_with_llm(
                message, affinity_level, mbti, recent_context,
                memory_context=pre_mem_ctx,
            )
        )
        # RAG(Chroma) 검색도 스레드에서 병렬 시작 — 호감도 분석과 동시 실행되어
        # LLM 프롬프트 조립 전까지 지연을 흡수한다.
        _rag_scope_id = _storage_scope_id(room_id, character_id)
        if _rag_scope_id and get_store():
            rag_task = asyncio.create_task(
                asyncio.to_thread(_rag_search_sync, _rag_scope_id, message)
            )
        else:
            rag_task = None
    else:
        affinity_task = None
        rag_task = None
        affinity_delta = calculate_affinity_delta(
            message, affinity_level, conversation_history, user_mbti, mbti
        )

    return affinity_task, rag_task, affinity_delta, pre_mem_ctx


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
    log_lora_routing: bool = True,
) -> Tuple[List[dict], str, Optional[str], AsyncOpenAI, Optional[str]]:
    """시스템 프롬프트 조립 + 모델 라우팅(파인튜닝/AB/복잡도) + LoRA 클라이언트 해석.

    generate_reply/stream_reply가 공유(S13/S14 잔여 본문 분할). 논스트림
    경로만 라우팅 성공 시 info 로그를 남기므로(기존 동작) log_lora_routing
    으로 _resolve_reply_client(S11) 호출 시 로그 여부를 제어한다
    (generate_reply=True, stream_reply=False).
    Returns (messages, model_id, ab_variant, active_client, lora_base_url).
    lora_base_url은 stream_reply가 stream_options 분기에 사용한다
    (generate_reply는 사용하지 않지만 반환값 형태는 통일한다).
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
    )

    # 모델 선택 (Phase 5: 복잡도 기반 라우팅 + A/B 테스트 overlay)
    model_id, ab_variant = _route_model(
        character_id, message, len(conversation_history)
    )

    # LoRA 서빙 라우팅: Together AI 엔드포인트 사용 (9차 스프린트)
    active_client, model_id, lora_base_url = await _resolve_reply_client(
        model_id, ab_variant, log_lora_routing=log_lora_routing
    )

    return messages, model_id, ab_variant, active_client, lora_base_url


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
        ), name="record-usage")

    # A/B 테스트 결과 기록 (백그라운드)
    if ab_variant and character_id:
        total_tokens = getattr(usage, "total_tokens", 0) if usage else 0
        create_tracked_task(_record_ab_result(
            experiment_id="model_routing",
            variant=ab_variant,
            user_id=character_id,
            character_id=character_id,
            tokens=float(total_tokens),
            response_time_ms=elapsed_ms,
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
) -> Tuple[List[ReplyPart], int]:
    """LLM을 사용하여 대화 응답 생성, (replies, affinity_delta) 반환"""

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

    # 2. 호감도 변화 계산 (LLM 우선, 실패 시 키워드 fallback)
    # P1 계측: build_memory_context 대기를 포함한 준비 단계 소요(t_memory)
    _t_memory_start = time.perf_counter()
    affinity_task, rag_task, affinity_delta, _pre_mem_ctx = await _spawn_parallel_analysis(
        message, mbti, affinity_level, conversation_history, user_mbti,
        character_name, nickname, character_id, room_id,
    )
    _t_memory_ms = (time.perf_counter() - _t_memory_start) * 1000

    # 3. API 키가 없으면 목업 응답
    if not client:
        return _mock_reply(message, mbti, nickname, affinity_level), affinity_delta

    # 4. LLM 호출
    try:
        # 대화 요약 기억 (memory_service): 10메시지마다 요약/핵심정보 갱신 (백그라운드)
        mem_ctx = _pre_mem_ctx  # 이미 조회한 memory_context 재사용
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
            if not mem_ctx:
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
        messages, model_id, _ab_variant, _active_client, _lora_base_url = await _assemble_prompt_and_model(
            mbti, speech_style, relationship, nickname, character_name, affinity_level,
            user_mbti, persona_raw, persona_summary, dialogue_prompt, visual_prompt,
            memory_dicts, mem_ctx, episode_context, mood, conversation_history, message,
            character_id,
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
        if replies:
            score = quick_score(message, content, mbti)
            if score < QUALITY_GATE_THRESHOLD:
                replies, content = await _quality_gate_regenerate(
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
            message, result, mbti, affinity_level,
        )

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
            ),
            name="turn-latency",
        )

        return result, affinity_delta

    except Exception as e:
        # 병렬 호감도 분석 태스크가 남아있으면 정리
        if affinity_task is not None and not affinity_task.done():
            affinity_task.cancel()
        if rag_task is not None and not rag_task.done():
            rag_task.cancel()
        logger.error(f"LLM 호출 실패: {e}")
        return [ReplyPart(
            text="앗, 잠깐 멍해졌어요... 다시 말해줄래요?",
            emotion="SURPRISED",
            delay=2000
        )], 0


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

    # 3+5. 선행 memory_context + 호감도 분석/RAG 병렬 시작 (공유 헬퍼, S13/S14)
    # 클라이언트가 없으면 헬퍼가 즉시 키워드 기반 호감도(affinity_delta)만
    # 계산하고 태스크는 만들지 않는다 — 아래 "4. 클라이언트 부재" 분기에서
    # 그 값을 그대로 사용한다(원본 stream_reply의 동일 계산과 동치).
    # P1 계측: build_memory_context 대기를 포함한 준비 단계 소요(t_memory)
    _t_memory_start = time.perf_counter()
    affinity_task, rag_task, affinity_delta, _pre_mem_ctx = await _spawn_parallel_analysis(
        message, mbti, affinity_level, conversation_history, user_mbti,
        character_name, nickname, character_id, room_id,
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
    try:
        # 6. 기억 컨텍스트 (N턴 백그라운드 갱신 + 조회)
        mem_ctx = _pre_mem_ctx
        if character_name and nickname and conversation_history:
            if _should_extract_memory(_orig_history_len):
                create_tracked_task(
                    _background_memory_extraction(
                        character_name, nickname, conversation_history,
                        character_id, room_id,
                    ),
                    name="memory-extraction",
                )
            if not mem_ctx:
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

        all_memories = _filter_relevant_memories(message, all_memories, top_k=3)
        memory_dicts = [{"key": m.key, "value": m.value} for m in all_memories]

        # 8. 프롬프트 + 모델 라우팅 (공유 헬퍼, S13/S14) — 스트리밍은 LoRA 라우팅
        # info 로그를 남기지 않는 기존 동작 유지(log_lora_routing=False).
        messages, model_id, _ab_variant, active_client, _lora_base_url = await _assemble_prompt_and_model(
            mbti, speech_style, relationship, nickname, character_name, affinity_level,
            user_mbti, persona_raw, persona_summary, dialogue_prompt, visual_prompt,
            memory_dicts, mem_ctx, episode_context, mood, conversation_history, message,
            character_id, log_lora_routing=False,
        )

        # 9. 스트리밍 호출 + 증분 파싱
        # A/B(P0-3): 논스트림 경로와 동일하게 토큰 사용량·응답시간을 기록하기 위해
        # 가능하면 usage 청크를 요청한다(Together AI LoRA 엔드포인트는 미지원일 수 있어 제외).
        _stream_kwargs: dict = dict(
            model=model_id,
            messages=messages,
            temperature=0.85,
            max_tokens=1200,
            timeout=45,
            stream=True,
        )
        if not (_lora_base_url and TOGETHER_API_KEY):
            _stream_kwargs["stream_options"] = {"include_usage": True}

        parser = IncrementalReplyParser()
        _t_start = time.monotonic()
        # P1 계측: LLM 호출 시작~첫 콘텐츠 청크 도착까지의 소요(t_first_token)
        _t_first_token_ms: Optional[float] = None
        _stream_total_tokens = 0.0
        stream = await active_client.chat.completions.create(**_stream_kwargs)
        async for chunk in stream:
            _chunk_usage = getattr(chunk, "usage", None)
            if _chunk_usage is not None:
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
                    yield part

        # 11. 그래도 비었으면 안전 기본 응답
        if not full_text:
            yield ReplyPart(text="음... 뭐라고 말해야 할지 모르겠어요", emotion="SHY", delay=2000)

        # 12. 저품질 텔레메트리 (재생성 없음)
        if full_text:
            _score = quick_score(message, parser.raw or full_text, mbti)
            if _score < QUALITY_GATE_THRESHOLD:
                _record_quality_gate_event(
                    _score, message, parser.raw or full_text, model_id, room_id, character_id,
                    extra_payload={"streaming": True},
                )

        # 13. 호감도 수집 (병렬 태스크)
        affinity_delta = await _collect_affinity_delta(
            affinity_task, message, affinity_level, conversation_history, user_mbti, mbti,
            warn_message="[stream] 호감도 분석 실패, 키워드 폴백",
        )

        # 14. 백그라운드 품질 평가
        if full_text:
            create_tracked_task(
                _post_response_quality_check(
                    message, full_text, mbti, affinity_level,
                    room_id=room_id, character_id=character_id,
                ),
                name="quality-check",
            )

        # 15. A/B 테스트 결과 기록 (P0-3, 백그라운드) — 논스트림 경로(generate_reply)와
        # 동일 컨벤션: assign_variant 시 character_id 기준으로 배정했으므로 결과도
        # character_id를 user_id로 사용해 기록한다.
        if _ab_variant and character_id:
            create_tracked_task(_record_ab_result(
                experiment_id="model_routing",
                variant=_ab_variant,
                user_id=character_id,
                character_id=character_id,
                tokens=_stream_total_tokens,
                response_time_ms=_elapsed_ms,
            ), name="record-ab-result")

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
            ),
            name="turn-latency",
        )

    except Exception as e:
        if not affinity_task.done():
            affinity_task.cancel()
        if rag_task is not None and not rag_task.done():
            rag_task.cancel()
        logger.error(f"스트리밍 생성 실패: {e}")
        if not full_text:
            yield ReplyPart(
                text="앗, 잠깐 멍해졌어요... 다시 말해줄래요?",
                emotion="SURPRISED",
                delay=2000,
            )

    yield StreamDone(affinity_delta=affinity_delta, full_text=full_text)


async def stream_lora_response(messages: list, model_id: str, base_url: str):
    """Together AI LoRA 모델 스트리밍 응답 제너레이터"""
    client = AsyncOpenAI(api_key=TOGETHER_API_KEY, base_url=base_url)
    response = await client.chat.completions.create(
        model=model_id,
        messages=messages,
        stream=True,
        max_tokens=MAX_TOKENS,
        temperature=0.85,
        timeout=45,
    )
    async for chunk in response:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


async def _record_usage(
    room_id: str,
    character_id: str,
    model_id: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> None:
    """OpenAI API 사용량 비동기 기록 (H-3)."""
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
) -> None:
    """A/B 테스트 메트릭(토큰 수·응답시간)을 백그라운드에서 기록 (DATA-B 신예린)."""
    try:
        # 지연 임포트: 순환/기동 순서 회피
        from .ab_test import get_ab_manager
        ab = get_ab_manager()
        ab.record_result(
            experiment_id=experiment_id,
            variant=variant,
            metric_name="total_tokens",
            value=tokens,
            user_id=user_id,
            character_id=character_id,
        )
        ab.record_result(
            experiment_id=experiment_id,
            variant=variant,
            metric_name="response_time_ms",
            value=response_time_ms,
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
) -> None:
    """응답 전송 후 fire-and-forget 으로 실행되는 품질 평가."""
    try:
        await score_response_async(
            user_msg=user_msg,
            ai_response=ai_response,
            mbti=mbti,
            affinity_level=affinity_level,
            room_id=room_id,
            character_id=character_id,
        )
        if character_id:
            check_diversity(character_id, ai_response, room_id=room_id)
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


def _calculate_delay(text: str) -> int:
    """텍스트 길이에 따른 자연스러운 딜레이 계산"""
    length = len(text)
    if length <= 5:  # 짧은 리액션 (ㅋㅋ, 헐, 응)
        return 800
    elif length <= 20:
        return 1200
    else:
        return min(length * 60 + 500, 3000)


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
                    replies.append(ReplyPart(text=text, emotion=emotion, delay=_calculate_delay(text)))
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
                        replies.append(ReplyPart(text=text, emotion=emotion, delay=_calculate_delay(text)))
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
                    replies.append(ReplyPart(text=text, emotion=emotion, delay=_calculate_delay(text)))
            if replies:
                return replies
    except Exception:
        pass

    # 5. 최종 fallback: 줄 단위 분할
    sentences = [s.strip() for s in content.split("\n") if s.strip()]
    if not sentences:
        sentences = [content.strip()]

    return [
        ReplyPart(text=s, emotion="NEUTRAL", delay=_calculate_delay(s))
        for s in sentences if s
    ]


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
        return ReplyPart(text=text, emotion=emotion, delay=_calculate_delay(text))


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
