"""P0-1 회귀 테스트: chat_turn 등 metric_events에 user_id가 채워지는지 검증.

검증관 실측 결함: routers/chat.py의 _finalize_chat_turn 내부 record_event 호출들이
user_id 인자 없이 호출되어, 라이브 chat_turn 이벤트에 user_id가 항상 비어 있었다.
"""

import types

import pytest

from app.models import ChatRequest, ReplyPart
from app.routers import chat as chat_router


def _fake_state(turn_count=3, next_hook="", next_goal=""):
    return types.SimpleNamespace(
        turn_count=turn_count,
        next_hook=next_hook,
        next_goal=next_goal,
        character_id="ENFP",
    )


def _base_req(**overrides) -> ChatRequest:
    kwargs = dict(
        message="안녕",
        mbti="ENFP",
        nickname="유저",
        end_of_session=False,
        affinity_level=1,
    )
    kwargs.update(overrides)
    return ChatRequest(**kwargs)


@pytest.fixture
def patch_finalize_deps(monkeypatch):
    """DB/외부 I/O 없이 _finalize_chat_turn을 실행하기 위한 공통 목킹."""
    recorded_events = []

    def _fake_record_event(**kwargs):
        recorded_events.append(kwargs)

    tracked = []

    def _fake_tracked(coro, name=""):
        tracked.append((name, coro))
        return None

    monkeypatch.setattr(chat_router, "record_event", _fake_record_event)
    monkeypatch.setattr(chat_router, "create_tracked_task", _fake_tracked)
    monkeypatch.setattr(chat_router, "mark_callback_used", lambda *a, **k: None)
    monkeypatch.setattr(chat_router, "get_story_state", lambda *a, **k: _fake_state())

    return recorded_events, tracked


@pytest.mark.asyncio
async def test_chat_turn_event_includes_user_id(patch_finalize_deps):
    recorded_events, tracked = patch_finalize_deps
    req = _base_req()
    user = {"uid": "test-uid-123"}

    result = await chat_router._finalize_chat_turn(
        req,
        user,
        room_id="room-1",
        state=_fake_state(),
        effective_character_id="ENFP",
        callback_key=None,
        replies=[ReplyPart(text="안녕!", emotion="HAPPY")],
        affinity_delta=0,
    )

    chat_turn_events = [e for e in recorded_events if e["event_type"] == "chat_turn"]
    assert len(chat_turn_events) == 1
    assert chat_turn_events[0]["user_id"] == "test-uid-123"
    assert chat_turn_events[0]["user_id"] != ""
    assert result["room_id"] == "room-1"

    # 백그라운드 태스크(persist-chat-data)도 스케줄되어야 한다 — 정리 목적으로 close
    for _name, coro in tracked:
        coro.close()


@pytest.mark.asyncio
async def test_chat_turn_event_empty_uid_when_unauthenticated(patch_finalize_deps):
    """user=None(미인증, REQUIRE_AUTH=false 개발 모드)이면 user_id는 빈 문자열이어야 한다."""
    recorded_events, tracked = patch_finalize_deps
    req = _base_req()

    await chat_router._finalize_chat_turn(
        req,
        None,
        room_id="room-2",
        state=_fake_state(),
        effective_character_id="ENFP",
        callback_key=None,
        replies=[ReplyPart(text="안녕!", emotion="HAPPY")],
        affinity_delta=0,
    )

    chat_turn_events = [e for e in recorded_events if e["event_type"] == "chat_turn"]
    assert chat_turn_events[0]["user_id"] == ""

    for _name, coro in tracked:
        coro.close()


@pytest.mark.asyncio
async def test_affinity_level_up_event_includes_user_id(patch_finalize_deps):
    """affinity_delta가 레벨업을 유발하면 affinity_level_up 이벤트에도 user_id가 실려야 한다."""
    recorded_events, tracked = patch_finalize_deps
    req = _base_req(affinity_level=1)
    user = {"uid": "test-uid-456"}

    await chat_router._finalize_chat_turn(
        req,
        user,
        room_id="room-3",
        state=_fake_state(),
        effective_character_id="ENFP",
        callback_key=None,
        replies=[ReplyPart(text="안녕!", emotion="HAPPY")],
        affinity_delta=50,  # 레벨업을 유발할 만큼 큰 delta
    )

    level_up_task = next((c for n, c in tracked if n == "record-affinity-level-up"), None)
    assert level_up_task is not None, "affinity_delta가 커도 레벨업 태스크가 스케줄되지 않음"

    await level_up_task  # 코루틴 실행 → 내부에서 record_event 호출

    level_up_events = [e for e in recorded_events if e["event_type"] == "affinity_level_up"]
    assert len(level_up_events) == 1
    assert level_up_events[0]["user_id"] == "test-uid-456"

    for name, coro in tracked:
        if name != "record-affinity-level-up":
            coro.close()
