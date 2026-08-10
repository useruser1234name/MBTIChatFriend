"""대화 기억 서비스 - PostgreSQL 영속화 + 인메모리 캐시 패턴"""

import asyncio
import json
import logging
import re
import time
from collections import OrderedDict
from typing import Dict, List, Optional

from openai import AsyncOpenAI

from .config import OPENAI_API_KEY, LLM_MODEL_SIMPLE
from .json_utils import extract_json_array
from .models import HistoryMessage
from .postgres import fetchone, execute, postgres_enabled, to_jsonb
from .scopes import build_legacy_memory_key, build_memory_key

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# 인메모리 캐시 (PostgreSQL 앞단 캐시 레이어) - OrderedDict로 FIFO eviction 지원
_conversation_summaries: OrderedDict[str, str] = OrderedDict()
_character_memories: OrderedDict[str, List[dict]] = OrderedDict()  # key-value 구조로 변경

# 절대 제거하면 안 되는 핵심 팩트 키
_CORE_FACT_KEYS = {"이름", "직업", "고민", "좋아하는것", "싫어하는것", "나이", "학교", "취미", "좋아하는 음식", "성격"}

_SENSITIVE_FACT_KEYS = {
    "비밀번호", "패스워드", "password", "주민등록번호", "주민번호",
    "카드번호", "신용카드", "계좌번호", "계좌", "주소", "전화번호",
    "휴대폰", "이메일", "email", "토큰", "api_key", "api key", "apikey",
}
_SENSITIVE_VALUE_PATTERNS = [
    re.compile(r"\b\d{2,3}-\d{3,4}-\d{4}\b"),
    re.compile(r"\b\d{6}-\d{7}\b"),
    re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
]

# 캐시 최대 크기
_MAX_SUMMARIES = 200
_MAX_MEMORIES = 200

# ── positive 캐시 TTL(2026-08-04 H2) ──────────────────────────────────────
# 배경: positive 캐시(_conversation_summaries/_character_memories)는 FIFO
# eviction 외에는 만료가 없어 영구였다. 그래서 (a) 다른 워커/프로세스가
# 대화를 삭제하거나 요약을 갱신해도 이 프로세스는 무기한 stale한 값을
# 프롬프트에 주입했고, (b) 삭제 경로가 캐시를 비워도 멀티 워커에서는
# 자기 워커만 비워졌다.
# 무효화가 아니라 "재검증"으로 푼다 — TTL이 지나면 다음 조회에서 DB를 한 번
# 다시 읽는다(캐시 미스 1회 수준의 TTFT 영향). 삭제 경로는 아래
# invalidate_memory_cache()로 즉시 비우고, TTL은 크로스 워커 안전망이다.
_POSITIVE_TTL_SECONDS = 300.0
_positive_loaded_at: Dict[str, float] = {}

# ── 네거티브 캐시(2026-08-03 P1-S4) ────────────────────────────────────────
# 배경: conversation_memory에 아직 행이 없는 방(= 첫 요약 이전의 모든 신규 방)은
# _load_from_db가 아무것도 캐싱하지 않아 매 턴 DB를 다시 조회했다. 그 조회 중
# 일부가 TTFT 직렬 경로에 있어 첫 토큰이 늦어졌다.
# "행 없음"도 기억하되, 다중 워커에서 다른 워커가 방금 저장한 요약을 오래 못 보는
# stale을 막기 위해 영구 캐시가 아니라 짧은 TTL로만 유지한다. 기존 positive 캐시
# (_conversation_summaries/_character_memories, FIFO eviction)와는 별도 dict라
# _MAX_SUMMARIES FIFO 정책과 충돌하지 않는다.
_NEGATIVE_TTL_SECONDS = 60.0
_MAX_NEGATIVE = 500
_negative_until: Dict[str, float] = {}


def _negative_cache_valid(key: str, now: float) -> bool:
    """key가 유효한 네거티브 마킹(=DB에 행 없음)을 갖고 있는지. 만료분은 즉시 정리."""
    until = _negative_until.get(key)
    if until is None:
        return False
    if until > now:
        return True
    _negative_until.pop(key, None)
    return False


def _mark_negative(key: str, now: float) -> None:
    _negative_until.pop(key, None)  # 재삽입으로 FIFO 순서 갱신
    _negative_until[key] = now + _NEGATIVE_TTL_SECONDS
    _prune_negative(now)


def _clear_negative(key: str) -> None:
    """요약/팩트가 저장되었으므로 '행 없음' 마킹을 즉시 해제."""
    _negative_until.pop(key, None)


