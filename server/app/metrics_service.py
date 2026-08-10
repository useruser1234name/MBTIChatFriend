"""Lightweight metrics/event logger backed by PostgreSQL."""

from __future__ import annotations

from datetime import timedelta
from statistics import median
from typing import Any, Literal, Optional
import logging

from .postgres import execute, fetchall, postgres_enabled, to_jsonb

logger = logging.getLogger(__name__)


def record_event(
    event_type: str,
    room_id: str = "",
    character_id: str = "",
    user_id: str = "",
    payload: Optional[dict[str, Any]] = None,
) -> None:
    if not event_type:
        return
    if not postgres_enabled():
        return

    try:
        execute(
            """
            INSERT INTO metric_events (event_type, room_id, character_id, user_id, payload)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                event_type,
                room_id or None,
                character_id or None,
                user_id or None,
                to_jsonb(payload or {}),
            ),
        )
    except Exception as e:
        logger.warning(f"Failed to record metric event '{event_type}': {e}")


async def record_event_async(
    event_type: str,
    room_id: str = "",
    character_id: str = "",
    user_id: str = "",
    payload: Optional[dict[str, Any]] = None,
) -> None:
    """record_event의 비동기 버전 (P2: 핫패스 이벤트 루프 블로킹 해소).

    postgres_async.get_async_db()의 psycopg3 async 풀을 사용 — 스키마/컬럼은
    record_event와 완전히 동일(metric_events 테이블, 5개 컬럼). 지연 임포트로
    postgres_async를 가져온다(순환/기동 순서 회피 — chat_service.py의
    _record_usage 등과 동일한 관례).
    """
    if not event_type:
        return
    if not postgres_enabled():
        return

    try:
        # 지연 임포트: 순환/기동 순서 회피
        from .postgres_async import get_async_db

        db = get_async_db()
        if not db.available:
            return
        await db.execute(
            """
            INSERT INTO metric_events (event_type, room_id, character_id, user_id, payload)
            VALUES ($1, $2, $3, $4, $5)
            """,
            event_type,
            room_id or None,
            character_id or None,
            user_id or None,
            to_jsonb(payload or {}),
        )
    except Exception as e:
        logger.warning(f"Failed to record metric event (async) '{event_type}': {e}")


# ── 세션 통계 (P3, 2026-08-03 회의 합의) ──────────────────────────
#
# "세션"을 별도로 계측하지 않고, 이미 적재된 metric_events(chat_turn/app_open)
# 로부터 30분 gap 휴리스틱으로 파생한다: 같은 room_id(또는 user_id)의 연속
# 이벤트 간격이 SESSION_GAP_MINUTES를 넘으면 새 세션으로 취급한다.
#
# 이는 SQL의 LAG(created_at) OVER (PARTITION BY group_key ORDER BY created_at)로
# 이전 이벤트와의 시간차를 구해 세션 경계를 표시하는 윈도우 함수 로직과
# 동일한 알고리즘이다. 경계 판정 자체는 파이썬으로 구현했는데(DB 조회는
# 단순 ORDER BY 쿼리 하나), 이는 quality_service.py의
# check_diversity/_diversity_score_from_rows와 동일한 관례를 따른 것 —
# 실 PostgreSQL 없이도 경계 로직(29분=동일 세션, 31분=신규 세션 등)을
# 결정적으로 단위 테스트할 수 있게 DB 접근과 순수 계산을 분리한다.

SESSION_GAP_MINUTES = 30
_SESSION_EVENT_TYPES: tuple[str, ...] = ("chat_turn", "app_open")


def _split_into_sessions(
    rows: list[dict[str, Any]],
    gap_minutes: int = SESSION_GAP_MINUTES,
) -> list[dict[str, Any]]:
    """(group_key, created_at) 오름차순 정렬된 이벤트 로우를 세션 단위로 분할.

    rows 각 원소는 {"group_key": str, "event_type": str, "created_at": datetime}.
    같은 group_key 내에서 created_at 간격이 gap_minutes 초과 시, 또는
    group_key가 바뀌면 새 세션 시작. LAG() OVER (PARTITION BY group_key
    ORDER BY created_at) 방식과 동일한 결과를 낸다.

    Returns: [{"group_key", "start", "end", "turn_count", "event_count",
               "duration_seconds"}, ...]
    """
    if not rows:
        return []

    gap = timedelta(minutes=gap_minutes)
    sessions: list[dict[str, Any]] = []
    current: Optional[dict[str, Any]] = None
    prev_key = None
    prev_ts = None

    for row in rows:
        key = row["group_key"]
        ts = row["created_at"]
        is_new_session = (
            current is None
            or key != prev_key
            or (ts - prev_ts) > gap
        )
        if is_new_session:
            current = {
                "group_key": key,
                "start": ts,
                "end": ts,
                "turn_count": 0,
                "event_count": 0,
            }
            sessions.append(current)

        current["end"] = ts
        current["event_count"] += 1
        if row.get("event_type") == "chat_turn":
            current["turn_count"] += 1

        prev_key = key
        prev_ts = ts

    for s in sessions:
        s["duration_seconds"] = (s["end"] - s["start"]).total_seconds()

    return sessions


def _aggregate_session_stats(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    """세션 리스트로부터 세션 수 / 세션당 턴 수(평균·중앙값) / 세션 길이(평균) 산출."""
    if not sessions:
        return {
            "session_count": 0,
            "avg_turns_per_session": 0.0,
            "median_turns_per_session": 0.0,
            "avg_session_duration_seconds": 0.0,
        }

    turn_counts = [s["turn_count"] for s in sessions]
    durations = [s["duration_seconds"] for s in sessions]

    return {
        "session_count": len(sessions),
        "avg_turns_per_session": round(sum(turn_counts) / len(turn_counts), 2),
        "median_turns_per_session": round(median(turn_counts), 2),
        "avg_session_duration_seconds": round(sum(durations) / len(durations), 1),
    }


def get_session_stats(
    days: int = 7,
    group_by: Literal["room", "user"] = "room",
) -> dict[str, Any]:
    """기간 내 세션 통계(세션 수, 세션당 턴 수 평균/중앙값, 세션 길이 평균).

    group_by="room": room_id 기준 세션 분할(캐릭터별 방 단위 몰입도).
    group_by="user": user_id 기준 세션 분할(사용자 단위 앱 사용 패턴).
    이벤트 소스는 metric_events의 chat_turn/app_open (신규 계측 없음 — P3 스펙).
    """
    empty = {
        "group_by": group_by,
        "days": days,
        "session_count": 0,
        "avg_turns_per_session": 0.0,
        "median_turns_per_session": 0.0,
        "avg_session_duration_seconds": 0.0,
    }

    if group_by not in ("room", "user"):
        raise ValueError("group_by must be 'room' or 'user'")

    if not postgres_enabled():
        return empty

    group_col = "room_id" if group_by == "room" else "user_id"
    placeholders = ", ".join(["%s"] * len(_SESSION_EVENT_TYPES))

    rows = fetchall(
        f"""
        SELECT {group_col} AS group_key, event_type, created_at
        FROM metric_events
        WHERE event_type IN ({placeholders})
          AND {group_col} IS NOT NULL AND {group_col} != ''
          AND created_at >= NOW() - INTERVAL '1 day' * %s
        ORDER BY {group_col}, created_at
        LIMIT 200000
        """,
        tuple(_SESSION_EVENT_TYPES) + (days,),
    )

    sessions = _split_into_sessions(rows)
    stats = _aggregate_session_stats(sessions)
    return {"group_by": group_by, "days": days, **stats}
