"""대화 기억 서비스 - PostgreSQL 영속화 + 인메모리 캐시 패턴"""

import asyncio
import json
import logging
from collections import OrderedDict
from typing import Dict, List, Optional

from openai import AsyncOpenAI

from .config import OPENAI_API_KEY, LLM_MODEL_SIMPLE
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

# 캐시 최대 크기
_MAX_SUMMARIES = 200
_MAX_MEMORIES = 200

def _evict_if_needed() -> None:
    """캐시 크기가 MAX를 초과하면 가장 오래된 항목(FIFO) 제거"""
    while len(_conversation_summaries) > _MAX_SUMMARIES:
        _conversation_summaries.popitem(last=False)
    while len(_character_memories) > _MAX_MEMORIES:
        _character_memories.popitem(last=False)


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


async def _load_from_db(key: str, fallback_keys: Optional[list[str]] = None) -> None:
    """PostgreSQL에서 캐시로 로드 (cold start 시) - async"""
    if not postgres_enabled():
        return
    if key in _conversation_summaries:
        return  # 이미 캐시에 있음

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
        _evict_if_needed()
        return


async def _save_to_db(key: str) -> None:
    """인메모리 캐시 → PostgreSQL 영속화 - async"""
    if not postgres_enabled():
        return
    summary = _conversation_summaries.get(key, "")
    facts = _character_memories.get(key, [])
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
            max_tokens=500
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
            max_tokens=300
        )
        content = response.choices[0].message.content or ""

        # JSON 배열 파싱 시도
        start = content.find("[")
        end = content.rfind("]") + 1
        if start >= 0 and end > start:
            data = json.loads(content[start:end])
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
            existing_keys = {f["key"] for f in existing if isinstance(f, dict)}
            merged = list(existing) + [
                f for f in new_facts if f["key"] not in existing_keys
            ]
            # 핵심 정보는 절대 제거하지 않음
            core = [f for f in merged if isinstance(f, dict) and f.get("key") in _CORE_FACT_KEYS]
            non_core = [f for f in merged if isinstance(f, dict) and f.get("key") not in _CORE_FACT_KEYS]
            max_non_core = max(0, 15 - len(core))
            _character_memories[key] = core + (non_core[-max_non_core:] if max_non_core > 0 else [])
            await _save_to_db(key)
            _evict_if_needed()
            logger.info(f"핵심 정보 업데이트 [{key}]: +{len(new_facts)}개")

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
        )
        content = response.choices[0].message.content or ""

        start = content.find("[")
        end = content.rfind("]") + 1
        if start < 0 or end <= start:
            return []

        episodes = json.loads(content[start:end])
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


async def build_memory_context(
    character_name: str,
    nickname: str,
    *,
    user: Optional[dict] = None,
    room_id: str = "",
    character_id: str = "",
) -> str:
    """프롬프트에 포함할 기억 컨텍스트 생성 (캐릭터 시점)"""
    summary = await get_existing_summary(
        character_name,
        nickname,
        user=user,
        room_id=room_id,
        character_id=character_id,
    )
    facts = await get_existing_facts(
        character_name,
        nickname,
        user=user,
        room_id=room_id,
        character_id=character_id,
    )

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
