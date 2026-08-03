"""M4-①(2026-08-03 회의 항목3): quick_score 분포 계측 테스트.

진단: quick_score가 게이트(0.4) 판정에만 쓰이고 값 자체가 어디에도 남지
않아 분포를 알 수 없었다. 수정: chat_service가 게이트 판정에 이미 쓴
quick_score를 score_response_async까지 그대로 전달해 quality_score
이벤트 payload에 "quick_score" 키로 기록한다 — 게이트 임계값/판정 로직은
그대로다(순수 계측).

이 파일은 3계층을 검증한다:
1. quality_service.score_response_async가 quick_score_value를 payload에 싣는지
2. chat_service.generate_reply가 게이트에서 쓴 quick_score를 그 경로까지 전달하는지
3. chat_service.stream_reply가 텔레메트리 quick_score를 그 경로까지 전달하는지
"""

import types

import pytest

from app import chat_service, quality_service


class _FakeQualityMessage:
    def __init__(self, content):
        self.content = content


class _FakeQualityChoice:
    def __init__(self, content):
        self.message = _FakeQualityMessage(content)


class _FakeQualityResponse:
    def __init__(self, content):
        self.choices = [_FakeQualityChoice(content)]


class _FakeQualityCompletions:
    async def create(self, **kwargs):
        return _FakeQualityResponse(
            '{"mbti_consistency":8,"contextual_relevance":8,'
            '"emotional_naturalness":8,"engagement_quality":8}'
        )


class _FakeQualityClient:
    def __init__(self):
        self.chat = types.SimpleNamespace(completions=_FakeQualityCompletions())


# ── 1. quality_service.score_response_async 단위 ───────────────────────────


@pytest.mark.asyncio
async def test_score_response_async_records_quick_score_in_payload(monkeypatch):
    monkeypatch.setattr(quality_service, "_client", _FakeQualityClient())

    recorded: list[dict] = []

    async def _fake_record_event_async(event_type, room_id="", character_id="", payload=None, **kw):
        recorded.append(dict(event_type=event_type, payload=payload or {}))

    monkeypatch.setattr(quality_service, "record_event_async", _fake_record_event_async)

    result = await quality_service.score_response_async(
        user_msg="안녕", ai_response='[{"text":"안녕!","emotion":"HAPPY"}]',
        mbti="ENFP", affinity_level=2, quick_score_value=0.73,
    )

    assert result is not None
    assert result["quick_score"] == 0.73
    assert len(recorded) == 1
    assert recorded[0]["payload"]["quick_score"] == 0.73


@pytest.mark.asyncio
async def test_score_response_async_quick_score_defaults_to_none(monkeypatch):
    """호출부가 값을 넘기지 않으면(기존 호출부 호환) None이 그대로 기록된다."""
    monkeypatch.setattr(quality_service, "_client", _FakeQualityClient())

    recorded: list[dict] = []

    async def _fake_record_event_async(event_type, room_id="", character_id="", payload=None, **kw):
        recorded.append(dict(payload=payload or {}))

    monkeypatch.setattr(quality_service, "record_event_async", _fake_record_event_async)

    result = await quality_service.score_response_async(
        user_msg="안녕", ai_response='[{"text":"안녕!","emotion":"HAPPY"}]',
        mbti="ENFP", affinity_level=2,
    )

    assert result["quick_score"] is None
    assert recorded[0]["payload"]["quick_score"] is None


# ── 2. generate_reply(논스트림) → score_response_async 전달 ────────────────


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeUsage:
    def __init__(self):
        self.prompt_tokens = 10
        self.completion_tokens = 5
        self.total_tokens = 15


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]
        self.usage = _FakeUsage()


class _FakeCompletions:
    def __init__(self, content):
        self._content = content

    async def create(self, **kwargs):
        return _FakeResponse(self._content)


class _FakeClient:
    def __init__(self, content):
        self.chat = types.SimpleNamespace(completions=_FakeCompletions(content))


