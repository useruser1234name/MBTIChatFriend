"""관계 히스토리 + 기억 앨범 API 모듈.
UX-B 안현우 + UI-C 정수아 설계 (5차 회의 합의).
캐릭터 투자감 강화 → 이탈률 감소 핵심 기능.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from datetime import date, datetime, timezone
from typing import Optional

from .postgres import fetchall, fetchone, execute, postgres_enabled
from .postgres_async import get_async_db

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------

def _extract_nouns(text: str) -> list[str]:
    """간단한 한국어/영어 명사 추출 (형태소 분석기 없이).

    2글자 이상의 한글 어절과 영어 단어를 추출한다.
    라이브러리 의존성 없이 동작하는 경량 구현.
    """
    # 한글 2글자 이상 토큰
    ko_tokens = re.findall(r"[가-힣]{2,}", text)
    # 영문 2글자 이상 토큰
    en_tokens = re.findall(r"[A-Za-z]{2,}", text)
    # 불용어 (조사·어미 형태로 빈번히 등장하는 단어 제거)
    stopwords = {
        "그게", "이게", "저게", "것도", "거야", "거지", "거든", "있어", "없어",
        "하면", "하고", "이랑", "그냥", "아니", "맞아", "정말", "너무", "진짜",
        "좀더", "이제", "다시", "근데", "그래", "에서", "으로", "부터", "까지",
        "이랑", "와서", "해서", "해도", "해야", "했어", "했는", "한거", "한것",
        "the", "a", "an", "is", "are", "was", "were", "and", "or", "but",
        "to", "of", "in", "on", "at", "it", "be", "do", "go",
    }
    tokens = [t for t in ko_tokens + en_tokens if t not in stopwords]
    return tokens


# ---------------------------------------------------------------------------
# 공개 API 함수
# ---------------------------------------------------------------------------


async def get_relationship_summary(room_id: str, character_id: str) -> dict:
    """관계 히스토리 요약 반환.

    반환 필드:
    - total_messages: 총 대화 메시지 수 (chat_turn 이벤트 기준)
    - total_sessions: 총 대화 세션 수 (날짜 기준)
    - days_together: 첫 대화 이후 경과 일수
    - affinity_journey: 호감도 변화 이력 [(날짜, 레벨)]
    - top_topics: 자주 언급된 키워드 top-5
    - first_chat_date: 첫 대화 날짜 (ISO 문자열)
    """
    if not postgres_enabled():
        return _empty_summary()

    # ── 총 메시지 수 & 첫 대화 날짜 ──
    usage_row = fetchone(
        """
        SELECT
            COUNT(*) AS total_messages,
            MIN(created_at) AS first_chat_at
        FROM api_usage
        WHERE room_id = %s
          AND (%s = '' OR character_id = %s)
        """,
        (room_id, character_id, character_id),
    )
    total_messages: int = int((usage_row or {}).get("total_messages") or 0)
    first_chat_at: Optional[datetime] = (usage_row or {}).get("first_chat_at")

    # ── 총 세션 수 (날짜 기준 고유일) ──
    session_row = fetchone(
        """
        SELECT COUNT(DISTINCT created_at::date) AS total_sessions
        FROM api_usage
        WHERE room_id = %s
          AND (%s = '' OR character_id = %s)
        """,
        (room_id, character_id, character_id),
    )
    total_sessions: int = int((session_row or {}).get("total_sessions") or 0)

    # ── 경과 일수 ──
    days_together = 0
    first_chat_date_str = ""
    if first_chat_at:
        if first_chat_at.tzinfo is None:
            first_chat_at = first_chat_at.replace(tzinfo=timezone.utc)
        delta = datetime.now(tz=timezone.utc) - first_chat_at
        days_together = max(0, delta.days)
        first_chat_date_str = first_chat_at.date().isoformat()

    # ── 호감도 변화 이력 (chat_turn 이벤트 payload.affinity_delta 누적) ──
    affinity_rows = fetchall(
        """
        SELECT
            created_at::date AS event_date,
            SUM((payload->>'affinity_delta')::int) AS daily_delta
        FROM metric_events
        WHERE event_type = 'chat_turn'
          AND room_id = %s
          AND (%s = '' OR character_id = %s)
          AND payload ? 'affinity_delta'
        GROUP BY created_at::date
        ORDER BY created_at::date ASC
        """,
        (room_id, character_id, character_id),
    )

    affinity_journey: list[tuple[str, int]] = []
    running_level = 1
    for row in affinity_rows:
        delta_val = int(row.get("daily_delta") or 0)
        running_level = max(1, min(5, running_level + delta_val))
        event_date = row.get("event_date")
        date_str = event_date.isoformat() if isinstance(event_date, date) else str(event_date)
        affinity_journey.append((date_str, running_level))

    # ── top-5 토픽 (diary_entries 텍스트 명사 추출) ──
    diary_rows = fetchall(
        """
        SELECT diary_text
        FROM diary_entries
        WHERE room_id = %s
          AND (%s = '' OR character_id = %s)
        ORDER BY created_at DESC
        LIMIT 30
        """,
        (room_id, character_id, character_id),
    )
    all_tokens: list[str] = []
    for row in diary_rows:
        text = row.get("diary_text") or ""
        all_tokens.extend(_extract_nouns(text))

    top_topics = [word for word, _ in Counter(all_tokens).most_common(5)]

    return {
        "total_messages": total_messages,
        "total_sessions": total_sessions,
        "days_together": days_together,
        "affinity_journey": affinity_journey,
        "top_topics": top_topics,
        "first_chat_date": first_chat_date_str,
    }


def _empty_summary() -> dict:
    return {
        "total_messages": 0,
        "total_sessions": 0,
        "days_together": 0,
        "affinity_journey": [],
        "top_topics": [],
        "first_chat_date": "",
    }


async def save_memory_moment(
    room_id: str,
    character_id: str,
    user_id: str,
    message_text: str,
    moment_type: str = "special",
    user_note: str = "",
) -> dict:
    """특별한 순간을 기억 앨범에 저장.

    moment_type: "special" | "funny" | "touching"
    """
    if not postgres_enabled():
        return {"status": "skipped", "reason": "postgres_disabled"}

    # moment_type 유효성 검사
    valid_types = {"special", "funny", "touching"}
    if moment_type not in valid_types:
        moment_type = "special"

    execute(
        """
        INSERT INTO memory_moments
            (room_id, character_id, user_id, message_text, moment_type, user_note)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (room_id, character_id, user_id or "", message_text, moment_type, user_note or ""),
    )
    logger.info(
        "기억 앨범 저장: room_id=%s character_id=%s type=%s",
        room_id, character_id, moment_type,
    )
    # 30일 리텐션 투자 이벤트 기록 (6차 — DATA-B 신예린 설계)
    db = get_async_db()
    await db.record_investment_event(
        room_id=room_id,
        event_type="memory_saved",
        character_id=character_id,
        payload={"moment_type": moment_type},
    )
    return {"status": "saved"}


async def get_memory_album(room_id: str, character_id: str) -> list[dict]:
    """저장된 기억 앨범 조회.

    최신순 정렬, 최대 200개.
    """
    if not postgres_enabled():
        return []

    rows = fetchall(
        """
        SELECT
            id,
            room_id,
            character_id,
            user_id,
            message_text,
            moment_type,
            user_note,
            created_at
        FROM memory_moments
        WHERE room_id = %s
          AND (%s = '' OR character_id = %s)
        ORDER BY created_at DESC
        LIMIT 200
        """,
        (room_id, character_id, character_id),
    )

    result = []
    for row in rows:
        created_at = row.get("created_at")
        created_at_str = (
            created_at.isoformat() if isinstance(created_at, datetime) else str(created_at or "")
        )
        result.append(
            {
                "id": row.get("id"),
                "room_id": row.get("room_id", ""),
                "character_id": row.get("character_id", ""),
                "user_id": row.get("user_id", ""),
                "message_text": row.get("message_text", ""),
                "moment_type": row.get("moment_type", "special"),
                "user_note": row.get("user_note", ""),
                "created_at": created_at_str,
            }
        )
    return result
