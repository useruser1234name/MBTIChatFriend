"""채팅 서비스 - LLM 연동 및 메시지 분할"""

import asyncio
import json
import logging
import math
import random
import re
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from openai import AsyncOpenAI

from .config import OPENAI_API_KEY, LLM_MODEL_COMPLEX, LLM_MODEL_SIMPLE, LLM_MODEL_BASE
from .background_tasks import create_tracked_task
from .content_filter import check_content, get_safety_system_prompt
from .models import HistoryMessage, MemoryItem, ReplyPart
from .prompts import build_system_prompt, build_diary_prompt, build_memory_extract_prompt
from .vector_store import get_store
from .finetune_service import get_model_for_character
from .memory_service import summarize_conversation, extract_facts, extract_episodes, build_memory_context
from .quality_service import check_diversity, quick_score, score_response_async
from .metrics_service import record_event

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# ── 품질 게이트 임계값 (0.0~1.0, 낮을수록 재생성 빈도 ↑) ─────────
QUALITY_GATE_THRESHOLD = 0.4

# ── LLM 비용 단가 (USD per 1K tokens, 2025-04 기준) ──────────────
_MODEL_COSTS = {
    "gpt-4.1":      {"prompt": 0.002, "completion": 0.008},
    "gpt-4.1-mini": {"prompt": 0.0004, "completion": 0.0016},
    # Legacy fallback
    "gpt-4o":       {"prompt": 0.0025, "completion": 0.0100},
    "gpt-4o-mini":  {"prompt": 0.00015, "completion": 0.0006},
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


def _get_mbti_group(mbti: str) -> str:
    """MBTI를 4개 기능 그룹으로 분류"""
    if len(mbti) != 4:
        return "NF"
    if mbti[1] == "N" and mbti[2] == "T":
        return "NT"
    elif mbti[1] == "N" and mbti[2] == "F":
        return "NF"
    elif mbti[1] == "S" and mbti[2:4] in ("TJ", "TP"):
        return "ST"
    else:
        return "SF"


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


def calculate_affinity_decay(
    current_score: int,
    current_level: int,
    last_chat_time: Optional[datetime],
) -> int:
    """
    미접속 기간에 따른 호감도 감쇠 계산.

    규칙 (전문가 합의):
    - 7일 이하: 동결 (변화 없음)
    - 7일 초과: 주당 -2점
    - 하한: 현재 레벨 -1의 최소 점수 (Level 1 이하로 떨어지지 않음)

    Returns: 감쇠 후 점수
    """
    if last_chat_time is None:
        return current_score

    now = datetime.now(timezone.utc)
    if last_chat_time.tzinfo is None:
        last_chat_time = last_chat_time.replace(tzinfo=timezone.utc)

    days_inactive = (now - last_chat_time).days

    if days_inactive <= FREEZE_DAYS:
        return current_score

    weeks_after_freeze = (days_inactive - FREEZE_DAYS) / 7
    decay = int(weeks_after_freeze * DECAY_PER_WEEK)

    # 하한: 현재 레벨 -1 최소 점수 (최소 Level 1 = 0점)
    lower_level = max(1, current_level - 1)
    min_score = AFFINITY_LEVEL_THRESHOLDS.get(lower_level, 0)

    return max(current_score - decay, min_score)


def calculate_return_bonus(original_score: int, current_score: int) -> int:
    """
    복귀 시 하락분의 50% 회복.
    Returns: 보너스 점수
    """
    lost = original_score - current_score
    if lost <= 0:
        return 0
    return int(lost * RETURN_RECOVERY_RATE)


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
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(content[start:end])
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
            max_tokens=300
        )

        content = response.choices[0].message.content or ""
        start = content.find("[")
        end = content.rfind("]") + 1
        if start >= 0 and end > start:
            data = json.loads(content[start:end])
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


