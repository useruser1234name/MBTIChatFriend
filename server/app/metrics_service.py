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
    payload: Optional[dict[str, Any]] = None,
) -> None:
    if not event_type:
        return
    if not postgres_enabled():
        return

    try:
        execute(
            """
            INSERT INTO metric_events (event_type, room_id, character_id, payload)
            VALUES (%s, %s, %s, %s)
            """,
            (
                event_type,
                room_id or None,
                character_id or None,
                to_jsonb(payload or {}),
            ),
        )
    except Exception as e:
        logger.warning(f"Failed to record metric event '{event_type}': {e}")
