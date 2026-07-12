"""비동기 PostgreSQL 연결 풀 — psycopg3 async 기반.

FastAPI async 이벤트 루프 블로킹 문제 해소 (2차 회의 W1-2 합의).
CTO-C 이서연 설계, ARCH-A 조성현 검증.

사용법:
    from .postgres_async import get_async_db

    async def some_handler():
        db = get_async_db()
        row = await db.fetchone("SELECT * FROM story_state WHERE room_id = $1", room_id)
"""

from __future__ import annotations

import logging
import re
from contextlib import asynccontextmanager
from typing import Any, Optional

from .config import DATABASE_URL, DATABASE_REPLICA_URL, DB_POOL_MIN_SIZE, DB_POOL_MAX_SIZE
from .circuit_breaker import CircuitOpenError, get_db_circuit

logger = logging.getLogger(__name__)

# 쿼리는 asyncpg 형식($1, $2, ...)으로 작성한다. psycopg3는 %s 위치 인자만
# 인식하므로 실행 직전에 변환한다. (동기 postgres.py와 동일한 규약)
_PG_PLACEHOLDER_RE = re.compile(r"\$(\d+)")


def _to_psycopg(query: str) -> str:
    """asyncpg 플레이스홀더($1, $2, ...) → psycopg 플레이스홀더(%s)로 변환."""
    return _PG_PLACEHOLDER_RE.sub("%s", query)

try:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg_pool import AsyncConnectionPool

    _PSYCOPG_ASYNC_AVAILABLE = True
except ImportError:
    psycopg = None
    dict_row = None
    AsyncConnectionPool = None
    _PSYCOPG_ASYNC_AVAILABLE = False