def _prune_negative(now: float) -> None:
    if len(_negative_until) <= _MAX_NEGATIVE:
        return
    for expired in [k for k, until in _negative_until.items() if until <= now]:
        _negative_until.pop(expired, None)
    while len(_negative_until) > _MAX_NEGATIVE:
        _negative_until.pop(next(iter(_negative_until)))


def _positive_cache_valid(key: str, now: float) -> bool:
    """positive 캐시 항목이 존재하고 TTL 안에 있는지(= DB 재검증 불필요).

    타임스탬프가 없는 항목(예: 외부에서 직접 주입)은 만료로 간주해 다음 조회에서
    DB를 한 번 재검증한다 — stale을 오래 끌고 가는 것보다 안전한 기본값.
    """
    if key not in _conversation_summaries:
        return False
    loaded_at = _positive_loaded_at.get(key)
    if loaded_at is None:
        return False
    return (now - loaded_at) < _POSITIVE_TTL_SECONDS


def _touch_positive(key: str, now: Optional[float] = None) -> None:
    """positive 캐시 항목의 신선도 시각을 갱신."""
    _positive_loaded_at[key] = time.monotonic() if now is None else now


def _drop_positive(key: str) -> bool:
    """positive 캐시(요약/팩트/신선도)를 제거. 제거된 항목이 있으면 True."""
    removed = _conversation_summaries.pop(key, None) is not None
    removed = (_character_memories.pop(key, None) is not None) or removed
    _positive_loaded_at.pop(key, None)
    return removed


def _normalize_fact_key(key: str) -> str:
    return re.sub(r"\s+", "", (key or "").strip()).lower()


def _is_sensitive_fact(fact: dict) -> bool:
    key = str(fact.get("key", "")).strip()
    value = str(fact.get("value", "")).strip()
    normalized_key = _normalize_fact_key(key)
    if any(marker in normalized_key for marker in _SENSITIVE_FACT_KEYS):
        return True
    return any(pattern.search(value) for pattern in _SENSITIVE_VALUE_PATTERNS)


def merge_memory_facts(
    existing: List[dict],
    new_facts: List[dict],
    *,
    max_total: int = 15,
) -> List[dict]:
    """Merge memory facts, replacing stale values and skipping secrets."""
    merged_by_key: OrderedDict[str, dict] = OrderedDict()

    for fact in list(existing or []) + list(new_facts or []):
        if not isinstance(fact, dict):
            continue
        key = str(fact.get("key", "")).strip()
        value = str(fact.get("value", "")).strip()
        if not key or not value:
            continue
        cleaned = {"key": key, "value": value}
        if _is_sensitive_fact(cleaned):
            continue
        norm_key = _normalize_fact_key(key)
        if norm_key in merged_by_key:
            del merged_by_key[norm_key]
        merged_by_key[norm_key] = cleaned

    merged = list(merged_by_key.values())
    core = [f for f in merged if f.get("key") in _CORE_FACT_KEYS]
    non_core = [f for f in merged if f.get("key") not in _CORE_FACT_KEYS]
    max_non_core = max(0, max_total - len(core))
    return core + (non_core[-max_non_core:] if max_non_core > 0 else [])

def _evict_if_needed() -> None:
    """캐시 크기가 MAX를 초과하면 가장 오래된 항목(FIFO) 제거"""
    while len(_conversation_summaries) > _MAX_SUMMARIES:
        evicted_key, _ = _conversation_summaries.popitem(last=False)
        if evicted_key not in _character_memories:
            _positive_loaded_at.pop(evicted_key, None)
    while len(_character_memories) > _MAX_MEMORIES:
        evicted_key, _ = _character_memories.popitem(last=False)
        if evicted_key not in _conversation_summaries:
            _positive_loaded_at.pop(evicted_key, None)


SUMMARY_PROMPT = """아래는 AI 캐릭터와 사용자 간의 이전 대화 내용이야.
이 대화를 간결하게 요약해줘. 반드시 다음 정보를 포함해:

1. **사용자에 대해 알게 된 것**: 이름, 취미, 좋아하는 것, 싫어하는 것, 직업, 고민 등
2. **대화에서 있었던 중요한 사건**: 약속, 감정적 순간, 함께한 활동
3. **관계 진행 상황**: 두 사람의 분위기가 어떻게 변했는지
4. **캐릭터가 사용자에게 한 약속이나 언급한 것**
5. **감정적 분위기 변화**: 대화 시작과 끝에서 분위기가 어떻게 달라졌는지
6. **사용자가 자주 언급하는 주제**: 최대 3개 정리
7. **마지막 대화의 핵심 맥락**: 다음 대화에서 이어갈 수 있는 포인트

요약은 한국어로, 5~8문장으로 작성해. 캐릭터 시점으로 기억하는 것처럼 써줘.
이전 요약과 중복되는 내용은 제거하고 새로운 정보 위주로 작성해.
JSON이나 특수 포맷 없이 자연스러운 한국어 문장으로만 작성해."""

