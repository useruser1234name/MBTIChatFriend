"""라우터 하드닝 테스트 (S-4 rate limit, S-5 내부상태 인증).

- community/billing/fcm 라우터에 limiter 인스턴스 존재 (rate limit)
- circuit-status 엔드포인트에 인증 의존성 존재 (내부 상태 노출 방지)
"""


def test_community_router_has_limiter():
    """community.py에 limiter 인스턴스가 있다."""
    import app.routers.community as community_mod
    assert hasattr(community_mod, "limiter"), "community.py에 limiter 없음"


def test_billing_router_has_limiter():
    """billing.py에 limiter 인스턴스가 있다."""
    import app.routers.billing as billing_mod
    assert hasattr(billing_mod, "limiter"), "billing.py에 limiter 없음"


def test_fcm_router_has_limiter():
    """fcm.py에 limiter 인스턴스가 있다."""
    import app.routers.fcm as fcm_mod
    assert hasattr(fcm_mod, "limiter"), "fcm.py에 limiter 없음"


def test_circuit_status_requires_auth():
    """circuit_status 엔드포인트에 인증(require_auth_always) 의존성이 있다."""
    import inspect
    from app.routers.health import circuit_status

    sig = inspect.signature(circuit_status)
    assert "user" in sig.parameters, "circuit_status에 user 파라미터(인증) 없음"
