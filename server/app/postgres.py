"""PostgreSQL helpers - async (asyncpg) + sync (psycopg) fallback."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Iterable, Optional

import asyncio

from .config import DATABASE_URL, DB_POOL_MIN_SIZE, DB_POOL_MAX_SIZE

logger = logging.getLogger(__name__)

# ── asyncpg (비동기, 프로덕션 권장) ──────────────────────────

_pool = None

try:
    import asyncpg
    _ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    _ASYNCPG_AVAILABLE = False

# ── psycopg (동기, 폴백) ────────────────────────────────────

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
    return bool(DATABASE_URL and (_ASYNCPG_AVAILABLE or _PSYCOPG_AVAILABLE))


# ── 비동기 커넥션 풀 관리 ────────────────────────────────────

async def init_async_pool(min_size: int | None = None, max_size: int | None = None) -> None:
    """asyncpg 커넥션 풀 초기화. 서버 시작 시 호출."""
    global _pool
    if not DATABASE_URL or not _ASYNCPG_AVAILABLE:
        logger.info("asyncpg not available, will use sync psycopg fallback.")
        return

    _min = min_size if min_size is not None else DB_POOL_MIN_SIZE
    _max = max_size if max_size is not None else DB_POOL_MAX_SIZE
    try:
        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=_min,
            max_size=_max,
            command_timeout=30,
        )
        logger.info(f"asyncpg pool created (min={_min}, max={_max})")
    except Exception as e:
        logger.error(f"Failed to create asyncpg pool: {e}")
        _pool = None


async def close_async_pool() -> None:
    """asyncpg 커넥션 풀 종료. 서버 종료 시 호출."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("asyncpg pool closed")


def _async_pool_ready() -> bool:
    return _pool is not None


def get_postgres_health() -> dict[str, Any]:
    if not DATABASE_URL:
        return {"status": "disabled", "mode": "none", "drivers": {"asyncpg": _ASYNCPG_AVAILABLE, "psycopg": _PSYCOPG_AVAILABLE}}

    if _async_pool_ready():
        return {"status": "ready", "mode": "async_pool", "drivers": {"asyncpg": _ASYNCPG_AVAILABLE, "psycopg": _PSYCOPG_AVAILABLE}}

    if _PSYCOPG_AVAILABLE:
        return {"status": "degraded", "mode": "sync_fallback", "drivers": {"asyncpg": _ASYNCPG_AVAILABLE, "psycopg": _PSYCOPG_AVAILABLE}}

    return {"status": "error", "mode": "unavailable", "drivers": {"asyncpg": _ASYNCPG_AVAILABLE, "psycopg": _PSYCOPG_AVAILABLE}}


# ── 쿼리 형식 변환 ────────────────────────────────────────────


import re as _re

_PG_PLACEHOLDER_RE = _re.compile(r"\$(\d+)")


def _asyncpg_to_psycopg(query: str) -> str:
    """asyncpg 플레이스홀더($1, $2, ...) → psycopg 플레이스홀더(%s)로 변환."""
    return _PG_PLACEHOLDER_RE.sub("%s", query)


# ── 비동기 쿼리 API ──────────────────────────────────────────

async def async_execute(query: str, *args: Any) -> str:
    """비동기 쿼리 실행 (INSERT/UPDATE/DELETE). asyncpg → psycopg 폴백.

    쿼리는 asyncpg 형식($1, $2)으로 작성하고, psycopg 폴백 시 자동 변환.
    """
    if not postgres_enabled():
        return ""

    if _async_pool_ready():
        async with _pool.acquire() as conn:
            return await conn.execute(query, *args)

    # 폴백: asyncpg($1) → psycopg(%s) 변환 후 동기 실행
    converted = _asyncpg_to_psycopg(query)
    await asyncio.to_thread(execute, converted, args if args else None)
    return ""


async def async_fetchone(query: str, *args: Any) -> Optional[dict]:
    """비동기 단일 행 조회."""
    if not postgres_enabled():
        return None

    if _async_pool_ready():
        async with _pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    converted = _asyncpg_to_psycopg(query)
    return await asyncio.to_thread(fetchone, converted, args if args else None)


async def async_fetchall(query: str, *args: Any) -> list[dict]:
    """비동기 다중 행 조회."""
    if not postgres_enabled():
        return []

    if _async_pool_ready():
        async with _pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(r) for r in rows]

    converted = _asyncpg_to_psycopg(query)
    return await asyncio.to_thread(fetchall, converted, args if args else None)


# ── 동기 API (기존 호환, 스키마 초기화 등) ────────────────────

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
        if DATABASE_URL and not (_PSYCOPG_AVAILABLE or _ASYNCPG_AVAILABLE):
            logger.warning("DATABASE_URL is set but no PostgreSQL driver installed.")
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
            user_id TEXT,
            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        # 기존 테이블에 user_id 컬럼 추가 (이미 존재하면 무시)
        """
        ALTER TABLE metric_events ADD COLUMN IF NOT EXISTS user_id TEXT
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
        """
        CREATE TABLE IF NOT EXISTS fcm_tokens (
            user_id TEXT PRIMARY KEY,
            token TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_story_state_character_id
        ON story_state(character_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_diary_entries_character_id
        ON diary_entries(character_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_diary_entries_room_id
        ON diary_entries(room_id)
        """,
    ]

    if not _PSYCOPG_AVAILABLE:
        logger.error(
            "[DB 경고] psycopg가 설치되지 않아 스키마 초기화를 건너뜁니다. "
            "필요한 테이블이 존재하지 않으면 런타임 오류가 발생할 수 있습니다. "
            "`pip install psycopg[binary]`로 설치하거나 DB를 사전에 마이그레이션하세요."
        )
        return

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                for ddl in ddl_statements:
                    cur.execute(ddl)
        logger.info("PostgreSQL schema initialized.")
    except Exception as e:
        logger.error(
            f"[DB 경고] PostgreSQL 스키마 초기화 실패: {e}. "
            "서버가 시작되었지만 일부 기능이 동작하지 않을 수 있습니다."
        )


def execute(query: str, params: Optional[Iterable[Any]] = None) -> None:
    if not postgres_enabled() or not _PSYCOPG_AVAILABLE:
        return
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params or ()))


def fetchone(query: str, params: Optional[Iterable[Any]] = None) -> Optional[dict]:
    if not postgres_enabled() or not _PSYCOPG_AVAILABLE:
        return None
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params or ()))
            return cur.fetchone()


def fetchall(query: str, params: Optional[Iterable[Any]] = None) -> list[dict]:
    if not postgres_enabled() or not _PSYCOPG_AVAILABLE:
        return []
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params or ()))
            return list(cur.fetchall())


def to_jsonb(value: Any) -> Any:
    if Json is None:
        return value
    return Json(value)