EXTRACT_FACTS_PROMPT = """아래 대화에서 사용자에 대한 핵심 정보만 추출해줘.
예: 이름, 나이, 직업, 취미, 좋아하는 것, 싫어하는 것, 고민, 특징 등

출력 형식 (JSON 배열만 출력, 다른 텍스트 없음):
[{{"key": "직업", "value": "대학생"}}, {{"key": "좋아하는 음식", "value": "라멘"}}]

이미 알고 있는 정보:
{known_facts}

이미 알고 있는 정보와 동일하거나 중복이면 제외.
새로운 사실이 없으면 빈 배열 [] 출력.
최대 5개까지만 추출.

대화 내용:
{conversation}"""


def _build_conversation_text(history: List[HistoryMessage]) -> str:
    """대화 히스토리를 텍스트로 변환"""
    lines = []
    for msg in history:
        role = "사용자" if msg.role == "user" else "캐릭터"
        lines.append(f"{role}: {msg.content}")
    return "\n".join(lines)


def get_memory_key(
    character_name: str = "",
    nickname: str = "",
    *,
    user: Optional[dict] = None,
    room_id: str = "",
    character_id: str = "",
) -> str:
    return build_memory_key(
        user=user,
        room_id=room_id,
        character_id=character_id,
        character_name=character_name,
        nickname=nickname,
    )


def _resolve_memory_keys(
    character_name: str = "",
    nickname: str = "",
    *,
    user: Optional[dict] = None,
    room_id: str = "",
    character_id: str = "",
) -> tuple[str, list[str]]:
    primary_key = get_memory_key(
        character_name,
        nickname,
        user=user,
        room_id=room_id,
        character_id=character_id,
    )
    fallback_keys: list[str] = []
    legacy_key = build_legacy_memory_key(character_name, nickname)
    if not user and not room_id and not character_id and legacy_key and legacy_key != primary_key:
        fallback_keys.append(legacy_key)
    return primary_key, fallback_keys


async def _load_from_db(key: str, fallback_keys: Optional[list[str]] = None) -> bool:
    """PostgreSQL에서 캐시로 로드 (cold start 시) - async

    Returns:
        True면 이번 호출이 DB 왕복 없이 처리됨(positive 캐시 히트 / 유효한 네거티브
        캐시 / postgres 비활성). False면 fetchone을 최소 1회 실행했다.

    H2(2026-08-04): positive 캐시 히트도 TTL(_POSITIVE_TTL_SECONDS)을 확인한다.
    만료된 항목은 조회 전에 버리고 DB를 다시 읽어, 다른 워커가 삭제/갱신한
    결과를 최대 TTL 이내에 반영한다. DB에도 행이 없으면(=삭제됨) 네거티브
    마킹으로 전환되어 삭제된 요약·팩트가 프롬프트에 다시 들어가지 않는다.
    """
    if not postgres_enabled():
        return True
    now = time.monotonic()
    if _positive_cache_valid(key, now):
        return True  # 이미 캐시에 있고 아직 신선함
    if key in _conversation_summaries:
        # 만료된 stale 항목 — 아래에서 재검증한다.
        _drop_positive(key)
    if _negative_cache_valid(key, now):
        return True  # DB에 행이 없다는 걸 최근에 확인함 — 재조회 생략

    candidate_keys = [key] + [candidate for candidate in (fallback_keys or []) if candidate]
    for candidate_key in candidate_keys:
        row = await asyncio.to_thread(
            fetchone,
            "SELECT summary, facts FROM conversation_memory WHERE memory_key = %s",
            (candidate_key,),
        )
        if not row:
            continue

        _conversation_summaries[key] = row.get("summary", "")
        facts_raw = row.get("facts", [])
        if isinstance(facts_raw, list):
            _character_memories[key] = facts_raw
        elif isinstance(facts_raw, str):
            try:
                _character_memories[key] = json.loads(facts_raw)
            except (json.JSONDecodeError, TypeError):
                _character_memories[key] = []
        else:
            _character_memories[key] = []
        _touch_positive(key, now)
        _clear_negative(key)
        _evict_if_needed()
        return False

    # 어떤 후보 키로도 행이 없음 → 짧은 TTL 동안 기억해 매 턴 재조회를 막는다.
    _mark_negative(key, now)
    return False


