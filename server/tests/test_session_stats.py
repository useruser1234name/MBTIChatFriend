"""P3 (2026-08-03 회의): 30분 gap 휴리스틱 기반 세션 파생 로직 테스트.

metric_events(chat_turn/app_open)로부터 세션을 파생하는 순수 로직
(_split_into_sessions/_aggregate_session_stats)과, 이를 감싸는
get_session_stats()의 DB 접근 계층(postgres_enabled/fetchall 목킹)을 검증한다.
"""

from datetime import datetime, timedelta

import pytest

from app import metrics_service
from app.metrics_service import (
    _aggregate_session_stats,
    _split_into_sessions,
    get_session_stats,
)


def _row(group_key: str, minute_offset: int, event_type: str = "chat_turn"):
    base = datetime(2026, 8, 3, 12, 0, 0)
    return {
        "group_key": group_key,
        "event_type": event_type,
        "created_at": base + timedelta(minutes=minute_offset),
    }


# ── _split_into_sessions: 순수 경계 판정 로직 ──────────────────────


def test_29_minute_gap_stays_in_same_session():
    rows = [_row("room1", 0), _row("room1", 29)]

    sessions = _split_into_sessions(rows)

    assert len(sessions) == 1
    assert sessions[0]["turn_count"] == 2
    assert sessions[0]["duration_seconds"] == 29 * 60


def test_31_minute_gap_starts_new_session():
    rows = [_row("room1", 0), _row("room1", 31)]

    sessions = _split_into_sessions(rows)

    assert len(sessions) == 2
    assert sessions[0]["turn_count"] == 1
    assert sessions[1]["turn_count"] == 1


def test_exactly_30_minute_gap_stays_in_same_session():
    """gap_minutes 경계값은 '초과(>)'만 새 세션 — 정확히 30분은 동일 세션."""
    rows = [_row("room1", 0), _row("room1", 30)]

    sessions = _split_into_sessions(rows)

    assert len(sessions) == 1


def test_single_event_forms_one_session():
    rows = [_row("room1", 0)]

    sessions = _split_into_sessions(rows)

    assert len(sessions) == 1
    assert sessions[0]["turn_count"] == 1
    assert sessions[0]["duration_seconds"] == 0


def test_empty_rows_returns_no_sessions():
    assert _split_into_sessions([]) == []


def test_group_key_change_always_starts_new_session_even_without_gap():
    """같은 타임스탬프라도 group_key(room/user)가 다르면 별도 세션."""
    rows = [_row("room1", 0), _row("room2", 0)]

    sessions = _split_into_sessions(rows)

    assert len(sessions) == 2
    assert {s["group_key"] for s in sessions} == {"room1", "room2"}


def test_app_open_events_do_not_count_as_turns():
    rows = [
        _row("room1", 0, event_type="app_open"),
        _row("room1", 1, event_type="chat_turn"),
        _row("room1", 2, event_type="chat_turn"),
    ]

    sessions = _split_into_sessions(rows)

    assert len(sessions) == 1
    assert sessions[0]["turn_count"] == 2
    assert sessions[0]["event_count"] == 3


def test_multiple_sessions_within_same_group():
    rows = [
        _row("room1", 0),
        _row("room1", 10),
        _row("room1", 100),  # 90분 뒤 → 새 세션
        _row("room1", 105),
        _row("room1", 110),
    ]

    sessions = _split_into_sessions(rows)

    assert len(sessions) == 2
    assert sessions[0]["turn_count"] == 2
    assert sessions[1]["turn_count"] == 3


# ── _aggregate_session_stats ────────────────────────────────────────


def test_aggregate_session_stats_computes_avg_and_median():
    sessions = [
        {"turn_count": 2, "duration_seconds": 60.0},
        {"turn_count": 4, "duration_seconds": 120.0},
        {"turn_count": 6, "duration_seconds": 180.0},
    ]

    stats = _aggregate_session_stats(sessions)

    assert stats["session_count"] == 3
    assert stats["avg_turns_per_session"] == 4.0
    assert stats["median_turns_per_session"] == 4.0
    assert stats["avg_session_duration_seconds"] == 120.0


def test_aggregate_session_stats_empty_returns_zeros():
    stats = _aggregate_session_stats([])

    assert stats == {
        "session_count": 0,
        "avg_turns_per_session": 0.0,
        "median_turns_per_session": 0.0,
        "avg_session_duration_seconds": 0.0,
    }


# ── get_session_stats: DB 접근 계층 (monkeypatch) ───────────────────


def test_get_session_stats_returns_empty_when_postgres_disabled(monkeypatch):
    monkeypatch.setattr(metrics_service, "postgres_enabled", lambda: False)

    result = get_session_stats(days=7, group_by="room")

    assert result["session_count"] == 0
    assert result["group_by"] == "room"
    assert result["days"] == 7


def test_get_session_stats_room_grouping_uses_room_id_column(monkeypatch):
    monkeypatch.setattr(metrics_service, "postgres_enabled", lambda: True)

    captured = {}

    def fake_fetchall(query, params=None):
        captured["query"] = query
        captured["params"] = params
        return [
            {"group_key": "roomA", "event_type": "chat_turn",
             "created_at": datetime(2026, 8, 3, 9, 0)},
            {"group_key": "roomA", "event_type": "chat_turn",
             "created_at": datetime(2026, 8, 3, 9, 10)},
        ]

    monkeypatch.setattr(metrics_service, "fetchall", fake_fetchall)

    result = get_session_stats(days=7, group_by="room")

    assert "room_id" in captured["query"]
    assert result["session_count"] == 1
    assert result["avg_turns_per_session"] == 2.0


def test_get_session_stats_user_grouping_uses_user_id_column(monkeypatch):
    monkeypatch.setattr(metrics_service, "postgres_enabled", lambda: True)
    captured = {}

    def fake_fetchall(query, params=None):
        captured["query"] = query
        return []

    monkeypatch.setattr(metrics_service, "fetchall", fake_fetchall)

    result = get_session_stats(days=3, group_by="user")

    assert "user_id" in captured["query"]
    assert result["days"] == 3
    assert result["session_count"] == 0


def test_get_session_stats_rejects_invalid_group_by(monkeypatch):
    monkeypatch.setattr(metrics_service, "postgres_enabled", lambda: True)

    with pytest.raises(ValueError):
        get_session_stats(days=7, group_by="invalid")  # type: ignore[arg-type]
