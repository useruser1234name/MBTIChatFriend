"""PostgreSQL helpers for backend state stores."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterable, Optional
import logging

from .config import DATABASE_URL

logger = logging.getLogger(__name__)

try:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.types.json import Json

    _PSYCOPG_AVAILABLE = True
except ImportError:
    psycopg = None
    dict_row = None
    Json = None
    _PSYCOPG_AVAILABLE = False


def postgres_enabled() -> bool:
    return bool(DATABASE_URL and _PSYCOPG_AVAILABLE)


@contextmanager
def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured")
    if not _PSYCOPG_AVAILABLE:
        raise RuntimeError("psycopg is not installed")

    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_postgres_schema() -> None:
    """Create required tables if PostgreSQL is configured."""
    if not postgres_enabled():
        if DATABASE_URL and not _PSYCOPG_AVAILABLE:
            logger.warning("DATABASE_URL is set but psycopg is not installed.")
        else:
            logger.info("DATABASE_URL not set. PostgreSQL stores are disabled.")
        return

    ddl_statements = [
        """
        CREATE TABLE IF NOT EXISTS story_state (
            room_id TEXT PRIMARY KEY,
            character_id TEXT NOT NULL DEFAULT '',
            chapter TEXT NOT NULL DEFAULT '',
            current_goal TEXT NOT NULL DEFAULT '',
            unresolved_hook TEXT NOT NULL DEFAULT '',
            promise TEXT NOT NULL DEFAULT '',
            trust_score INTEGER NOT NULL DEFAULT 0,
            last_callback_at_turn INTEGER NOT NULL DEFAULT 0,
            last_callback_key TEXT NOT NULL DEFAULT '',
            turn_count INTEGER NOT NULL DEFAULT 0,
            next_hook TEXT NOT NULL DEFAULT '',
            next_goal TEXT NOT NULL DEFAULT '',
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS diary_entries (
            id BIGSERIAL PRIMARY KEY,
            room_id TEXT NOT NULL,
            character_id TEXT NOT NULL DEFAULT '',
            diary_date DATE NOT NULL,
            diary_text TEXT NOT NULL,
            emotion TEXT NOT NULL DEFAULT 'NEUTRAL',
            next_hook TEXT NOT NULL DEFAULT '',
            next_goal TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (room_id, character_id, diary_date)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS metric_events (
            id BIGSERIAL PRIMARY KEY,
            event_type TEXT NOT NULL,
            room_id TEXT,
            character_id TEXT,
            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_metric_events_created_at
        ON metric_events(created_at DESC)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_metric_events_event_type
        ON metric_events(event_type)
        """,
        """
        CREATE TABLE IF NOT EXISTS conversation_memory (
            id BIGSERIAL PRIMARY KEY,
            memory_key TEXT NOT NULL UNIQUE,
            summary TEXT NOT NULL DEFAULT '',
            facts JSONB NOT NULL DEFAULT '[]'::jsonb,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_conversation_memory_key
        ON conversation_memory(memory_key)
        """,
        """
        CREATE TABLE IF NOT EXISTS response_feedback (
            id BIGSERIAL PRIMARY KEY,
            room_id TEXT NOT NULL,
            character_id TEXT NOT NULL DEFAULT '',
            message_id TEXT NOT NULL,
            feedback_type TEXT NOT NULL,
            feedback_detail TEXT DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_response_feedback_character
        ON response_feedback(character_id, created_at DESC)
        """,
    ]

    with get_conn() as conn:
        with conn.cursor() as cur:
            for ddl in ddl_statements:
                cur.execute(ddl)

    logger.info("PostgreSQL schema initialized.")


def execute(query: str, params: Optional[Iterable[Any]] = None) -> None:
    if not postgres_enabled():
        return
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params or ()))


def fetchone(query: str, params: Optional[Iterable[Any]] = None) -> Optional[dict]:
    if not postgres_enabled():
        return None
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params or ()))
            return cur.fetchone()


def fetchall(query: str, params: Optional[Iterable[Any]] = None) -> list[dict]:
    if not postgres_enabled():
        return []
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params or ()))
            return list(cur.fetchall())


def to_jsonb(value: Any) -> Any:
    if Json is None:
        return value
    return Json(value)