async def _save_to_db(key: str) -> None:
    """인메모리 캐시 → PostgreSQL 영속화 - async"""
    if not postgres_enabled():
        return
    summary = _conversation_summaries.get(key, "")
    facts = _character_memories.get(key, [])
    # 행이 생겼으므로 '행 없음' 마킹을 즉시 해제 — 저장 직후 조회가 새 값을 본다.
    _clear_negative(key)
    # 방금 이 워커가 쓴 값이 최신이므로 TTL 시계를 리셋한다(H2).
    _touch_positive(key)
    await asyncio.to_thread(
        execute,
        """
        INSERT INTO conversation_memory (memory_key, summary, facts, updated_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (memory_key) DO UPDATE SET
            summary = EXCLUDED.summary,
            facts = EXCLUDED.facts,
            updated_at = NOW()
        """,
        (key, summary, to_jsonb(facts)),
    )


async def get_existing_summary(
    character_name: str,
    nickname: str,
    *,
    user: Optional[dict] = None,
    room_id: str = "",
    character_id: str = "",
) -> str:
    """기존 요약 가져오기 (캐시 미스 시 DB 로드) - async"""
    key, fallback_keys = _resolve_memory_keys(
        character_name,
        nickname,
        user=user,
        room_id=room_id,
        character_id=character_id,
    )
    await _load_from_db(key, fallback_keys)
    return _conversation_summaries.get(key, "")


async def get_existing_facts(
    character_name: str,
    nickname: str,
    *,
    user: Optional[dict] = None,
    room_id: str = "",
    character_id: str = "",
) -> List[dict]:
    """기존 핵심 정보 가져오기 (key-value 구조) - async"""
    key, fallback_keys = _resolve_memory_keys(
        character_name,
        nickname,
        user=user,
        room_id=room_id,
        character_id=character_id,
    )
    await _load_from_db(key, fallback_keys)
    return _character_memories.get(key, [])


async def summarize_conversation(
    character_name: str,
    nickname: str,
    conversation_history: List[HistoryMessage],
    *,
    user: Optional[dict] = None,
    room_id: str = "",
    character_id: str = "",
) -> str:
    """대화 내용을 요약하여 저장하고 반환"""
    if not client or len(conversation_history) < 4:
        return await get_existing_summary(
            character_name,
            nickname,
            user=user,
            room_id=room_id,
            character_id=character_id,
        )

    key, fallback_keys = _resolve_memory_keys(
        character_name,
        nickname,
        user=user,
        room_id=room_id,
        character_id=character_id,
    )
    await _load_from_db(key, fallback_keys)
    existing = _conversation_summaries.get(key, "")

    conv_text = _build_conversation_text(conversation_history)

    prompt = SUMMARY_PROMPT
    if existing:
        prompt += f"\n\n이전 요약:\n{existing}\n\n위 요약을 참고하되, 새 대화 내용도 반영해서 통합 요약을 작성해."

    try:
        response = await client.chat.completions.create(
            model=LLM_MODEL_SIMPLE,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": conv_text}
            ],
            temperature=0.3,
            max_tokens=500,
            timeout=30,
        )
        summary = response.choices[0].message.content or ""
        _conversation_summaries[key] = summary.strip()
        await _save_to_db(key)
        _evict_if_needed()
        logger.info(f"대화 요약 갱신 [{key}]: {summary[:50]}...")
        return summary.strip()
    except Exception as e:
        logger.error(f"대화 요약 실패: {e}")
        return existing


