"""apply_diary_outcome 저장 시점 길이 캡 테스트 (Low-2, 2026-08-04 점검).

ProactiveChatRequest.hook의 max_length=300 계약과 정합시키기 위해
next_hook/next_goal을 저장 전 300자로 절단하는지 검증한다. 안드로이드
클라이언트가 이미 절단하지만, 서버 저장 원천에서도 이중 방어해야
다른 경로가 절단 없이 값을 넘겨도 계약이 깨지지 않는다.
"""

from app import story_state_store as sss


def _fake_state(**overrides):
    state = sss._empty_state("room-1", "char-1")
    for k, v in overrides.items():
        setattr(state, k, v)
    return state


def test_apply_diary_outcome_truncates_next_hook_and_goal_to_300_chars(monkeypatch):
    monkeypatch.setattr(sss, "get_story_state", lambda room_id, character_id: _fake_state())

    captured = {}

    def fake_execute(query, params):
        captured["query"] = query
        captured["params"] = params

    monkeypatch.setattr(sss, "execute", fake_execute)

    long_hook = "가" * 500
    long_goal = "나" * 500

    sss.apply_diary_outcome("room-1", "char-1", long_hook, long_goal)

    stored_next_hook, stored_next_goal, unresolved_hook_fallback, current_goal_fallback, room_id = captured["params"]
    assert len(stored_next_hook) == 300
    assert len(stored_next_goal) == 300
    assert len(unresolved_hook_fallback) == 300
    assert len(current_goal_fallback) == 300
    assert room_id == "room-1"


def test_apply_diary_outcome_leaves_short_values_untouched(monkeypatch):
    monkeypatch.setattr(sss, "get_story_state", lambda room_id, character_id: _fake_state())

    captured = {}

    def fake_execute(query, params):
        captured["params"] = params

    monkeypatch.setattr(sss, "execute", fake_execute)

    sss.apply_diary_outcome("room-1", "char-1", "짧은 훅", "짧은 목표")

    stored_next_hook, stored_next_goal, _, _, _ = captured["params"]
    assert stored_next_hook == "짧은 훅"
    assert stored_next_goal == "짧은 목표"


def test_apply_diary_outcome_handles_none_gracefully(monkeypatch):
    monkeypatch.setattr(sss, "get_story_state", lambda room_id, character_id: _fake_state())

    captured = {}

    def fake_execute(query, params):
        captured["params"] = params

    monkeypatch.setattr(sss, "execute", fake_execute)

    sss.apply_diary_outcome("room-1", "char-1", None, None)

    stored_next_hook, stored_next_goal, _, _, _ = captured["params"]
    assert stored_next_hook == ""
    assert stored_next_goal == ""


def test_apply_diary_outcome_noop_without_room_id(monkeypatch):
    called = {"execute": False}
    monkeypatch.setattr(sss, "execute", lambda *a, **k: called.__setitem__("execute", True))
    sss.apply_diary_outcome("", "char-1", "hook", "goal")
    assert called["execute"] is False
