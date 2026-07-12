"""P1: 턴 단계별 레이턴시(turn_latency) 계측 이벤트 테스트.

stream_reply를 test_stream_reply.py의 patch_deps 방식으로 목킹 실행하고,
create_tracked_task로 스케줄되는 "turn-latency" 백그라운드 태스크가
record_event_async(event_type="turn_latency")를 t_memory_ms/t_rag_ms/
t_first_token_ms 3개 구간 키를 포함한 payload로 호출하는지 검증한다.

t_gate(라우터 게이트 단계)는 이번 계측 범위에서 의도적으로 제외했으므로
(chat_service.py의 _record_turn_latency_event 참고) 3구간만 단언한다.

P2 갱신: chat_service.py가 record_event(동기) 대신 record_event_async만
모듈 전역으로 참조하도록 바뀌어(핫패스 이벤트 루프 블로킹 해소), 이 테스트의
목도 record_event_async를 async 함수로 patch하도록 갱신했다.
"""

import types

import pytest

from app import chat_service


class _FakeChunk:
    def __init__(self, content):
        self.choices = [types.SimpleNamespace(delta=types.SimpleNamespace(content=content))]


class _FakeStream:
    def __init__(self, tokens):
        self._tokens = list(tokens)

    def __aiter__(self):
        self._it = iter(self._tokens)
        return self

    async def __anext__(self):
        try:
            return _FakeChunk(next(self._it))
        except StopIteration:
            raise StopAsyncIteration


class _FakeCompletions:
    def __init__(self, tokens):
        self._tokens = tokens

    async def create(self, **kwargs):
        return _FakeStream(self._tokens)


class _FakeClient:
    def __init__(self, tokens):
        self.chat = types.SimpleNamespace(completions=_FakeCompletions(tokens))


@pytest.fixture
def patch_deps(monkeypatch):
    """공통 의존성 목킹 + create_tracked_task 캡처(코루틴을 닫지 않고 보존)."""

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

    def apply(tokens):
        monkeypatch.setattr(chat_service, "client", _FakeClient(tokens))
        monkeypatch.setattr(chat_service, "analyze_affinity_with_llm", _fake_affinity)
        monkeypatch.setattr(chat_service, "build_memory_context", _fake_mem_ctx)
        monkeypatch.setattr(chat_service, "resolve_model_endpoint", _fake_resolve)
        monkeypatch.setattr(chat_service, "get_store", lambda: None)
        monkeypatch.setattr(chat_service, "create_tracked_task", _capture_tracked)
        monkeypatch.setattr(chat_service, "quick_score", lambda *a, **k: 0.9)
        monkeypatch.setattr(chat_service, "check_content", lambda text: (True, ""))
        return tracked

    return apply


async def _collect(gen):
    parts, done = [], None
    async for item in gen:
        if isinstance(item, chat_service.StreamDone):
            done = item
        else:
            parts.append(item)
    return parts, done


def _base_kwargs(**over):
    kw = dict(
        message="안녕",
        mbti="ENFP",
        speech_style="반말",
        relationship="친구",
        nickname="유저",
        affinity_level=3,
        conversation_history=[],
        character_name="캐릭터",
        character_id="",
        room_id="room-1",
    )
    kw.update(over)
    return kw


async def _close_untracked(tracked, keep_name):
    for name, coro in tracked:
        if name != keep_name:
            try:
                coro.close()
            except Exception:
                pass


@pytest.mark.asyncio
async def test_stream_reply_records_turn_latency_event(patch_deps, monkeypatch):
    tracked = patch_deps(['[{"text":"안녕","emotion":"HAPPY"}]'])

    recorded: list[dict] = []

    async def _fake_record_event_async(event_type, room_id="", character_id="", user_id="", payload=None):
        recorded.append(dict(
            event_type=event_type,
            room_id=room_id,
            character_id=character_id,
            user_id=user_id,
            payload=payload or {},
        ))

    monkeypatch.setattr(chat_service, "record_event_async", _fake_record_event_async)

    parts, done = await _collect(
        chat_service.stream_reply(**_base_kwargs(room_id="room-latency"))
    )
    assert done is not None
    assert parts

    latency_task = next((c for n, c in tracked if n == "turn-latency"), None)
    assert latency_task is not None, "turn-latency 백그라운드 태스크가 스케줄되어야 함"
    await latency_task
    await _close_untracked(tracked, "turn-latency")

    assert len(recorded) == 1
    event = recorded[0]
    assert event["event_type"] == "turn_latency"
    assert event["room_id"] == "room-latency"

    payload = event["payload"]
    for key in ("t_memory_ms", "t_rag_ms", "t_first_token_ms"):
        assert key in payload, f"payload에 {key} 구간이 있어야 함"
        assert isinstance(payload[key], (int, float))
        assert payload[key] >= 0

    assert payload["streaming"] is True
    assert "model_id" in payload


@pytest.mark.asyncio
async def test_generate_reply_records_turn_latency_event(patch_deps, monkeypatch):
    tracked = patch_deps([])  # generate_reply는 스트림이 아니라 completions.create 결과를 직접 사용

    async def _fake_create(**kwargs):
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(
                message=types.SimpleNamespace(
                    content='[{"text":"안녕","emotion":"HAPPY"}]'
                )
            )],
            usage=types.SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )

    monkeypatch.setattr(chat_service.client.chat.completions, "create", _fake_create)

    recorded: list[dict] = []

    async def _fake_record_event_async(event_type, room_id="", character_id="", user_id="", payload=None):
        recorded.append(dict(event_type=event_type, room_id=room_id, payload=payload or {}))

    monkeypatch.setattr(chat_service, "record_event_async", _fake_record_event_async)

    replies, affinity_delta = await chat_service.generate_reply(
        **_base_kwargs(room_id="room-latency-2")
    )
    assert replies

    latency_task = next((c for n, c in tracked if n == "turn-latency"), None)
    assert latency_task is not None
    await latency_task
    await _close_untracked(tracked, "turn-latency")

    assert len(recorded) == 1
    event = recorded[0]
    assert event["event_type"] == "turn_latency"
    assert event["room_id"] == "room-latency-2"
    payload = event["payload"]
    for key in ("t_memory_ms", "t_rag_ms", "t_first_token_ms"):
        assert key in payload
    assert payload["streaming"] is False