async def extract_facts(
    character_name: str,
    nickname: str,
    conversation_history: List[HistoryMessage],
    *,
    user: Optional[dict] = None,
    room_id: str = "",
    character_id: str = "",
) -> List[dict]:
    """대화에서 사용자에 대한 핵심 정보 추출 (key-value 구조)"""
    if not client or len(conversation_history) < 2:
        return await get_existing_facts(
            character_name,
            nickname,
            user=user,
            room_id=room_id,
            character_id=character_id,
        )

    key, fallback_keys = _resolve_memory_keys(
        character_name,
        nickname,
        user=user,
        room_id=room_id,
        character_id=character_id,
    )
    await _load_from_db(key, fallback_keys)
    existing = _character_memories.get(key, [])
    known = "\n".join(
        f"- {f['key']}: {f['value']}" for f in existing if isinstance(f, dict)
    ) if existing else "없음"
    conv_text = _build_conversation_text(conversation_history)

    prompt = EXTRACT_FACTS_PROMPT.format(
        known_facts=known,
        conversation=conv_text
    )

    try:
        response = await client.chat.completions.create(
            model=LLM_MODEL_SIMPLE,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=300,
            timeout=30,
        )
        content = response.choices[0].message.content or ""

        # JSON 배열 파싱 시도
        json_str = extract_json_array(content)
        if json_str is not None:
            data = json.loads(json_str)
            new_facts = [
                {"key": item["key"], "value": item["value"]}
                for item in data
                if isinstance(item, dict) and item.get("key") and item.get("value")
            ]
        else:
            # fallback: 줄 기반 파싱 (이전 호환)
            new_facts = []
            for line in content.split("\n"):
                line = line.strip().lstrip("- ").strip()
                if line and len(line) > 3 and line != "없음":
                    if ": " in line:
                        k, v = line.split(": ", 1)
                        new_facts.append({"key": k.strip(), "value": v.strip()})

        if new_facts:
            _character_memories[key] = merge_memory_facts(existing, new_facts)
            await _save_to_db(key)
            _evict_if_needed()
            logger.info(
                "핵심 정보 업데이트 [%s]: extracted=%s stored=%s",
                key,
                len(new_facts),
                len(_character_memories[key]),
            )

        return _character_memories.get(key, existing)
    except Exception as e:
        logger.error(f"핵심 정보 추출 실패: {e}")
        return existing


EXTRACT_EPISODES_PROMPT = """아래 대화에서 감정적으로 의미 있는 에피소드를 추출해줘.

추출 대상:
- 감정이 크게 변한 순간 (기쁨→슬픔, 화남→감동 등)
- 서로의 약속이나 중요한 결심
- 함께 공유한 특별한 경험이나 이벤트
- 깊은 감정 교류가 있었던 대화 (고백, 위로, 격려 등)
- 중요한 정보를 처음 알게 된 순간

출력 형식 (JSON 배열만 출력):
[{{"text": "에피소드 설명 (1-2문장)", "emotion": "감정코드", "importance": 중요도(1-5), "topic": "주제"}}]

emotion: NEUTRAL | HAPPY | SHY | SAD | ANGRY | SURPRISED | LOVE | PLAYFUL | WORRIED | TOUCHED
importance: 1(사소) ~ 5(매우 중요)

에피소드가 없으면 빈 배열 [] 출력. 최대 3개까지만 추출."""


async def extract_episodes(
    character_name: str,
    nickname: str,
    conversation_history: "List[HistoryMessage]",
    character_id: str = "",
    room_id: str = "",
) -> list:
    """대화에서 감정적으로 의미 있는 에피소드 추출 → ChromaDB에 저장"""
    if not client or len(conversation_history) < 4:
        return []

    # 지연 임포트: 순환/기동 순서 회피
    from .vector_store import get_store

    conv_text = _build_conversation_text(conversation_history[-20:])

    try:
        response = await client.chat.completions.create(
            model=LLM_MODEL_SIMPLE,
            messages=[
                {"role": "system", "content": EXTRACT_EPISODES_PROMPT},
                {"role": "user", "content": f"캐릭터: {character_name}, 사용자: {nickname}\n\n{conv_text}"},
            ],
            temperature=0.3,
            max_tokens=500,
            timeout=30,
        )
        content = response.choices[0].message.content or ""

        json_str = extract_json_array(content)
        if json_str is None:
            return []

        episodes = json.loads(json_str)
        valid_episodes = [
            ep for ep in episodes
            if isinstance(ep, dict) and ep.get("text")
        ]

        scope_id = room_id.strip() or character_id.strip()
        if valid_episodes and scope_id:
            store = get_store()
            if store:
                store.upsert_episodes(scope_id, valid_episodes)

        logger.info(f"에피소드 추출 [{character_name}]: {len(valid_episodes)}개")
        return valid_episodes

    except Exception as e:
        logger.error(f"에피소드 추출 실패: {e}")
        return []