# pgBouncer 앞단 운영: 앱 레벨 풀은 소규모로 유지
class AsyncDatabase:
    """비동기 PostgreSQL 커넥션 풀 래퍼.

    FastAPI lifespan에서 initialize() 호출 후 사용.
    풀 크기: config.py의 DB_POOL_MIN_SIZE/DB_POOL_MAX_SIZE(기본 5/20)를 기본값으로
    사용한다(P4 — 이전에는 min=2/max=10으로 하드코딩되어 config 값을 무시했음).
    pgBouncer 앞단 운영 기준 — DATA-A 오재원 권고.
    """

    def __init__(self) -> None:
        self._pool: Optional[Any] = None

    @property
    def available(self) -> bool:
        return self._pool is not None

    async def initialize(
        self,
        dsn: str = "",
        min_size: int = DB_POOL_MIN_SIZE,
        max_size: int = DB_POOL_MAX_SIZE,
    ) -> None:
        """애플리케이션 시작 시 1회 호출."""
        if not _PSYCOPG_ASYNC_AVAILABLE:
            logger.warning(
                "psycopg / psycopg_pool 미설치 — 비동기 DB 풀 비활성화. "
                "`pip install psycopg[binary] psycopg-pool` 설치 필요."
            )
            return

        target_dsn = dsn or DATABASE_URL
        if not target_dsn:
            logger.info("DATABASE_URL 미설정 — 비동기 DB 풀 비활성화.")
            return

        try:
            self._pool = AsyncConnectionPool(
                conninfo=target_dsn,
                min_size=min_size,
                max_size=max_size,
                kwargs={"row_factory": dict_row},
                open=False,
            )
            await self._pool.open()
            logger.info(f"비동기 PostgreSQL 풀 초기화 완료 (min={min_size}, max={max_size})")
        except Exception as e:
            logger.error(f"비동기 PostgreSQL 풀 초기화 실패: {e}")
            self._pool = None

    async def close(self) -> None:
        """애플리케이션 종료 시 호출."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("비동기 PostgreSQL 풀 종료")

    async def execute(self, query: str, *args: Any) -> None:
        """INSERT / UPDATE / DELETE 등 결과 없는 쿼리 실행."""
        if not self._pool:
            return
        q = _to_psycopg(query)
        cb = get_db_circuit()
        try:
            async def _do() -> None:
                async with self._pool.connection() as conn:
                    await conn.execute(q, args)
            await cb.call(_do())
        except CircuitOpenError:
            logger.warning("[CB] postgres circuit OPEN — DB 호출 스킵")
        except Exception:
            raise

    async def fetchone(self, query: str, *args: Any) -> Optional[dict]:
        """단일 행 조회."""
        if not self._pool:
            return None
        q = _to_psycopg(query)
        cb = get_db_circuit()
        try:
            async def _do() -> Optional[dict]:
                async with self._pool.connection() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute(q, args)
                        return await cur.fetchone()
            return await cb.call(_do())
        except CircuitOpenError:
            logger.warning("[CB] postgres circuit OPEN — DB 호출 스킵")
            return None
        except Exception:
            raise

    async def fetchall(self, query: str, *args: Any) -> list[dict]:
        """다중 행 조회."""
        if not self._pool:
            return []
        q = _to_psycopg(query)
        cb = get_db_circuit()
        try:
            async def _do() -> list[dict]:
                async with self._pool.connection() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute(q, args)
                        return await cur.fetchall()
            return await cb.call(_do())
        except CircuitOpenError:
            logger.warning("[CB] postgres circuit OPEN — DB 호출 스킵")
            return []
        except Exception:
            raise

    async def execute_sequence(
        self, statements: list[tuple[str, tuple]],
    ) -> list[Optional[Exception]]:
        """여러 결과 없는 쿼리를 커넥션 1회 획득으로 순차 실행한다 (P8).

        execute()는 호출마다 풀에서 커넥션을 새로 획득/반환한다(왕복 N회).
        이 메서드는 커넥션을 한 번만 빌려 그 위에서 문장들을 순서대로
        실행해 왕복 횟수를 1회로 줄인다.

        **트랜잭션으로 묶지 않는다.** 문장 하나가 실패해도 나머지 문장이
        독립적으로 실행되어야 하므로(호출부의 기존 문장별 try/except와 동일한
        견고성), 각 문장 실행 직후 개별적으로 commit(성공) 또는 rollback(실패)
        한다 — Postgres는 트랜잭션 내부에서 한 문장이 실패하면 그 트랜잭션
        전체가 abort 상태가 되어 이후 문장까지 연쇄로 실패하므로, 문장마다
        즉시 commit/rollback해 그 상태가 다음 문장으로 전이되지 않게 한다.

        Returns: statements와 같은 길이·순서의 리스트. 성공한 문장은 None,
        실패한 문장은 발생한 Exception 객체를 담는다 — 예외를 여기서 삼키지
        않고 그대로 반환해 호출부가 문장별로 독립적인 로깅을 할 수 있게 한다.
        커넥션 자체를 획득할 수 없는 경우(풀 없음/서킷 오픈)는 모든 문장에
        동일한 예외를 채운 리스트를 반환한다(이 경우는 원래도 전 문장이
        똑같이 실패했을 상황이므로 독립성 훼손이 아니다).
        """
        if not self._pool:
            return [RuntimeError("async pool unavailable")] * len(statements)

        cb = get_db_circuit()
        try:
            async def _do() -> list[Optional[Exception]]:
                local_results: list[Optional[Exception]] = []
                async with self._pool.connection() as conn:
                    for query, args in statements:
                        q = _to_psycopg(query)
                        try:
                            await conn.execute(q, args)
                            await conn.commit()
                            local_results.append(None)
                        except Exception as stmt_exc:
                            await conn.rollback()
                            local_results.append(stmt_exc)
                return local_results
            return await cb.call(_do())
        except CircuitOpenError:
            logger.warning("[CB] postgres circuit OPEN — DB 호출 스킵")
            return [CircuitOpenError("postgres")] * len(statements)
        except Exception:
            raise

    # ── asyncpg 호환 별칭 ──────────────────────────────────────────
    # 라우터들이 asyncpg API(fetchrow/fetch/fetchval)를 기대하고 작성되어 있어
    # 누락 시 호출 즉시 AttributeError가 발생한다. dict_row 기반으로 매핑한다.
    async def fetchrow(self, query: str, *args: Any) -> Optional[dict]:
        """단일 행 조회 (asyncpg fetchrow 호환). fetchone과 동일."""
        return await self.fetchone(query, *args)

    async def fetch(self, query: str, *args: Any) -> list[dict]:
        """다중 행 조회 (asyncpg fetch 호환). fetchall과 동일."""
        return await self.fetchall(query, *args)

    async def fetchval(self, query: str, *args: Any) -> Any:
        """첫 행의 첫 컬럼 값 조회 (asyncpg fetchval 호환)."""
        row = await self.fetchone(query, *args)
        if not row:
            return None
        # dict_row 기준 첫 번째 값 반환
        for value in row.values():
            return value
        return None

    async def record_api_usage(
        self,
        room_id: str,
        character_id: str,
        model_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        endpoint: str = "chat",
    ) -> None:
        """OpenAI API 사용량 기록 — H-3 비용 메트릭 수집."""
        await self.execute(
            """
            INSERT INTO api_usage
                (room_id, character_id, model_id, prompt_tokens,
                 completion_tokens, total_tokens, endpoint)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            room_id,
            character_id,
            model_id,
            prompt_tokens,
            completion_tokens,
            prompt_tokens + completion_tokens,
            endpoint,
        )

    async def check_daily_budget(
        self,
        user_id: str,
        daily_limit: int = 50_000,
    ) -> tuple[bool, int]:
        """사용자의 오늘 토큰 사용량 확인.

        W2-6: PM-B 손민준 + ARCH-B 황인호 설계.
        room_id는 '{uid}:...' 형식으로 저장되므로 LIKE 매칭.
        집계(SUM) 쿼리이므로 읽기 복제본으로 라우팅.

        Returns:
            (is_within_budget, current_usage)
        """
        row = None
        try:
            async with get_async_db_read() as conn:
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute(
                        _to_psycopg(
                            """
                            SELECT COALESCE(SUM(total_tokens), 0) AS used
                            FROM api_usage
                            WHERE room_id LIKE $1
                              AND created_at >= CURRENT_DATE
                            """
                        ),
                        (f"{user_id}:%",),
                    )
                    row = await cur.fetchone()
        except Exception as exc:
            logger.warning("[check_daily_budget] 읽기 복제본 조회 실패, primary로 폴백: %s", exc)
            row = await self.fetchone(
                """
                SELECT COALESCE(SUM(total_tokens), 0) AS used
                FROM api_usage
                WHERE room_id LIKE $1
                  AND created_at >= CURRENT_DATE
                """,
                f"{user_id}:%",
            )
        used = int(row["used"]) if row else 0
        return used < daily_limit, used

    async def delete_conversation(self, room_id: str, character_id: str = "") -> int:
        """대화 기록 삭제 — GDPR/개인정보 보호 대응.

        Returns: 삭제된 메시지 수
        """
        if not self._pool:
            return 0

        deleted = 0
        async with self._pool.connection() as conn:
            # conversation_memory 삭제
            mem_key = f"{character_id}:{room_id}" if character_id else room_id
            await conn.execute(
                _to_psycopg("DELETE FROM conversation_memory WHERE memory_key LIKE $1"),
                (f"%{mem_key}%",),
            )

            # metric_events 삭제
            await conn.execute(
                _to_psycopg("DELETE FROM metric_events WHERE room_id = $1"),
                (room_id,),
            )

            # story_state 삭제
            await conn.execute(
                _to_psycopg("DELETE FROM story_state WHERE room_id = $1"),
                (room_id,),
            )

            # diary_entries 삭제
            if character_id:
                cur = await conn.execute(
                    _to_psycopg(
                        "DELETE FROM diary_entries WHERE room_id = $1 AND character_id = $2"
                    ),
                    (room_id, character_id),
                )
            else:
                cur = await conn.execute(
                    _to_psycopg("DELETE FROM diary_entries WHERE room_id = $1"),
                    (room_id,),
                )
            deleted = getattr(cur, "rowcount", 0) or 0

            # api_usage 삭제
            await conn.execute(
                _to_psycopg("DELETE FROM api_usage WHERE room_id = $1"),
                (room_id,),
            )

            # 삭제 이력 기록
            await conn.execute(
                _to_psycopg(
                    "INSERT INTO deletion_log (room_id, character_id) VALUES ($1, $2)"
                ),
                (room_id, character_id or ""),
            )

        return deleted

    async def record_investment_event(
        self,
        room_id: str,
        event_type: str,
        character_id: str = "",
        payload: dict | None = None,
    ) -> None:
        """30일 리텐션 코호트 투자 이벤트 기록 (6차 회의 — DATA-B 신예린 설계).

        투자 이벤트 유형:
            'memory_saved'        — 기억 앨범에 저장
            'character_customized'— 캐릭터 커스터마이징 1회 이상
            'affinity_level_3'    — 호감도 레벨 3 이상 달성

        metric_events 테이블에 기록. 30일 코호트 쿼리에서 활용.
        """
        import json as _json
        await self.execute(
            """
            INSERT INTO metric_events (event_type, room_id, character_id, payload)
            VALUES ($1, $2, $3, $4::jsonb)
            """,
            event_type,
            room_id,
            character_id,
            _json.dumps(payload or {}),
        )

    async def get_cohort_retention(
        self,
        days: int = 30,
    ) -> dict:
        """30일 리텐션 — 투자 사용자 vs 비투자 사용자 비교 쿼리.

        무거운 집계 쿼리(CTE 3개 + GROUP BY + JOIN)이므로 읽기 복제본으로 라우팅.

        Returns:
            {
                'invested_users': int,
                'invested_retained': int,
                'non_invested_users': int,
                'non_invested_retained': int,
                'invested_retention_rate': float,
                'non_invested_retention_rate': float,
            }
        """
        query = f"""
            WITH first_sessions AS (
                SELECT room_id, MIN(created_at) AS first_at
                FROM metric_events
                GROUP BY room_id
            ),
            invested AS (
                SELECT DISTINCT room_id
                FROM metric_events
                WHERE event_type IN ('memory_saved', 'character_customized', 'affinity_level_3')
            ),
            returned AS (
                SELECT DISTINCT room_id
                FROM metric_events me
                JOIN first_sessions fs ON me.room_id = fs.room_id
                WHERE me.created_at >= fs.first_at + INTERVAL '{days} days'
            )
            SELECT
                COUNT(DISTINCT fs.room_id) FILTER (WHERE i.room_id IS NOT NULL)     AS invested_users,
                COUNT(DISTINCT r.room_id) FILTER (WHERE i.room_id IS NOT NULL)      AS invested_retained,
                COUNT(DISTINCT fs.room_id) FILTER (WHERE i.room_id IS NULL)         AS non_invested_users,
                COUNT(DISTINCT r.room_id) FILTER (WHERE i.room_id IS NULL)          AS non_invested_retained
            FROM first_sessions fs
            LEFT JOIN invested i ON fs.room_id = i.room_id
            LEFT JOIN returned r ON fs.room_id = r.room_id
            WHERE fs.first_at <= NOW() - INTERVAL '{days} days'
            """
        row = None
        try:
            async with get_async_db_read() as conn:
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute(query)
                    row = await cur.fetchone()
        except Exception as exc:
            logger.warning("[get_cohort_retention] 읽기 복제본 조회 실패, 폴백 없음: %s", exc)
            return {}
        if not row:
            return {}
        inv = int(row["invested_users"] or 0)
        inv_ret = int(row["invested_retained"] or 0)
        non = int(row["non_invested_users"] or 0)
        non_ret = int(row["non_invested_retained"] or 0)
        return {
            "invested_users": inv,
            "invested_retained": inv_ret,
            "non_invested_users": non,
            "non_invested_retained": non_ret,
            "invested_retention_rate": round(inv_ret / inv, 3) if inv else 0.0,
            "non_invested_retention_rate": round(non_ret / non, 3) if non else 0.0,
        }


