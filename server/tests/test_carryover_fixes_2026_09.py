"""2026-09-14 미비 작업 일괄 처리 — 리팩토링 이월 버그 백로그 + 점검 잔여 회귀 테스트.

대상:
- AsyncDatabase.execute가 statusmessage를 반환 → community 삭제의 "UPDATE 0" 403 분기 부활
- referral get_referral_stats 소유권 검사를 _assert_owner로 통일
- web_chat 업스트림 예외 원문 비노출
- /metrics/session-stats 내부 토큰 게이트
- FCM data payload에 notification_type 항상 포함 (C6 이월: Android 분기 계약)
- D5 잡이 character_mbti를 data로 전달
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException


# ── AsyncDatabase.execute → statusmessage ─────────────────────────────


class _FakeCursor:
    def __init__(self, status: str):
        self.statusmessage = status


class _FakeConn:
    def __init__(self, status: str):
        self._status = status
        self.executed: list[tuple[str, tuple]] = []

    async def execute(self, q, args):
        self.executed.append((q, args))
        return _FakeCursor(self._status)


class _FakePool:
    def __init__(self, status: str):
        self.conn = _FakeConn(status)

    @asynccontextmanager
    async def connection(self):
        yield self.conn


@pytest.mark.asyncio
async def test_async_execute_returns_statusmessage():
    from app.postgres_async import AsyncDatabase

    db = AsyncDatabase()
    db._pool = _FakePool("UPDATE 0")
    result = await db.execute("UPDATE t SET a = 1 WHERE id = $1", 7)
    assert result == "UPDATE 0"
    # $1 → %s 변환 + 인자 전달은 기존 계약 유지
    q, args = db._pool.conn.executed[0]
    assert "%s" in q and args == (7,)


@pytest.mark.asyncio
async def test_async_execute_without_pool_returns_none():
    from app.postgres_async import AsyncDatabase

    db = AsyncDatabase()
    assert await db.execute("UPDATE t SET a = 1") is None


# ── community 삭제: UPDATE 0 → 403 (이전엔 영구 데드 분기) ────────────


class _StatusDb:
    def __init__(self, status):
        self.status = status

    async def execute(self, query, *args):
        return self.status


@pytest.mark.asyncio
async def test_delete_post_raises_403_when_no_row_updated():
    from app.routers import community

    with pytest.raises(HTTPException) as exc:
        await community.delete_post(
            post_id=1, user_id="u1", user={"uid": "u1"}, db=_StatusDb("UPDATE 0")
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_delete_post_succeeds_when_row_updated():
    from app.routers import community

    result = await community.delete_post(
        post_id=1, user_id="u1", user={"uid": "u1"}, db=_StatusDb("UPDATE 1")
    )
    assert result is None


@pytest.mark.asyncio
async def test_delete_comment_raises_403_when_no_row_updated():
    from app.routers import community

    with pytest.raises(HTTPException) as exc:
        await community.delete_comment(
            post_id=1, comment_id=2, user_id="u1", user={"uid": "u1"}, db=_StatusDb("UPDATE 0")
        )
    assert exc.value.status_code == 403


# ── referral stats 소유권 (_assert_owner 통일) ─────────────────────────


@pytest.mark.asyncio
async def test_referral_stats_rejects_other_user():
    from app.routers import referral

    with pytest.raises(HTTPException) as exc:
        await referral.get_referral_stats(user_id="victim", user={"uid": "attacker"})
    assert exc.value.status_code == 403
    assert "본인의 현황만" in exc.value.detail


@pytest.mark.asyncio
async def test_referral_stats_rejects_unauthenticated():
    from app.routers import referral

    with pytest.raises(HTTPException) as exc:
        await referral.get_referral_stats(user_id="victim", user=None)
    assert exc.value.status_code == 403


# ── web_chat: 업스트림 예외 원문 비노출 ────────────────────────────────


@pytest.mark.asyncio
async def test_web_chat_does_not_leak_upstream_error_text(monkeypatch):
    from app.routers import web_chat
    from app.routers.web_chat import WebChatRequest, send_web_chat

    secret = "sk-SECRET-KEY-FRAGMENT https://internal.example/upstream"

    class _Completions:
        async def create(self, **kwargs):
            raise RuntimeError(secret)

    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

    monkeypatch.setattr(web_chat, "client", _Client())

    with pytest.raises(HTTPException) as exc:
        await send_web_chat(WebChatRequest(message="안녕", mbti="INFP", persona="테스트"))
    assert exc.value.status_code == 502
    assert "SECRET" not in exc.value.detail
    assert "internal.example" not in exc.value.detail


# ── /metrics/session-stats 내부 토큰 게이트 ────────────────────────────


def test_session_stats_requires_internal_token_when_configured(monkeypatch):
    from fastapi.testclient import TestClient

    from app import auth_middleware
    from app.main import app
    from app.routers import quality

    monkeypatch.setattr(auth_middleware, "INTERNAL_API_TOKEN", "secret-token", raising=False)
    monkeypatch.setattr(
        quality, "get_session_stats", lambda days, group_by: {"days": days, "group_by": group_by}
    )
    client = TestClient(app)

    denied = client.get("/api/v1/metrics/session-stats")
    assert denied.status_code == 403

    wrong = client.get("/api/v1/metrics/session-stats", headers={"X-Internal-Token": "nope"})
    assert wrong.status_code == 403

    ok = client.get("/api/v1/metrics/session-stats", headers={"X-Internal-Token": "secret-token"})
    assert ok.status_code == 200
    assert ok.json()["group_by"] == "room"


# ── FCM data payload에 notification_type 포함 (C6 이월) ────────────────


@pytest.mark.asyncio
async def test_send_notification_with_record_includes_notification_type_in_fcm_data(monkeypatch):
    from app import firebase_service, postgres_async

    class _Db:
        async def execute(self, *a, **k):
            return None

    monkeypatch.setattr(postgres_async, "get_async_db", lambda: _Db())
    monkeypatch.setattr(firebase_service, "get_token", lambda uid: "fcm-token")
    captured = {}

    def _fake_send(token, title, body, data=None):
        captured["data"] = data
        return True

    monkeypatch.setattr(firebase_service, "send_push_notification", _fake_send)

    ok = await firebase_service.send_notification_with_record(
        user_id="uid-1", title="t", body="b", notification_type="d5_longing", deep_link="mbtichat://chat"
    )
    assert ok is True
    assert captured["data"]["notification_type"] == "d5_longing"
    assert captured["data"]["deep_link"] == "mbtichat://chat"


@pytest.mark.asyncio
async def test_send_notification_with_record_respects_caller_notification_type(monkeypatch):
    from app import firebase_service, postgres_async

    class _Db:
        async def execute(self, *a, **k):
            return None

    monkeypatch.setattr(postgres_async, "get_async_db", lambda: _Db())
    monkeypatch.setattr(firebase_service, "get_token", lambda uid: "fcm-token")
    captured = {}
    monkeypatch.setattr(
        firebase_service,
        "send_push_notification",
        lambda token, title, body, data=None: captured.setdefault("data", data) or True,
    )

    await firebase_service.send_notification_with_record(
        user_id="uid-1",
        title="t",
        body="b",
        notification_type="referral_d2",
        data={"notification_type": "d2_expiry", "code": "ABC"},
    )
    # referral.py처럼 호출부가 명시한 값이 우선
    assert captured["data"]["notification_type"] == "d2_expiry"
    assert captured["data"]["code"] == "ABC"


# ── D5 잡: character_mbti를 data로 전달 ─────────────────────────────────


class _FakeAsyncDb:
    def __init__(self, fetch_return):
        self.available = True
        self._fetch_return = fetch_return

    async def fetch(self, query, *args):
        return self._fetch_return


@pytest.mark.asyncio
async def test_send_d5_passes_character_mbti_in_data(monkeypatch):
    from app import postgres_async, scheduler

    fake_db = _FakeAsyncDb([{"user_id": "uid-1", "character_mbti": "ENFP"}])
    monkeypatch.setattr(postgres_async, "get_async_db", lambda: fake_db)
    sent = AsyncMock(return_value=True)
    monkeypatch.setattr("app.firebase_service.send_notification_with_record", sent)

    await scheduler.send_d5_character_messages()

    _, kwargs = sent.call_args
    assert kwargs.get("notification_type") == "d5_longing"
    assert kwargs.get("data") == {"character_mbti": "ENFP"}