def is_memory_cached(
    character_name: str = "",
    nickname: str = "",
    *,
    user: Optional[dict] = None,
    room_id: str = "",
    character_id: str = "",
) -> bool:
    """다음 build_memory_context 호출이 DB 왕복 없이 처리되는지 (계측용, sync/무부하).

    True 조건: postgres 비활성 / positive 캐시 보유 / 유효한 네거티브 마킹 보유.
    turn_latency 이벤트의 t_memory_cache_hit이 이 값을 사용한다.
    """
    if not postgres_enabled():
        return True
    key, _ = _resolve_memory_keys(
        character_name,
        nickname,
        user=user,
        room_id=room_id,
        character_id=character_id,
    )
    now = time.monotonic()
    # H2: TTL이 지난 positive 항목은 다음 조회에서 DB를 재검증하므로 hit이 아니다
    # (_load_from_db의 판정과 정확히 같은 조건을 유지해 t_memory_cache_hit의
    #  의미 — "이번 턴이 DB 왕복 없이 처리됨" — 을 보존한다).
    if _positive_cache_valid(key, now):
        return True
    return _negative_cache_valid(key, now)


def invalidate_memory_cache(
    room_id: str = "",
    character_id: str = "",
    *,
    user: Optional[dict] = None,
    character_name: str = "",
    nickname: str = "",
) -> int:
    """대화 기억이 DB에서 삭제됐을 때 인메모리 캐시를 즉시 무효화한다(H2).

    배경(2026-08-04 점검 H2): postgres_async.delete_conversation은 DB만 지우고
    이 모듈의 캐시(_conversation_summaries/_character_memories/_negative_until)를
    건드리지 않았다. _load_from_db가 캐시 히트 시 조기 반환하므로, 프로세스가
    살아있는 동안 **삭제된 요약·팩트가 계속 프롬프트에 주입**됐다.

    삭제 범위는 delete_conversation과 맞춘다. DB 삭제가
    `memory_key LIKE '%{character_id}:{room_id}%'`(또는 `'%{room_id}%'`)이므로,
    캐시도 해석된 정확한 키에 더해 같은 fragment를 포함하는 캐시 키를 함께
    비운다(레거시 키·다른 스코프 표기까지 커버).

    Returns: 실제로 제거된 캐시 항목 수(요약/팩트/네거티브 마킹 합산 아님 —
             positive 항목 기준).
    """
    targets: set[str] = set()

    primary_key, fallback_keys = _resolve_memory_keys(
        character_name,
        nickname,
        user=user,
        room_id=room_id,
        character_id=character_id,
    )
    for candidate in [primary_key, *fallback_keys]:
        if candidate:
            targets.add(candidate)

    clean_room_id = (room_id or "").strip()
    clean_character_id = (character_id or "").strip()
    fragments = [
        fragment
        for fragment in (
            f"{clean_character_id}:{clean_room_id}" if (clean_character_id and clean_room_id) else "",
            clean_room_id,
        )
        if fragment
    ]
    if fragments:
        cached_keys = set(_conversation_summaries) | set(_character_memories) | set(_negative_until)
        for cached_key in cached_keys:
            if any(fragment in cached_key for fragment in fragments):
                targets.add(cached_key)

    removed = 0
    for target in targets:
        if _drop_positive(target):
            removed += 1
        _negative_until.pop(target, None)

    if targets:
        logger.info("기억 캐시 무효화: keys=%s removed=%s", len(targets), removed)
    return removed


async def build_memory_context(
    character_name: str,
    nickname: str,
    *,
    user: Optional[dict] = None,
    room_id: str = "",
    character_id: str = "",
) -> str:
    """프롬프트에 포함할 기억 컨텍스트 생성 (캐릭터 시점)

    P1-S4: summary/facts를 각각 로드해 fetchone을 2회 쓰던 것을 키 1회 해석 +
    _load_from_db 1회로 합쳤다(결과는 기존과 동치 — 두 로드가 같은 키를 조회했음).
    """
    key, fallback_keys = _resolve_memory_keys(
        character_name,
        nickname,
        user=user,
        room_id=room_id,
        character_id=character_id,
    )
    await _load_from_db(key, fallback_keys)
    summary = _conversation_summaries.get(key, "")
    facts = _character_memories.get(key, [])

    parts = []
    if summary:
        parts.append(f"## 이전 대화에서 기억하는 것 (내 시점)\n{summary}")
    if facts:
        facts_text = "\n".join(
            f"- {f['key']}: {f['value']}" for f in facts if isinstance(f, dict)
        )
        if facts_text:
            parts.append(f"## {nickname}에 대해 아는 것\n이 정보를 대화에서 자연스럽게 활용해.\n{facts_text}")

    return "\n\n".join(parts)
