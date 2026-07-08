"""P0-4 회귀 테스트: 피드백 엔드포인트가 user_id를 인증 토큰에서만 채우는지 검증.

배경 결함(검증관 실측):
- response_feedback 테이블에 user_id 컬럼이 없었음
- /feedback/submit, /session-feedback 모두 user_id를 저장하지 않았음
- 클라가 위조할 수 없도록 인증 토큰(require_auth_always)에서만 채워야 한다
  (events.py 라우터와 동일 패턴).
"""

import pytest
from starlette.requests import Request

from app.models import FeedbackRequest
from app.routers import quality


def _fake_request(path: str) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": path,
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "query_string": b"",
    }
    return Request(scope)


class _FakeAsyncDb:
    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []

    async def execute(self, query, *args):
        self.calls.append((query, args))


@pytest.mark.asyncio
async def test_submit_feedback_uses_uid_from_auth_token(monkeypatch):
    captured = []

    def _fake_pg_execute(query, params=None):
        captured.append((query, params))

    monkeypatch.setattr(quality, "pg_execute", _fake_pg_execute)

    req = FeedbackRequest(
        room_id="room-1", character_id="char-1", message_id="msg-1", feedback_type="thumbs_up"
    )
    result = await quality.submit_feedback(
        _fake_request("/api/v1/feedback/submit"), req, user={"uid": "auth-uid-1"}
    )

    assert result == {"status": "ok"}
    assert len(captured) == 1
    _query, params = captured[0]
    # user_id는 params의 마지막 컬럼(INSERT 컬럼 순서 room_id, character_id, message_id,
    # feedback_type, feedback_detail, user_id)이며 mutation 방어를 위해 정확한 값 검증
    assert params[-1] == "auth-uid-1"
    assert params[-1] != ""


@pytest.mark.asyncio
async def test_submit_feedback_requires_auth():
    """require_auth_always 의존성 사용 확인 — 클라가 user_id를 직접 지정할 방법이 없어야 한다."""
    import inspect

    sig = inspect.signature(quality.submit_feedback)
    user_param = sig.parameters["user"]
    # Depends(require_auth_always) 의존성이 연결되어 있어야 함(선택적 verify_firebase_token 아님)
    assert user_param.default.dependency is quality.require_auth_always


@pytest.mark.asyncio
async def test_submit_session_feedback_uses_uid_from_auth_token(monkeypatch):
    fake_db = _FakeAsyncDb()
    monkeypatch.setattr(quality, "get_async_db", lambda: fake_db)

    req = quality.SessionFeedbackRequest(session_id="sess-1", room_id="room-1", rating=5, text="good")
    result = await quality.submit_session_feedback(
        _fake_request("/api/v1/session-feedback"), req, user={"uid": "auth-uid-2"}
    )

    assert result == {"status": "ok"}
    assert len(fake_db.calls) == 1
    _query, args = fake_db.calls[0]
    assert args[-1] == "auth-uid-2"
    assert args[-1] != ""
    # rating/text가 실제로 저장되는지도 함께 확인 (P0-4c)
    assert args[0] == "sess-1"
    assert args[1] == "room-1"
    assert args[2] == 5
    assert args[3] == "good"


@pytest.mark.asyncio
async def test_submit_session_feedback_requires_auth():
    import inspect

    sig = inspect.signature(quality.submit_session_feedback)
    user_param = sig.parameters["user"]
    assert user_param.default.dependency is quality.require_auth_always


@pytest.mark.asyncio
async def test_submit_session_feedback_rejects_invalid_rating(monkeypatch):
    fake_db = _FakeAsyncDb()
    monkeypatch.setattr(quality, "get_async_db", lambda: fake_db)

    req = quality.SessionFeedbackRequest(session_id="sess-2", room_id="room-2", rating=9)
    with pytest.raises(Exception) as exc:
        await quality.submit_session_feedback(
            _fake_request("/api/v1/session-feedback"), req, user={"uid": "auth-uid-3"}
        )
    assert getattr(exc.value, "status_code", None) == 400
    assert fake_db.calls == []