async def _background_memory_extraction(
    character_name: str,
    nickname: str,
    conversation_history: List[HistoryMessage],
    character_id: str,
    room_id: str,
) -> None:
    """백그라운드 메모리 추출 (사용자 응답 블로킹 방지)"""
    try:
        scope_id = _storage_scope_id(room_id, character_id)
        await summarize_conversation(
            character_name,
            nickname,
            conversation_history,
            room_id=room_id,
            character_id=character_id,
        )
        await extract_facts(
            character_name,
            nickname,
            conversation_history,
            room_id=room_id,
            character_id=character_id,
        )
        if scope_id:
            await extract_memories(
                character_name,
                nickname,
                conversation_history,
                character_id,
                room_id,
            )
            await extract_episodes(
                character_name,
                nickname,
                conversation_history,
                character_id,
                room_id,
            )
        logger.info(f"백그라운드 메모리 추출 완료: {character_name}")
    except Exception as e:
        logger.warning(f"백그라운드 메모리 추출 실패: {e}")


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

    # 1. 사용자 입력 필터링
    is_safe, reason = check_content(message)
    if not is_safe:
        return [ReplyPart(
            text="그런 표현은 사용하지 말아줘요... 다른 이야기 해볼까요?",
            emotion="SAD",
            delay=2000
        )], -2

    # 2. 호감도 변화 계산 (LLM 우선, 실패 시 키워드 fallback)
    affinity_delta = 0
    # 선행 memory_context 조회 (호감도 분석에 활용)
    _pre_mem_ctx = ""
    if character_name and nickname:
        _pre_mem_ctx = await build_memory_context(
            character_name,
            nickname,
            room_id=room_id,
            character_id=character_id,
        )

    if client:
        recent_context = ""
        if conversation_history and len(conversation_history) >= 2:
            recent_msgs = conversation_history[-8:]
            recent_context = "\n".join(
                f"{'사용자' if h.role == 'user' else '캐릭터'}: {h.content}"
                for h in recent_msgs if h.content.strip()
            )
        # 호감도 분석을 비동기 태스크로 시작 (메인 LLM 호출과 병렬 실행)
        affinity_task = asyncio.create_task(
            analyze_affinity_with_llm(
                message, affinity_level, mbti, recent_context,
                memory_context=_pre_mem_ctx,
            )
        )
    else:
        affinity_task = None
        affinity_delta = calculate_affinity_delta(
            message, affinity_level, conversation_history, user_mbti, mbti
        )

    # 3. API 키가 없으면 목업 응답
    if not client:
        return _mock_reply(message, mbti, nickname, affinity_level), affinity_delta

    # 4. LLM 호출
    try:
        # 대화 요약 기억 (memory_service): 10메시지마다 요약/핵심정보 갱신 (백그라운드)
        mem_ctx = _pre_mem_ctx  # 이미 조회한 memory_context 재사용
        if character_name and nickname and conversation_history:
            hist_len = len(conversation_history)
            if hist_len >= 4 and hist_len % 10 == 0:
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

        # RAG: Chroma에서 현재 메시지와 관련된 기억 시맨틱 검색
        all_memories = list(memories or [])
        episode_context = ""
        scope_id = _storage_scope_id(room_id, character_id)
        if scope_id:
            store = get_store()
            if store:
                rag_docs = store.search_relevant(scope_id, message, n_results=3)
                existing_keys = {m.key for m in all_memories}
                for doc in rag_docs:
                    if ": " in doc:
                        key, value = doc.split(": ", 1)
                        if key not in existing_keys:
                            all_memories.append(MemoryItem(key=key, value=value))
                            existing_keys.add(key)

                # 에피소드 기억 검색
                episodes = store.search_episodes(scope_id, message, n_results=3)
                if episodes:
                    ep_lines = ["## 떠오르는 기억"]
                    ep_lines.append("이 기억들을 대화에서 자연스럽게 활용할 수 있으면 활용해.")
                    for ep in episodes:
                        ep_lines.append(f"- {ep['text']} (감정: {ep['emotion']})")
                    episode_context = "\n".join(ep_lines)

        memory_dicts = [{"key": m.key, "value": m.value} for m in all_memories]
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
        )
        # 메시지 구성 (시스템 + safety 인라인 + 히스토리 + 현재 메시지)
        # safety_prompt는 거의 변하지 않으므로 정적 system_prompt에 인라인하여 prefix caching 효율 극대화
        safety_prompt = get_safety_system_prompt()
        combined_prompt = f"{system_prompt}\n\n{safety_prompt}" if safety_prompt else system_prompt
        messages = [
            {"role": "system", "content": combined_prompt}
        ]
        # mood만 별도 system 메시지로 분리 (동적 블록)
        if mood:
            messages.append({"role": "system", "content": f"[사용자 오늘 기분: {mood}]"})

        # 대화 히스토리 추가 (최근 20개로 확대)
        for hist in conversation_history[-20:]:
            role = hist.role if hist.role in ("user", "assistant") else "user"
            if hist.content.strip():
                messages.append({"role": role, "content": hist.content})

        # 현재 메시지 (prompt injection 방어를 위한 명시적 경계)
        messages.append({"role": "user", "content": f"[사용자 메시지]\n{message}\n[/사용자 메시지]"})

        # 모델 선택 (Phase 5: 복잡도 기반 라우팅)
        complexity = _classify_message_complexity(message, len(conversation_history))
        finetuned_model = get_model_for_character(character_id, owner_uid=owner_uid) if character_id else None
        if finetuned_model and finetuned_model not in ("gpt-4o", "gpt-4.1", LLM_MODEL_BASE):
            model_id = finetuned_model  # 파인튜닝 모델 우선
        else:
            model_id = LLM_MODEL_COMPLEX if complexity == "complex" else LLM_MODEL_SIMPLE

        response = await client.chat.completions.create(
            model=model_id,
            messages=messages,
            temperature=0.85,
            max_tokens=1200,
            timeout=60,
        )

        content = response.choices[0].message.content or ""
        replies = _parse_reply(content)

        # 호감도 분석 태스크 결과 수집 (메인 LLM과 병렬 실행됨)
        if affinity_task is not None:
            try:
                affinity_delta = await affinity_task
            except Exception as e:
                logger.warning(f"호감도 분석 태스크 실패, 키워드 폴백 사용: {e}")
                affinity_delta = 0
            if affinity_delta == 0:
                affinity_delta = calculate_affinity_delta(
                    message, affinity_level, conversation_history, user_mbti, mbti
                )

        # 토큰 사용량 추적
        total_prompt_tokens = response.usage.prompt_tokens if response.usage else 0
        total_completion_tokens = response.usage.completion_tokens if response.usage else 0
        llm_call_count = 1

        # 품질 게이트: 매우 저품질 시 1회 재생성, 점수 비교 후 교체
        if replies:
            score = quick_score(message, content, mbti)
            if score < QUALITY_GATE_THRESHOLD:
                logger.info(f"품질 게이트 발동 (score={score}), 재생성 시도")
                retry_response = await client.chat.completions.create(
                    model=model_id,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=1200,
                )
                retry_content = retry_response.choices[0].message.content or ""
                retry_replies = _parse_reply(retry_content)
                if retry_replies:
                    retry_score = quick_score(message, retry_content, mbti)
                    if retry_score > score:
                        replies = retry_replies
                        content = retry_content
                        logger.info(f"재생성 채택 (원본={score}, 재생성={retry_score})")
                    else:
                        logger.info(f"재생성 기각 (원본={score}, 재생성={retry_score})")
                # 재시도 토큰 누적
                if retry_response.usage:
                    total_prompt_tokens += retry_response.usage.prompt_tokens
                    total_completion_tokens += retry_response.usage.completion_tokens
                    llm_call_count += 1

        # AI 응답 안전성 필터
        filtered_replies = []
        for reply in replies:
            is_safe, _ = check_content(reply.text)
            if is_safe:
                filtered_replies.append(reply)
        result = filtered_replies if filtered_replies else [
            ReplyPart(text="음... 뭐라고 말해야 할지 모르겠어요", emotion="SHY", delay=2000)
        ]

        # 비용 메트릭 기록
        estimated_cost = _estimate_cost(model_id, total_prompt_tokens, total_completion_tokens)
        record_event(
            "llm_usage",
            room_id=room_id or "",
            character_id=character_id or "",
            payload={
                "model": model_id,
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": total_completion_tokens,
                "total_tokens": total_prompt_tokens + total_completion_tokens,
                "estimated_cost_usd": round(estimated_cost, 6),
                "llm_calls": llm_call_count,
                "complexity": complexity,
                "finetuned": bool(finetuned_model and finetuned_model not in ("gpt-4o", "gpt-4.1", LLM_MODEL_BASE)),
            },
        )

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

        return result, affinity_delta

    except Exception as e:
        # 병렬 호감도 분석 태스크가 남아있으면 정리
        if affinity_task is not None and not affinity_task.done():
            affinity_task.cancel()
        logger.error(f"LLM 호출 실패: {e}")
        return [ReplyPart(
            text="앗, 잠깐 멍해졌어요... 다시 말해줄래요?",
            emotion="SURPRISED",
            delay=2000
        )], 0


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
            max_tokens=600
        )

        content = response.choices[0].message.content or ""

        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(content[start:end])
                diary = data.get("diary", "").strip() or content.strip()
                emotion = data.get("emotion", "NEUTRAL")
                valid_emotions = {"NEUTRAL", "HAPPY", "SHY", "SAD", "ANGRY", "SURPRISED", "LOVE", "PLAYFUL", "WORRIED", "TOUCHED"}
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
        )

        content = response.choices[0].message.content or ""
        valid_emotions = {
            "NEUTRAL", "HAPPY", "SHY", "SAD", "ANGRY",
            "SURPRISED", "LOVE", "PLAYFUL", "WORRIED", "TOUCHED",
        }

        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                data = json.loads(content[start:end])
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
    valid_emotions = {"NEUTRAL", "HAPPY", "SHY", "SAD", "ANGRY", "SURPRISED", "LOVE", "PLAYFUL", "WORRIED", "TOUCHED"}

    # 1. markdown 코드블록 제거
    content = re.sub(r'```json?\s*', '', content)
    content = re.sub(r'```\s*', '', content)
    content = content.strip()

    # 2. JSON 배열 추출 시도
    try:
        start = content.find("[")
        end = content.rfind("]") + 1
        if start >= 0 and end > start:
            json_str = content[start:end]
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