@pytest.mark.asyncio
async def test_generate_reply_forwards_quick_score_to_quality_check(monkeypatch):
    async def _fake_affinity(*a, **k):
        return 3

    async def _fake_mem_ctx(*a, **k):
        return ""

    async def _fake_resolve(model_id, ab_variant):
        return model_id, ""

    tracked: list[tuple[str, object]] = []

    def _capture_tracked(coro, name=""):
        tracked.append((name, coro))
        return None

    monkeypatch.setattr(chat_service, "client", _FakeClient('[{"text":"안녕!","emotion":"HAPPY"}]'))
    monkeypatch.setattr(chat_service, "analyze_affinity_with_llm", _fake_affinity)
    monkeypatch.setattr(chat_service, "build_memory_context", _fake_mem_ctx)
    monkeypatch.setattr(chat_service, "resolve_model_endpoint", _fake_resolve)
    monkeypatch.setattr(chat_service, "get_store", lambda: None)
    monkeypatch.setattr(chat_service, "create_tracked_task", _capture_tracked)
    monkeypatch.setattr(chat_service, "quick_score", lambda *a, **k: 0.82)
    monkeypatch.setattr(chat_service, "check_content", lambda text: (True, ""))

    captured = {}

    async def _fake_post_check(user_msg, ai_response, mbti, affinity_level,
                                room_id="", character_id="", quick_score_value=None):
        captured["quick_score_value"] = quick_score_value

    monkeypatch.setattr(chat_service, "_post_response_quality_check", _fake_post_check)

    parts, delta = await chat_service.generate_reply(
        message="안녕", mbti="ENFP", speech_style="반말", relationship="친구",
        nickname="유저", affinity_level=3, conversation_history=[],
        character_name="캐릭터", character_id="", room_id="room-qs",
    )
    assert parts

    quality_task = next((c for n, c in tracked if n == "quality-check"), None)
    assert quality_task is not None
    await quality_task
    await _close_untracked(tracked, "quality-check")

    assert captured["quick_score_value"] == 0.82


async def _close_untracked(tracked, keep_name):
    for name, coro in tracked:
        if name != keep_name:
            try:
                coro.close()
            except Exception:
                pass


# ── 3. stream_reply(스트리밍) → score_response_async 전달 ──────────────────


class _FakeStreamChunk:
    def __init__(self, content):
        self.choices = [types.SimpleNamespace(delta=types.SimpleNamespace(content=content))]
        self.usage = None


class _FakeStream:
    def __init__(self, tokens):
        self._tokens = list(tokens)

    def __aiter__(self):
        self._it = iter(self._tokens)
        return self

    async def __anext__(self):
        try:
            return _FakeStreamChunk(next(self._it))
        except StopIteration:
            raise StopAsyncIteration


class _FakeStreamCompletions:
    def __init__(self, tokens):
        self._tokens = tokens

    async def create(self, **kwargs):
        return _FakeStream(self._tokens)


class _FakeStreamClient:
    def __init__(self, tokens):
        self.chat = types.SimpleNamespace(completions=_FakeStreamCompletions(tokens))


@pytest.mark.asyncio
async def test_stream_reply_forwards_quick_score_to_quality_check(monkeypatch):
    async def _fake_affinity(*a, **k):
        return 3

    async def _fake_mem_ctx(*a, **k):
        return ""

    async def _fake_resolve(model_id, ab_variant):
        return model_id, ""

    tracked: list[tuple[str, object]] = []

    def _capture_tracked(coro, name=""):
        tracked.append((name, coro))
        return None

    monkeypatch.setattr(chat_service, "client", _FakeStreamClient(['[{"text":"안녕","emotion":"HAPPY"}]']))
    monkeypatch.setattr(chat_service, "analyze_affinity_with_llm", _fake_affinity)
    monkeypatch.setattr(chat_service, "build_memory_context", _fake_mem_ctx)
    monkeypatch.setattr(chat_service, "resolve_model_endpoint", _fake_resolve)
    monkeypatch.setattr(chat_service, "get_store", lambda: None)
    monkeypatch.setattr(chat_service, "create_tracked_task", _capture_tracked)
    monkeypatch.setattr(chat_service, "quick_score", lambda *a, **k: 0.65)
    monkeypatch.setattr(chat_service, "check_content", lambda text: (True, ""))

    captured = {}

    async def _fake_post_check(user_msg, ai_response, mbti, affinity_level,
                                room_id="", character_id="", quick_score_value=None):
        captured["quick_score_value"] = quick_score_value

    monkeypatch.setattr(chat_service, "_post_response_quality_check", _fake_post_check)

    parts = []
    done = None
    async for item in chat_service.stream_reply(
        message="안녕", mbti="ENFP", speech_style="반말", relationship="친구",
        nickname="유저", affinity_level=3, conversation_history=[],
        character_name="캐릭터", character_id="", room_id="room-qs-stream",
    ):
        if isinstance(item, chat_service.StreamDone):
            done = item
        else:
            parts.append(item)
    assert done is not None
    assert parts

    quality_task = next((c for n, c in tracked if n == "quality-check"), None)
    assert quality_task is not None
    await quality_task
    await _close_untracked(tracked, "quality-check")

    assert captured["quick_score_value"] == 0.65
