"""Lightweight metrics/event logger backed by PostgreSQL."""

from __future__ import annotations

from typing import Any, Optional
import logging

from .postgres import execute, postgres_enabled, to_jsonb

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
