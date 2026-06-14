"""scheduler.py 4잡 회귀 테스트 (S-10).

DB·FCM 없이 mock으로 검증:
- db.available=False → early return (FCM 호출 0회)
- db.fetch mock → FCM 호출 확인

스케줄러 함수들은 get_async_db와 send_notification_with_record를
함수 내부에서 로컬 import하므로, 원래 모듈 경로를 패치한다.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── 공통 헬퍼 ─────────────────────────────────────────────────────────


def _make_db(available: bool, rows=None):
    """AsyncDatabase mock 생성."""
    db = MagicMock()
    db.available = available
    db.fetch = AsyncMock(return_value=rows or [])
    db.execute = AsyncMock()
    return db


# ── send_d3_personalized_notifications ───────────────────────────────


def test_d3_early_return_when_db_unavailable():
    """DB 미연결 시 early return — FCM 호출 0회."""
    from app.scheduler import send_d3_personalized_notifications

    db_mock = _make_db(available=False)

    with (
        patch("app.postgres_async.get_async_db", return_value=db_mock),
        patch("app.firebase_service.send_notification_with_record", new_callable=AsyncMock) as fcm_mock,
    ):
        asyncio.run(send_d3_personalized_notifications())
        fcm_mock.assert_not_called()


def test_d3_sends_fcm_when_rows_exist():
    """DB에 D+3 미접속 사용자가 있으면 FCM 발송."""
    import datetime
    from app.scheduler import send_d3_personalized_notifications, KST

    current_hour = datetime.datetime.now(KST).hour
    rows = [{"user_id": "uid-001", "content": "오늘 날씨", "last_active_hour": current_hour}]
    db_mock = _make_db(available=True, rows=rows)

    fcm_mock = AsyncMock()
    with (
        patch("app.postgres_async.get_async_db", return_value=db_mock),
        patch("app.firebase_service.send_notification_with_record", fcm_mock),
    ):
        asyncio.run(send_d3_personalized_notifications())
        fcm_mock.assert_called_once()
        call_kwargs = fcm_mock.call_args.kwargs
        assert call_kwargs["user_id"] == "uid-001"
        assert call_kwargs["notification_type"] == "d3_personalized"


# ── send_d5_character_messages ────────────────────────────────────────


def test_d5_early_return_when_db_unavailable():
    """DB 미연결 시 early return."""
    from app.scheduler import send_d5_character_messages

    db_mock = _make_db(available=False)

    with (
        patch("app.postgres_async.get_async_db", return_value=db_mock),
        patch("app.firebase_service.send_notification_with_record", new_callable=AsyncMock) as fcm_mock,
    ):
        asyncio.run(send_d5_character_messages())
        fcm_mock.assert_not_called()


def test_d5_sends_longing_message():
    """D+5 잡 — MBTI별 그리움 메시지 발송."""
    from app.scheduler import send_d5_character_messages

    rows = [{"user_id": "uid-002", "character_mbti": "ENFP"}]
    db_mock = _make_db(available=True, rows=rows)

    fcm_mock = AsyncMock()
    with (
        patch("app.postgres_async.get_async_db", return_value=db_mock),
        patch("app.firebase_service.send_notification_with_record", fcm_mock),
    ):
        asyncio.run(send_d5_character_messages())
        fcm_mock.assert_called_once()
        call_kwargs = fcm_mock.call_args.kwargs
        assert call_kwargs["user_id"] == "uid-002"
        assert call_kwargs["notification_type"] == "d5_longing"
        assert "빨리 돌아와" in call_kwargs["body"]  # ENFP 메시지


# ── send_weekly_summary ───────────────────────────────────────────────


def test_weekly_early_return_when_db_unavailable():
    """DB 미연결 시 early return."""
    from app.scheduler import send_weekly_summary

    db_mock = _make_db(available=False)

    with (
        patch("app.postgres_async.get_async_db", return_value=db_mock),
        patch("app.firebase_service.send_notification_with_record", new_callable=AsyncMock) as fcm_mock,
    ):
        asyncio.run(send_weekly_summary())
        fcm_mock.assert_not_called()


def test_weekly_sends_summary():
    """주간 요약 잡 — 대화 수 포함 FCM 발송."""
    from app.scheduler import send_weekly_summary

    rows = [{"user_id": "uid-003", "msg_count": 42}]
    db_mock = _make_db(available=True, rows=rows)

    fcm_mock = AsyncMock()
    with (
        patch("app.postgres_async.get_async_db", return_value=db_mock),
        patch("app.firebase_service.send_notification_with_record", fcm_mock),
    ):
        asyncio.run(send_weekly_summary())
        fcm_mock.assert_called_once()
        call_kwargs = fcm_mock.call_args.kwargs
        assert call_kwargs["user_id"] == "uid-003"
        assert call_kwargs["notification_type"] == "weekly_summary"
        assert "42번" in call_kwargs["body"]


# ── send_gratitude_day_push ───────────────────────────────────────────


def test_gratitude_early_return_when_db_unavailable():
    """DB 미연결 시 early return."""
    from app.scheduler import send_gratitude_day_push

    db_mock = _make_db(available=False)

    with (
        patch("app.postgres_async.get_async_db", return_value=db_mock),
        patch("app.firebase_service.send_notification_with_record", new_callable=AsyncMock) as fcm_mock,
    ):
        asyncio.run(send_gratitude_day_push())
        fcm_mock.assert_not_called()


def test_gratitude_sends_push():
    """Gratitude 잡 — push_enabled 사용자에게 FCM 발송."""
    from app.scheduler import send_gratitude_day_push

    rows = [{"user_id": "uid-004", "mbti_type": "INFP"}]
    db_mock = _make_db(available=True, rows=rows)

    fcm_mock = AsyncMock()
    with (
        patch("app.postgres_async.get_async_db", return_value=db_mock),
        patch("app.firebase_service.send_notification_with_record", fcm_mock),
    ):
        asyncio.run(send_gratitude_day_push())
        fcm_mock.assert_called_once()
        call_kwargs = fcm_mock.call_args.kwargs
        assert call_kwargs["user_id"] == "uid-004"
        assert "INFP" in call_kwargs["body"]


# ── _pool import 부재 확인 ────────────────────────────────────────────


def test_scheduler_has_no_pool_import():
    """scheduler.py에 _pool import/사용이 없어야 한다 (S-1 센티넬)."""
    import inspect
    from app import scheduler

    source = inspect.getsource(scheduler)
    assert "_pool" not in source, "scheduler.py에 _pool 참조가 남아 있습니다"
