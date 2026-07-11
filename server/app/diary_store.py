"""Night diary persistence backed by PostgreSQL."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from .postgres import fetchone, postgres_enabled


def night_bucket_date(client_local_hour: Optional[int], now_utc: Optional[datetime] = None) -> date:
    """Map night time (22:00~04:59) into one logical diary day bucket."""
    now = now_utc or datetime.now(timezone.utc).replace(tzinfo=None)
    bucket = now.date()

    if client_local_hour is None:
        return bucket

    if 0 <= client_local_hour <= 4:
        return bucket - timedelta(days=1)
    return bucket


def has_night_diary(room_id: str, character_id: str, diary_date: date) -> bool:
    if not postgres_enabled():
        return False
    row = fetchone(
        """
        SELECT id
        FROM diary_entries
        WHERE room_id = %s AND character_id = %s AND diary_date = %s
        LIMIT 1
        """,
        (room_id, character_id or "", diary_date),
    )
    return row is not None


def save_night_diary(
    room_id: str,
    character_id: str,
    diary_date: date,
    diary_text: str,
    emotion: str,
    next_hook: str = "",
    next_goal: str = "",
) -> bool:
    if not postgres_enabled():
        return False

    row = fetchone(
        """
        INSERT INTO diary_entries (
            room_id, character_id, diary_date, diary_text, emotion, next_hook, next_goal
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (room_id, character_id, diary_date) DO NOTHING
        RETURNING id
        """,
        (
            room_id,
            character_id or "",
            diary_date,
            diary_text,
            emotion or "NEUTRAL",
            next_hook or "",
            next_goal or "",
        ),
    )
    return row is not None
