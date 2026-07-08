"""scheduler.py 배치 잡 테스트.

2026-07-02 개선 회의 P0-2:
- d3/d5/weekly/gratitude 4개 잡이 `app.postgres_async._pool`(존재하지 않는 심볼) +
  `.acquire()`(asyncpg 전용 API)를 사용해 실행 시 ImportError/AttributeError로 죽어있었다.
  get_async_db() + db.fetch()/execute() 패턴(flush_empathy_notifications과 동일)으로 교체.
- d3 잡이 유저 원문 메시지 앞 20자를 푸시 본문에 노출하던 프라이버시 결함을 제거.
- d5 잡의 MBTI 16종 중 8종 누락 문구를 보강.
- gratitude 잡의 start_scheduler 등록을 활성화.

DB 없이도 (a) import 자체가 깨지지 않는지, (b) mock DB로 정상 흐름이 도는지 검증한다.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


MBTI_16 = [
    "INTJ", "INTP", "ENTJ", "ENTP",
    "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ",
    "ISTP", "ISFP", "ESTP", "ESFP",
]


class _FakeAsyncDb:
    """postgres_async.AsyncDatabase 흉내 — available/fetch/execute만 필요."""

    def __init__(self, fetch_return=None):
        self.available = True
        self._fetch_return = fetch_return if fetch_return is not None else []
        self.fetch = AsyncMock(return_value=self._fetch_return)
        self.execute = AsyncMock(return_value=None)


class _UnavailableAsyncDb:
    def __init__(self):
        self.available = False
        self.fetch = AsyncMock(side_effect=AssertionError("fetch가 호출되면 안 됨 (DB 미연결)"))
        self.execute = AsyncMock(side_effect=AssertionError("execute가 호출되면 안 됨 (DB 미연결)"))


# ── (a) import 자체가 깨지지 않는지 (구 _pool / .acquire() 회귀 방지) ──────────
def test_scheduler_module_imports_without_error():
    import importlib

    mod = importlib.import_module("app.scheduler")
    assert mod.scheduler is not None
    for name in (
        "send_d3_personalized_notifications",
        "send_d5_character_messages",
        "send_weekly_summary",
        "send_gratitude_day_push",
        "flush_empathy_notifications",
        "send_night_diary_push",
    ):
        assert hasattr(mod, name)


def test_scheduler_jobs_do_not_reference_module_level_pool():
    """구 버그(`from app.postgres_async import _pool`)가 재도입되지 않았는지 소스 레벨로도 확인."""
    import inspect

    from app import scheduler as scheduler_mod

    for fn in (
        scheduler_mod.send_d3_personalized_notifications,
        scheduler_mod.send_d5_character_messages,
        scheduler_mod.send_weekly_summary,
        scheduler_mod.send_gratitude_day_push,
    ):
        src = inspect.getsource(fn)
        assert "_pool" not in src, f"{fn.__name__} 이 여전히 모듈 레벨 _pool을 참조함"
        assert ".acquire()" not in src, f"{fn.__name__} 이 여전히 asyncpg 전용 .acquire()를 사용함"
        assert "get_async_db" in src, f"{fn.__name__} 이 get_async_db() 패턴을 사용하지 않음"


# ── DB 미연결 시 조용히 종료 ────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_jobs_noop_when_db_unavailable(monkeypatch):
    from app import postgres_async, scheduler

    fake_db = _UnavailableAsyncDb()
    monkeypatch.setattr(postgres_async, "get_async_db", lambda: fake_db)

    # 예외 없이 조용히 반환되어야 함 (fetch/execute 호출 시 AssertionError로 실패)
    await scheduler.send_d3_personalized_notifications()
    await scheduler.send_d5_character_messages()
    await scheduler.send_weekly_summary()
    await scheduler.send_gratitude_day_push()


# ── (b) mock DB로 정상 흐름 ─────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_send_d3_personalized_notifications_happy_path(monkeypatch):
    from app import postgres_async, scheduler

    fake_db = _FakeAsyncDb(fetch_return=[])
    monkeypatch.setattr(postgres_async, "get_async_db", lambda: fake_db)

    sent = AsyncMock(return_value=True)
    monkeypatch.setattr("app.firebase_service.send_notification_with_record", sent)

    await scheduler.send_d3_personalized_notifications()

    fake_db.fetch.assert_awaited_once()
    sent.assert_not_awaited()  # 빈 결과 → 발송 없음


@pytest.mark.asyncio
async def test_send_d3_personalized_notifications_sends_and_hides_user_content(monkeypatch):
    """(c) 프라이버시 회귀 방지: 유저 content가 알림 본문에 절대 포함되지 않아야 한다."""
    from app import postgres_async, scheduler

    secret_message = "사실 나 요즘 회사에서 상사랑 크게 다퉜어서 너무 힘들어"
    rows = [
        {"user_id": "uid-1", "content": secret_message, "last_active_hour": scheduler.datetime.now(scheduler.KST).hour}
    ]
    fake_db = _FakeAsyncDb(fetch_return=rows)
    monkeypatch.setattr(postgres_async, "get_async_db", lambda: fake_db)

    sent = AsyncMock(return_value=True)
    monkeypatch.setattr("app.firebase_service.send_notification_with_record", sent)

    await scheduler.send_d3_personalized_notifications()

    sent.assert_awaited_once()
    _, kwargs = sent.call_args
    body = kwargs.get("body", "")
    assert secret_message not in body
    assert secret_message[:20] not in body
    assert kwargs.get("user_id") == "uid-1"
    assert kwargs.get("notification_type") == "d3_personalized"


@pytest.mark.asyncio
async def test_send_d5_character_messages_happy_path(monkeypatch):
    from app import postgres_async, scheduler

    rows = [{"user_id": "uid-1", "character_mbti": "ENFP"}]
    fake_db = _FakeAsyncDb(fetch_return=rows)
    monkeypatch.setattr(postgres_async, "get_async_db", lambda: fake_db)

    sent = AsyncMock(return_value=True)
    monkeypatch.setattr("app.firebase_service.send_notification_with_record", sent)

    await scheduler.send_d5_character_messages()

    sent.assert_awaited_once()
    _, kwargs = sent.call_args
    assert kwargs.get("user_id") == "uid-1"
    assert kwargs.get("notification_type") == "d5_longing"
    assert kwargs.get("body")


@pytest.mark.asyncio
async def test_send_d5_character_messages_unknown_mbti_falls_back_to_default(monkeypatch):
    from app import postgres_async, scheduler

    rows = [{"user_id": "uid-2", "character_mbti": "unknown"}]
    fake_db = _FakeAsyncDb(fetch_return=rows)
    monkeypatch.setattr(postgres_async, "get_async_db", lambda: fake_db)

    sent = AsyncMock(return_value=True)
    monkeypatch.setattr("app.firebase_service.send_notification_with_record", sent)

    await scheduler.send_d5_character_messages()

    sent.assert_awaited_once()
    _, kwargs = sent.call_args
    assert kwargs.get("body") == "요즘 많이 바빴죠? 나는 여기서 기다리고 있었어요."


# ── (d) d5 16종 전부 문구 존재 ───────────────────────────────────────────────
def test_send_d5_longing_messages_cover_all_16_mbti_types():
    import inspect

    from app import scheduler

    src = inspect.getsource(scheduler.send_d5_character_messages)
    # 함수 내부 LONGING_MESSAGES 리터럴을 직접 실행하지 않고, 소스에 16종 키가
    # 모두 존재하는지로 검증 (딕셔너리가 함수 로컬이라 import만으로는 접근 불가).
    for mbti in MBTI_16:
        assert f'"{mbti}"' in src, f"{mbti} 문구가 LONGING_MESSAGES에 없음"


@pytest.mark.asyncio
async def test_send_d5_longing_messages_all_16_types_produce_distinct_nonempty_bodies(monkeypatch):
    """16종 각각에 대해 실제로 서로 다른 비어있지 않은 문구가 발송되는지 실행 레벨로 검증."""
    from app import postgres_async, scheduler

    bodies: dict[str, str] = {}
    for mbti in MBTI_16:
        rows = [{"user_id": f"uid-{mbti}", "character_mbti": mbti}]
        fake_db = _FakeAsyncDb(fetch_return=rows)
        monkeypatch.setattr(postgres_async, "get_async_db", lambda db=fake_db: db)

        sent = AsyncMock(return_value=True)
        monkeypatch.setattr("app.firebase_service.send_notification_with_record", sent)

        await scheduler.send_d5_character_messages()

        sent.assert_awaited_once()
        _, kwargs = sent.call_args
        body = kwargs.get("body", "")
        assert body, f"{mbti} 문구가 비어있음"
        bodies[mbti] = body

    # 기본 문구로 뭉뚱그려지지 않고 각 유형이 고유 문구를 가져야 함
    assert len(set(bodies.values())) == len(MBTI_16)


@pytest.mark.asyncio
async def test_send_weekly_summary_happy_path(monkeypatch):
    from app import postgres_async, scheduler

    rows = [{"user_id": "uid-1", "msg_count": 12}]
    fake_db = _FakeAsyncDb(fetch_return=rows)
    monkeypatch.setattr(postgres_async, "get_async_db", lambda: fake_db)

    sent = AsyncMock(return_value=True)
    monkeypatch.setattr("app.firebase_service.send_notification_with_record", sent)

    await scheduler.send_weekly_summary()

    sent.assert_awaited_once()
    _, kwargs = sent.call_args
    assert kwargs.get("user_id") == "uid-1"
    assert "12" in kwargs.get("body", "")
    assert kwargs.get("notification_type") == "weekly_summary"


@pytest.mark.asyncio
async def test_send_gratitude_day_push_happy_path(monkeypatch):
    from app import postgres_async, scheduler

    rows = [{"user_id": "uid-1", "mbti_type": "INFP"}]
    fake_db = _FakeAsyncDb(fetch_return=rows)
    monkeypatch.setattr(postgres_async, "get_async_db", lambda: fake_db)

    sent = AsyncMock(return_value=True)
    monkeypatch.setattr("app.firebase_service.send_notification_with_record", sent)

    await scheduler.send_gratitude_day_push()

    sent.assert_awaited_once()
    _, kwargs = sent.call_args
    assert kwargs.get("user_id") == "uid-1"
    assert "INFP" in kwargs.get("body", "")


# ── gratitude 잡 등록 활성화 확인 ────────────────────────────────────────────
def test_gratitude_job_is_registered_in_start_scheduler():
    import inspect

    from app import scheduler

    src = inspect.getsource(scheduler.start_scheduler)
    assert "send_gratitude_day_push" in src
    # 주석 처리(#)로 죽어있지 않은지 — 실제 add_job 호출부에 등장해야 함
    assert src.count("send_gratitude_day_push") >= 1
    for line in src.splitlines():
        if "send_gratitude_day_push" in line:
            assert not line.strip().startswith("#"), "gratitude 잡이 여전히 주석 처리되어 있음"
