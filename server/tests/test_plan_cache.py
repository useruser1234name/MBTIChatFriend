"""P3: SubscriptionManager 플랜 캐시(60초 TTL) 테스트.

get_plan_async가 DB fetch(_fetch_plan_async)를 몇 번 호출하는지 카운팅하는
목으로 캐시 히트/무효화/TTL 만료 동작을 검증한다. 실제 DB 없이도 검증
가능하도록 SubscriptionManager._fetch_plan_async(내부 private 헬퍼, P3에서
캐시와 분리하기 위해 신설)만 monkeypatch한다.
"""

import pytest

from app.subscription import Plan, SubscriptionManager


@pytest.mark.asyncio
async def test_get_plan_async_caches_within_ttl(monkeypatch):
    """같은 uid를 TTL 내에 두 번 조회하면 DB fetch는 1회만 발생해야 한다."""
    mgr = SubscriptionManager()
    calls: list[str] = []

    async def _fake_fetch(user_id: str) -> Plan:
        calls.append(user_id)
        return Plan.PREMIUM

    monkeypatch.setattr(mgr, "_fetch_plan_async", _fake_fetch)

    plan1 = await mgr.get_plan_async("uid-1")
    plan2 = await mgr.get_plan_async("uid-1")

    assert plan1 == Plan.PREMIUM
    assert plan2 == Plan.PREMIUM
    assert len(calls) == 1, "두 번째 조회는 캐시 히트라 fetch가 다시 발생하면 안 됨"


@pytest.mark.asyncio
async def test_invalidate_plan_cache_forces_refetch(monkeypatch):
    """invalidate_plan_cache 호출 후 재조회하면 fetch가 다시 발생해야 한다."""
    mgr = SubscriptionManager()
    calls: list[str] = []

    async def _fake_fetch(user_id: str) -> Plan:
        calls.append(user_id)
        return Plan.FREE

    monkeypatch.setattr(mgr, "_fetch_plan_async", _fake_fetch)

    await mgr.get_plan_async("uid-2")
    await mgr.get_plan_async("uid-2")
    assert len(calls) == 1

    mgr.invalidate_plan_cache("uid-2")
    await mgr.get_plan_async("uid-2")

    assert len(calls) == 2, "무효화 후 재조회 시 fetch가 다시 발생해야 함"


@pytest.mark.asyncio
async def test_invalidate_plan_cache_is_noop_for_unknown_uid(monkeypatch):
    """캐시에 없는 uid를 무효화해도 예외 없이 안전하게 넘어가야 한다."""
    mgr = SubscriptionManager()
    mgr.invalidate_plan_cache("never-cached-uid")  # 예외 없이 통과하면 성공


@pytest.mark.asyncio
async def test_get_plan_async_refetches_after_ttl_expiry(monkeypatch):
    """TTL(60초)이 지나면 캐시가 만료되어 fetch가 다시 발생해야 한다."""
    mgr = SubscriptionManager()
    calls: list[str] = []

    async def _fake_fetch(user_id: str) -> Plan:
        calls.append(user_id)
        return Plan.FREE

    monkeypatch.setattr(mgr, "_fetch_plan_async", _fake_fetch)

    await mgr.get_plan_async("uid-3")
    assert len(calls) == 1

    # 캐시 타임스탬프를 TTL(60s) 밖으로 되돌려 만료를 시뮬레이션
    cached_plan, cached_at = mgr._plan_cache["uid-3"]
    mgr._plan_cache["uid-3"] = (cached_plan, cached_at - 61.0)

    await mgr.get_plan_async("uid-3")
    assert len(calls) == 2, "TTL 만료 후에는 캐시를 신뢰하지 않고 다시 fetch해야 함"


@pytest.mark.asyncio
async def test_plan_cache_clears_entirely_when_over_capacity(monkeypatch):
    """최대 엔트리(1000) 초과 시 전체 clear 정책을 검증(간이 스텁으로 상한을 낮춤)."""
    mgr = SubscriptionManager()

    async def _fake_fetch(user_id: str) -> Plan:
        return Plan.FREE

    monkeypatch.setattr(mgr, "_fetch_plan_async", _fake_fetch)
    monkeypatch.setattr("app.subscription._PLAN_CACHE_MAX_ENTRIES", 2)

    await mgr.get_plan_async("uid-a")
    await mgr.get_plan_async("uid-b")
    assert len(mgr._plan_cache) == 2

    # 3번째 신규 uid 조회 시 상한(2) 도달 → 전체 clear 후 자신만 다시 채워짐
    await mgr.get_plan_async("uid-c")
    assert set(mgr._plan_cache.keys()) == {"uid-c"}
