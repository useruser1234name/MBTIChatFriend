"""PostgreSQL helpers for backend state stores.

동기(psycopg3) 레이어 — 기존 동기 코드와의 하위 호환 유지.
비동기 작업은 postgres_async.py의 AsyncDatabase 사용 권장.
"""

from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from typing import Any, Iterable, Optional
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
        # P0-4: user_id 컬럼 추가 — 인증 토큰에서 채워 클라 위조를 방지한다.
        """
        ALTER TABLE response_feedback ADD COLUMN IF NOT EXISTS user_id TEXT
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_response_feedback_character
        ON response_feedback(character_id, created_at DESC)
        """,
        # H-3: API 비용 메트릭 테이블 (2차 회의 합의 — DATA-A 오재원 제안)
        """
        CREATE TABLE IF NOT EXISTS api_usage (
            id BIGSERIAL PRIMARY KEY,
            room_id TEXT NOT NULL DEFAULT '',
            character_id TEXT NOT NULL DEFAULT '',
            model_id TEXT NOT NULL DEFAULT '',
            prompt_tokens INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0,
            total_tokens INTEGER NOT NULL DEFAULT 0,
            endpoint TEXT NOT NULL DEFAULT 'chat',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_api_usage_created_at
        ON api_usage(created_at DESC)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_api_usage_model
        ON api_usage(model_id, created_at DESC)
        """,
        # 대화 기록 삭제 추적 (GDPR/개인정보 삭제 이력)
        """
        CREATE TABLE IF NOT EXISTS deletion_log (
            id BIGSERIAL PRIMARY KEY,
            room_id TEXT NOT NULL,
            character_id TEXT NOT NULL DEFAULT '',
            deleted_by TEXT NOT NULL DEFAULT 'user',
            deleted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        # A/B 테스트 실험 결과 (3차 회의 합의 — DATA-B 신예린 설계)
        """
        CREATE TABLE IF NOT EXISTS ab_test_results (
            id BIGSERIAL PRIMARY KEY,
            experiment_id TEXT,
            variant TEXT,
            user_id TEXT,
            character_id TEXT,
            metric_name TEXT,
            metric_value FLOAT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_ab_test_results_experiment
        ON ab_test_results(experiment_id, created_at DESC)
        """,
        # 구독 플랜 관리 (5차 스프린트 — CTO-A 박지훈 + ARCH-C 오세진 설계)
        # 6차 스프린트: IAP 연동용 purchase_token, order_id, verified_at 컬럼 추가
        """
        CREATE TABLE IF NOT EXISTS user_subscriptions (
            id BIGSERIAL PRIMARY KEY,
            user_id TEXT NOT NULL,
            plan TEXT NOT NULL DEFAULT 'free',
            purchase_token TEXT DEFAULT '',
            order_id TEXT DEFAULT '',
            verified_at TIMESTAMPTZ,
            started_at TIMESTAMPTZ DEFAULT NOW(),
            expires_at TIMESTAMPTZ,
            rtdn_token TEXT DEFAULT '',
            trial_expires_at TIMESTAMPTZ,
            UNIQUE(user_id)
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user_id
        ON user_subscriptions(user_id)
        """,
        # 기억 앨범 — 캐릭터 투자감 강화 (5차 회의 합의 — UX-B 안현우 + UI-C 정수아)
        """
        CREATE TABLE IF NOT EXISTS memory_moments (
            id BIGSERIAL PRIMARY KEY,
            room_id TEXT NOT NULL,
            character_id TEXT NOT NULL,
            user_id TEXT,
            message_text TEXT,
            moment_type TEXT DEFAULT 'special',
            user_note TEXT DEFAULT '',
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_memory_moments_room
        ON memory_moments(room_id, character_id, created_at DESC)
        """,
        # 30일 리텐션 코호트 측정 — 투자 이벤트 인덱스 (6차 회의 합의 — DATA-B 신예린)
        # 투자 이벤트 유형: 'memory_saved', 'character_customized', 'affinity_level_3'
        """
        CREATE INDEX IF NOT EXISTS idx_metric_events_investment
        ON metric_events(event_type, room_id, created_at)
        WHERE event_type IN ('memory_saved', 'character_customized', 'affinity_level_3')
        """,
        # 사용자 학습 데이터 활용 opt-in 동의 (10차 회의 — 법무 전문가 김지은)
        # 명시적 opt-in, 기본값 False, 철회 시 익명화 처리
        """
        CREATE TABLE IF NOT EXISTS user_data_consent (
            id BIGSERIAL PRIMARY KEY,
            user_id TEXT NOT NULL,
            consented BOOLEAN NOT NULL DEFAULT FALSE,
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(user_id)
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_user_data_consent_user_id
        ON user_data_consent(user_id)
        """,
        # QS 충족 세션 종료 시 인앱 별점 + 피드백 수집
        """
        CREATE TABLE IF NOT EXISTS session_feedback (
            id          BIGSERIAL PRIMARY KEY,
            session_id  TEXT NOT NULL,
            room_id     TEXT NOT NULL,
            rating      SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
            text        TEXT,
            created_at  TIMESTAMPTZ DEFAULT now()
        )
        """,
        # P0-4: user_id 컬럼 추가 — 인증 토큰에서 채워 클라 위조를 방지한다.
        """
        ALTER TABLE session_feedback ADD COLUMN IF NOT EXISTS user_id TEXT
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_session_feedback_room
            ON session_feedback(room_id, created_at DESC)
        """,
        # 초대(레퍼럴) 코드 관리
        """
        CREATE TABLE IF NOT EXISTS referral_codes (
            code        TEXT PRIMARY KEY,
            inviter_id  TEXT NOT NULL,
            created_at  TIMESTAMPTZ DEFAULT now(),
            expires_at  TIMESTAMPTZ DEFAULT now() + INTERVAL '7 days',
            redeemed_by TEXT,
            redeemed_at TIMESTAMPTZ
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_referral_inviter ON referral_codes(inviter_id)
        """,
        # 커뮤니티 게시판 (18차 스프린트)
        """
        CREATE TABLE IF NOT EXISTS community_posts (
            id              BIGSERIAL PRIMARY KEY,
            user_id         TEXT NOT NULL,
            mbti            CHAR(4) NOT NULL,
            content         TEXT NOT NULL CHECK (char_length(content) <= 300),
            anonymous_name  TEXT NOT NULL,
            empathy_count   INT DEFAULT 0,
            created_at      TIMESTAMPTZ DEFAULT now(),
            deleted_at      TIMESTAMPTZ
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_community_mbti
            ON community_posts(mbti, created_at DESC)
            WHERE deleted_at IS NULL
        """,
        """
        CREATE TABLE IF NOT EXISTS community_empathies (
            post_id     BIGINT REFERENCES community_posts(id) ON DELETE CASCADE,
            user_id     TEXT NOT NULL,
            created_at  TIMESTAMPTZ DEFAULT now(),
            PRIMARY KEY (post_id, user_id)
        )
        """,
        # 커뮤니티 댓글 (20차 스프린트)
        """
        CREATE TABLE IF NOT EXISTS community_comments (
            id              BIGSERIAL PRIMARY KEY,
            post_id         BIGINT REFERENCES community_posts(id) ON DELETE CASCADE,
            user_id         TEXT NOT NULL,
            mbti            CHAR(4) NOT NULL,
            content         TEXT NOT NULL CHECK (char_length(content) <= 150),
            anonymous_name  TEXT NOT NULL,
            created_at      TIMESTAMPTZ DEFAULT now(),
            deleted_at      TIMESTAMPTZ
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_community_comments_post
            ON community_comments(post_id, created_at ASC)
            WHERE deleted_at IS NULL
        """,
        # 공감 알림 배치 큐 (20차 스프린트 — APScheduler 배치 발송용)
        """
        CREATE TABLE IF NOT EXISTS pending_empathy_notifications (
            id          BIGSERIAL PRIMARY KEY,
            post_id     BIGINT NOT NULL,
            author_id   TEXT NOT NULL,
            actor_name  TEXT NOT NULL,
            created_at  TIMESTAMPTZ DEFAULT now(),
            sent_at     TIMESTAMPTZ
        )
        """,
        # 댓글 수 캐싱 컬럼 (21차 스프린트)
        """
        ALTER TABLE community_posts ADD COLUMN IF NOT EXISTS comment_count INT DEFAULT 0
        """,
        # 댓글 수 자동 업데이트 트리거 (21차 스프린트)
        """
        CREATE OR REPLACE FUNCTION update_comment_count()
        RETURNS TRIGGER AS $$
        BEGIN
          IF TG_OP = 'INSERT' AND (NEW.deleted_at IS NULL) THEN
            UPDATE community_posts SET comment_count = comment_count + 1 WHERE id = NEW.post_id;
          ELSIF TG_OP = 'UPDATE' AND (NEW.deleted_at IS NOT NULL) AND (OLD.deleted_at IS NULL) THEN
            UPDATE community_posts SET comment_count = comment_count - 1 WHERE id = NEW.post_id;
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """,
        """
        CREATE OR REPLACE TRIGGER trg_community_comment_count
          AFTER INSERT OR UPDATE ON community_comments
          FOR EACH ROW EXECUTE FUNCTION update_comment_count()
        """,
        # 통합 알림 테이블 (21차 스프린트)
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id          BIGSERIAL PRIMARY KEY,
            user_id     TEXT NOT NULL,
            type        TEXT NOT NULL,
            title       TEXT NOT NULL,
            body        TEXT NOT NULL,
            is_read     BOOLEAN DEFAULT FALSE,
            created_at  TIMESTAMPTZ DEFAULT now()
        )
        """,
        # 알림 딥링크 컬럼 추가 (22차 스프린트)
        """
        ALTER TABLE notifications ADD COLUMN IF NOT EXISTS deep_link TEXT
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_notifications_user
            ON notifications(user_id, created_at DESC)
            WHERE is_read = FALSE
        """,
        # 커뮤니티 신고 기능 (25차 스프린트)
        """
        ALTER TABLE community_posts ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN DEFAULT FALSE
        """,
        # 고정 공지 기능 (29차 스프린트)
        """
        ALTER TABLE community_posts ADD COLUMN IF NOT EXISTS is_pinned BOOLEAN DEFAULT FALSE
        """,
        """
        CREATE TABLE IF NOT EXISTS post_reports (
            id          BIGSERIAL PRIMARY KEY,
            reporter_id TEXT NOT NULL,
            post_id     BIGINT REFERENCES community_posts(id),
            reason      TEXT NOT NULL,
            created_at  TIMESTAMPTZ DEFAULT now(),
            UNIQUE(reporter_id, post_id)
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_post_reports_post
            ON post_reports(post_id)
        """,
        """
        CREATE OR REPLACE FUNCTION check_post_reports()
        RETURNS TRIGGER AS $$
        BEGIN
          IF (SELECT COUNT(*) FROM post_reports WHERE post_id = NEW.post_id) >= 3 THEN
            UPDATE community_posts SET is_hidden = TRUE WHERE id = NEW.post_id;
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """,
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_trigger WHERE tgname = 'trg_post_reports'
          ) THEN
            CREATE TRIGGER trg_post_reports
              AFTER INSERT ON post_reports
              FOR EACH ROW EXECUTE FUNCTION check_post_reports();
          END IF;
        END;
        $$
        """,
        # 사용자 감정 일기 (32차 스프린트)
        # NOTE: 'diary_entries'는 캐릭터 시점 밤일기(room_id/diary_date/diary_text)로 이미
        # 정의되어 있다. 사용자 감정일기는 컬럼이 완전히 다르므로 별도 테이블로 분리한다.
        # (이전엔 동일 이름이라 IF NOT EXISTS로 무시되어 /diary/entries CRUD가 크래시했음.)
        """
        CREATE TABLE IF NOT EXISTS user_diary_entries (
            id BIGSERIAL PRIMARY KEY,
            user_id TEXT NOT NULL,
            content TEXT NOT NULL,
            emotion_tags TEXT[],
            created_at TIMESTAMPTZ DEFAULT NOW(),
            deleted_at TIMESTAMPTZ
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_user_diary_entries_user_id ON user_diary_entries(user_id)
        """,
        # FCM 토큰 저장소 (firebase_service가 참조하나 DDL이 누락되어 있었음)
        """
        CREATE TABLE IF NOT EXISTS fcm_tokens (
            user_id    TEXT PRIMARY KEY,
            token      TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        # 사용자 테이블 — 가입일/마지막 접속 추적, scheduler D+3/D+5/gratitude 쿼리용
        # push_enabled: FCM 수신 동의 여부 (기본 TRUE — 앱 최초 실행 시 upsert)
        # mbti_type: gratitude_day_push 메시지 개인화 (선택적, NULL 허용)
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id       TEXT PRIMARY KEY,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_active_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            push_enabled  BOOLEAN NOT NULL DEFAULT TRUE,
            mbti_type     TEXT
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_users_last_active
            ON users(last_active_at DESC)
        """,
        # 채팅 메시지 적재 테이블 — scheduler D+3/D+5 리텐션 알림 쿼리용
        # character_mbti: D+5 캐릭터 그리움 메시지 개인화에 사용
        # role: 'user' | 'assistant'
        """
        CREATE TABLE IF NOT EXISTS messages (
            id             BIGSERIAL PRIMARY KEY,
            user_id        TEXT NOT NULL,
            character_mbti TEXT NOT NULL DEFAULT '',
            role           TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
            content        TEXT NOT NULL,
            created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_messages_user_created
            ON messages(user_id, created_at DESC)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_messages_created
            ON messages(created_at DESC)
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
