"""대화 기억 서비스 - 이전 대화를 요약하여 장기 기억 제공"""

import json
import logging
from typing import Dict, List, Optional

from openai import AsyncOpenAI

from .config import OPENAI_API_KEY
from .models import HistoryMessage

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# 캐릭터별 대화 요약 저장 (서버 메모리 기반, 실서비스에서는 DB 사용 권장)
_conversation_summaries: Dict[str, str] = {}

# 캐릭터별 기억할 핵심 정보
_character_memories: Dict[str, List[str]] = {}

SUMMARY_PROMPT = """아래는 AI 캐릭터와 사용자 간의 이전 대화 내용이야.
이 대화를 간결하게 요약해줘. 반드시 다음 정보를 포함해:

1. **사용자에 대해 알게 된 것**: 이름, 취미, 좋아하는 것, 싫어하는 것, 직업, 고민 등
2. **대화에서 있었던 중요한 사건**: 약속, 감정적 순간, 함께한 활동
3. **관계 진행 상황**: 두 사람의 분위기가 어떻게 변했는지
4. **캐릭터가 사용자에게 한 약속이나 언급한 것**
5. **감정적 분위기 변화**: 대화 시작과 끝에서 분위기가 어떻게 달라졌는지
6. **사용자가 자주 언급하는 주제**: 최대 3개 정리
7. **마지막 대화의 핵심 맥락**: 다음 대화에서 이어갈 수 있는 포인트

요약은 한국어로, 4~6문장으로 작성해. 캐릭터 시점으로 기억하는 것처럼 써줘.
이전 요약과 중복되는 내용은 제거하고 새로운 정보 위주로 작성해.
JSON이나 특수 포맷 없이 자연스러운 한국어 문장으로만 작성해."""

EXTRACT_FACTS_PROMPT = """아래 대화에서 사용자에 대한 핵심 정보만 추출해줘.
예: 이름, 나이, 직업, 취미, 좋아하는 것, 싫어하는 것, 고민, 특징 등

형식: 각 사실을 한 줄씩, "-" 로 시작
이미 알고 있는 정보와 중복되면 제외.
새로운 사실이 없으면 "없음" 이라고만 써.

이미 알고 있는 정보:
{known_facts}

대화 내용:
{conversation}"""


def _build_conversation_text(history: List[HistoryMessage]) -> str:
    """대화 히스토리를 텍스트로 변환"""
    lines = []
    for msg in history:
        role = "사용자" if msg.role == "user" else "캐릭터"
        lines.append(f"{role}: {msg.content}")
    return "\n".join(lines)


def get_memory_key(character_name: str, nickname: str) -> str:
    """캐릭터+사용자 조합 키"""
    return f"{character_name}_{nickname}"


def get_existing_summary(character_name: str, nickname: str) -> str:
    """기존 요약 가져오기"""
    key = get_memory_key(character_name, nickname)
    return _conversation_summaries.get(key, "")


def get_existing_facts(character_name: str, nickname: str) -> List[str]:
    """기존 핵심 정보 가져오기"""
    key = get_memory_key(character_name, nickname)
    return _character_memories.get(key, [])


async def summarize_conversation(
    character_name: str,
    nickname: str,
    conversation_history: List[HistoryMessage],
) -> str:
    """대화 내용을 요약하여 저장하고 반환"""
    if not client or len(conversation_history) < 4:
        return get_existing_summary(character_name, nickname)

    key = get_memory_key(character_name, nickname)
    existing = _conversation_summaries.get(key, "")

    conv_text = _build_conversation_text(conversation_history)

    prompt = SUMMARY_PROMPT
    if existing:
        prompt += f"\n\n이전 요약:\n{existing}\n\n위 요약을 참고하되, 새 대화 내용도 반영해서 통합 요약을 작성해."

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": conv_text}
            ],
            temperature=0.3,
            max_tokens=300
        )
        summary = response.choices[0].message.content or ""
        _conversation_summaries[key] = summary.strip()
        logger.info(f"대화 요약 갱신 [{key}]: {summary[:50]}...")
        return summary.strip()
    except Exception as e:
        logger.error(f"대화 요약 실패: {e}")
        return existing


async def extract_facts(
    character_name: str,
    nickname: str,
    conversation_history: List[HistoryMessage],
) -> List[str]:
    """대화에서 사용자에 대한 핵심 정보 추출"""
    if not client or len(conversation_history) < 2:
        return get_existing_facts(character_name, nickname)

    key = get_memory_key(character_name, nickname)
    existing = _character_memories.get(key, [])
    known = "\n".join(f"- {f}" for f in existing) if existing else "없음"
    conv_text = _build_conversation_text(conversation_history)

    prompt = EXTRACT_FACTS_PROMPT.format(
        known_facts=known,
        conversation=conv_text
    )

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=200
        )
        content = response.choices[0].message.content or ""

        if "없음" in content and len(content) < 10:
            return existing

        new_facts = [
            line.strip().lstrip("- ").strip()
            for line in content.split("\n")
            if line.strip().startswith("-") and len(line.strip()) > 3
        ]

        if new_facts:
            # 중복 제거 후 합치기 (최대 15개)
            all_facts = existing + [f for f in new_facts if f not in existing]
            _character_memories[key] = all_facts[-15:]
            logger.info(f"핵심 정보 업데이트 [{key}]: +{len(new_facts)}개")

        return _character_memories.get(key, existing)
    except Exception as e:
        logger.error(f"핵심 정보 추출 실패: {e}")
        return existing


def build_memory_context(character_name: str, nickname: str) -> str:
    """프롬프트에 포함할 기억 컨텍스트 생성 (캐릭터 시점)"""
    summary = get_existing_summary(character_name, nickname)
    facts = get_existing_facts(character_name, nickname)

    parts = []
    if summary:
        parts.append(f"## 이전 대화에서 기억하는 것 (내 시점)\n{summary}")
    if facts:
        facts_text = "\n".join(f"- {f}" for f in facts)
        parts.append(f"## {nickname}에 대해 아는 것\n이 정보를 대화에서 자연스럽게 활용해.\n{facts_text}")

    return "\n\n".join(parts)