# 전역 싱글톤 인스턴스
_async_db = AsyncDatabase()


def get_async_db() -> AsyncDatabase:
    """애플리케이션 전역 비동기 DB 인스턴스 반환."""
    return _async_db


# 읽기 전용 풀 (SELECT 쿼리용, replica endpoint)
_read_pool: Optional[AsyncConnectionPool] = None


async def initialize_read_pool(dsn: str = None) -> None:
    """읽기 복제본 연결 풀 초기화. DATABASE_REPLICA_URL 없으면 스킵."""
    global _read_pool
    read_dsn = dsn or DATABASE_REPLICA_URL
    if not read_dsn:
        return
    _read_pool = AsyncConnectionPool(
        conninfo=read_dsn,
        min_size=1,
        max_size=5,
        open=False,
    )
    await _read_pool.open()


@asynccontextmanager
async def get_async_db_read():
    """읽기 전용 DB. replica 없으면 primary로 폴백.

    _read_pool과 _async_db._pool 모두 None이면 RuntimeError를 일으켜
    AttributeError 대신 명확한 오류 메시지를 제공한다.
    """
    pool = _read_pool if _read_pool is not None else _async_db._pool
    if pool is None:
        raise RuntimeError(
            "읽기 전용 DB 풀이 초기화되지 않았습니다. "
            "lifespan에서 init_async_pool()이 완료되었는지 확인하세요."
        )
    async with pool.connection() as conn:
        yield conn
