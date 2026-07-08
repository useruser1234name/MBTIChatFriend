"""2026-06-01 스프린트 보안/P0 수정 회귀 테스트.

DB·네트워크 의존 없이 검증 가능한 로직만 다룬다:
- postgres_async 플레이스홀더 변환 + asyncpg 호환 메서드 존재
- play_billing 검증 정책 (mock 허용 / production 거부)
- 라우터/앱 import 정상성 (인증 의존성 주입 후에도 부팅)
"""

import asyncio

import pytest


# ── P0-1: AsyncDatabase 플레이스홀더 변환 + 누락 메서드 ──────────────
def test_to_psycopg_converts_placeholders():
    from app.postgres_async import _to_psycopg

    assert _to_psycopg("SELECT * FROM t WHERE a = $1 AND b = $2") == (
        "SELECT * FROM t WHERE a = %s AND b = %s"
    )
    # $ 없는 쿼리는 그대로
    assert _to_psycopg("SELECT 1") == "SELECT 1"


def test_async_db_has_asyncpg_compat_methods():
    from app.postgres_async import AsyncDatabase

    db = AsyncDatabase()
    for name in ("execute", "fetchone", "fetchall", "fetchrow", "fetch", "fetchval"):
        assert hasattr(db, name), f"AsyncDatabase.{name} 누락"


def test_async_db_methods_safe_without_pool():
    """풀 미초기화 시 메서드들이 예외 없이 기본값 반환."""
    from app.postgres_async import AsyncDatabase

    db = AsyncDatabase()  # _pool is None

    async def run():
        assert await db.fetchone("SELECT 1") is None
        assert await db.fetchall("SELECT 1") == []
        assert await db.fetchrow("SELECT 1") is None
        assert await db.fetch("SELECT 1") == []
        assert await db.fetchval("SELECT 1") is None
        # execute는 None 반환(예외 없음)
        assert await db.execute("DELETE FROM t WHERE id = $1", 1) is None

    asyncio.run(run())


def test_fetchval_returns_first_column():
    from app.postgres_async import AsyncDatabase

    db = AsyncDatabase()

    async def fake_fetchone(query, *args):
        return {"count": 7, "other": 99}

    db.fetchone = fake_fetchone  # type: ignore

    async def run():
        assert await db.fetchval("SELECT COUNT(*) FROM t") == 7

    asyncio.run(run())


# ── P0-2: play_billing 영수증 검증 정책 ─────────────────────────────
def test_verify_purchase_rejects_empty_token():
    from app.play_billing import verify_subscription_purchase

    result = verify_subscription_purchase("premium_monthly", "")
    assert result.ok is False


def test_verify_purchase_dev_mock_allowed(monkeypatch):
    import app.play_billing as pb

    monkeypatch.setattr(pb, "_IS_PROD", False)
    monkeypatch.setattr(pb, "BILLING_ALLOW_MOCK", True)
    monkeypatch.setattr(pb, "GOOGLE_PLAY_PACKAGE_NAME", "")
    monkeypatch.setattr(pb, "GOOGLE_PLAY_SERVICE_ACCOUNT_JSON", "")

    result = pb.verify_subscription_purchase("premium_monthly", "token-abc")
    assert result.ok is True
    assert result.mock is True


def test_verify_purchase_production_refuses_when_unconfigured(monkeypatch):
    import app.play_billing as pb

    monkeypatch.setattr(pb, "_IS_PROD", True)
    monkeypatch.setattr(pb, "GOOGLE_PLAY_PACKAGE_NAME", "")
    monkeypatch.setattr(pb, "GOOGLE_PLAY_SERVICE_ACCOUNT_JSON", "")

    result = pb.verify_subscription_purchase("premium_monthly", "token-abc")
    assert result.ok is False  # production은 mock 우회 금지


def test_rtdn_production_refuses_without_audience(monkeypatch):
    import app.play_billing as pb

    monkeypatch.setattr(pb, "_IS_PROD", True)
    monkeypatch.setattr(pb, "PLAY_RTDN_AUDIENCE", "")

    result = pb.verify_rtdn_token("Bearer something")
    assert result.ok is False


# ── 라우터/앱 import 정상성 ─────────────────────────────────────────
def test_all_routers_import():
    """인증 의존성 추가 후에도 라우터 모듈 import 성공."""
    import importlib

    for mod in (
        "app.routers.billing",
        "app.routers.subscription",
        "app.routers.subscriptions",
        "app.routers.notifications",
        "app.routers.data",
        "app.routers.community",
        "app.routers.referral",
        "app.routers.chat",
    ):
        importlib.import_module(mod)


def test_internal_token_dependency_exists():
    from app.auth_middleware import require_internal_token

    assert callable(require_internal_token)
