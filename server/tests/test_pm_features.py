"""PM 로드맵 기능 테스트 — 이벤트 로깅 + 밤 일기 FREE 해금.

DB 없이 검증 가능한 로직만 다룬다.
"""

import asyncio

import pytest


# ── 이벤트 로깅 ─────────────────────────────────────────────────────
def test_analytics_allowlist():
    from app import analytics_events as ae

    assert ae.is_allowed(ae.APP_OPEN)
    assert ae.is_allowed(ae.PURCHASE_COMPLETE)
    assert ae.is_allowed("paywall_shown")
    # 허용 목록 외는 거부
    assert not ae.is_allowed("arbitrary_spam_event")
    assert not ae.is_allowed("")


def test_events_router_imports():
    import importlib

    mod = importlib.import_module("app.routers.events")
    assert mod.router is not None


# ── 밤 일기 FREE 해금 ───────────────────────────────────────────────
def test_free_plan_night_diary_unlocked():
    from app.subscription import PLAN_LIMITS, Plan

    free = PLAN_LIMITS[Plan.FREE]
    assert free["night_diary"] is True  # PM 로드맵: FREE 해금
    assert free["night_diary_weekly_limit"] == 3

    premium = PLAN_LIMITS[Plan.PREMIUM]
    assert premium["night_diary"] is True
    assert premium["night_diary_weekly_limit"] == -1  # 무제한


def test_night_diary_limit_optimistic_when_no_db():
    """DB 미연결 시 밤 일기 생성 낙관적 허용."""
    from app.subscription import get_subscription_manager

    mgr = get_subscription_manager()

    async def run():
        allowed, _reason = await mgr.check_night_diary_limit("uid-without-db")
        assert allowed is True

    asyncio.run(run())


def test_subscription_status_model_has_weekly_limit():
    from app.models import SubscriptionStatusResponse

    resp = SubscriptionStatusResponse(night_diary=True, night_diary_weekly_limit=3)
    assert resp.night_diary_weekly_limit == 3
