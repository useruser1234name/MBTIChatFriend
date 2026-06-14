"""FCM 엔드포인트 IDOR 방지 회귀 테스트.

배경: /fcm/register, /fcm/send가 클라이언트가 보낸 user_id를 토큰 uid와
대조하지 않아, 인증된 사용자가 타인에게 푸시를 발송하거나(스팸/피싱)
타인 user_id에 자기 토큰을 등록(하이재킹)할 수 있었다.

수정: require_auth_always로 전환해 REQUIRE_AUTH 설정과 무관하게 항상 인증을 요구하고,
토큰 uid를 강제한다. register는 uid 귀속, send는 본인 대상만 허용.
미인증 요청은 401로 거부된다(이전엔 req.user_id를 신뢰하던 IDOR 분기 존재).
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth_middleware import require_auth_always
from app.routers import fcm as fcm_router


def _make_client(auth_uid):
    """auth_uid로 인증된 격리 앱 TestClient. auth_uid=None이면 인증 의존성을 오버라이드하지
    않아 require_auth_always가 실제로 실행되며 미인증(401) 분기를 검증한다."""
    app = FastAPI()
    app.state.limiter = fcm_router.limiter
    app.include_router(fcm_router.router)
    if auth_uid:
        app.dependency_overrides[require_auth_always] = lambda: {"uid": auth_uid}
    return TestClient(app)


def test_send_to_other_user_is_forbidden(monkeypatch):
    """인증된 alice가 bob을 대상으로 발송 시 403."""
    monkeypatch.setattr(fcm_router, "get_token", lambda uid: "tok")
    sent = {}
    monkeypatch.setattr(
        fcm_router, "send_push_notification",
        lambda **kw: sent.update(kw) or True,
    )
    client = _make_client("alice")
    resp = client.post("/api/v1/fcm/send", json={"user_id": "bob", "body": "hi"})
    assert resp.status_code == 403, resp.text
    assert not sent, "타인 대상 발송이 차단되지 않고 실제로 전송됨"


def test_send_to_self_succeeds(monkeypatch):
    """인증된 alice가 본인 대상으로 발송 시 성공."""
    monkeypatch.setattr(fcm_router, "get_token", lambda uid: f"tok:{uid}")
    sent = {}
    monkeypatch.setattr(
        fcm_router, "send_push_notification",
        lambda **kw: sent.update(kw) or True,
    )
    client = _make_client("alice")
    resp = client.post("/api/v1/fcm/send", json={"user_id": "alice", "body": "hi"})
    assert resp.status_code == 200, resp.text
    assert sent.get("token") == "tok:alice"


def test_register_binds_to_token_uid_not_client(monkeypatch):
    """인증된 alice가 user_id=bob으로 등록 시도해도 alice에 귀속되어야 한다."""
    registered = {}
    monkeypatch.setattr(
        fcm_router, "register_token",
        lambda uid, token: registered.update(uid=uid, token=token),
    )
    client = _make_client("alice")
    resp = client.post(
        "/api/v1/fcm/register", json={"user_id": "bob", "token": "mytok"}
    )
    assert resp.status_code == 200, resp.text
    assert registered["uid"] == "alice", "클라이언트 user_id(bob)가 강제 무시되지 않음"


def test_unauthenticated_register_is_rejected(monkeypatch):
    """미인증 요청은 401로 거부되어야 한다 (req.user_id로 타인 토큰 등록 차단).

    이전 IDOR: REQUIRE_AUTH=false에서 user=None → req.user_id를 그대로 신뢰해
    임의 uid에 공격자 토큰을 등록할 수 있었다. require_auth_always로 봉합됨.
    """
    registered = {}
    monkeypatch.setattr(
        fcm_router, "register_token",
        lambda uid, token: registered.update(uid=uid, token=token),
    )
    client = _make_client(None)  # 인증 의존성 미오버라이드 → 실제 require_auth_always 실행
    resp = client.post(
        "/api/v1/fcm/register", json={"user_id": "victim", "token": "attacker_tok"}
    )
    assert resp.status_code == 401, resp.text
    assert not registered, "미인증 요청인데 토큰이 등록됨 (IDOR 미봉합)"


def test_unauthenticated_send_is_rejected(monkeypatch):
    """미인증 요청은 401로 거부되어야 한다 (임의 uid 대상 푸시 발송 차단)."""
    monkeypatch.setattr(fcm_router, "get_token", lambda uid: f"tok:{uid}")
    sent = {}
    monkeypatch.setattr(
        fcm_router, "send_push_notification",
        lambda **kw: sent.update(kw) or True,
    )
    client = _make_client(None)
    resp = client.post("/api/v1/fcm/send", json={"user_id": "victim", "body": "spam"})
    assert resp.status_code == 401, resp.text
    assert not sent, "미인증 요청인데 푸시가 발송됨 (IDOR 미봉합)"
