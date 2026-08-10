"""H3 / M-G / M-I(2026-08-04 점검): 스트림 수명주기 회귀 테스트.

H3 — SSE 조기 종료 시 태스크 누수 + 후처리 유실
  - stream_reply의 yield가 try 안에 있고 `except Exception`은 GeneratorExit를
    잡지 못해, 클라이언트가 스트림을 조기 종료하면 affinity_task가 고아로
    남고 AB/api_usage/turn_latency/품질평가가 통째로 유실됐다.
  - routers/chat.py `_openai_event_generator`도 중단되면 `_finalize_chat_turn`이
    아예 실행되지 않아 chat_turn 이벤트·messages 적재가 유실됐다.

M-G — 실패/서킷오픈 턴은 turn_latency를 남기지 않아 레이턴시 분포에
      생존편향이 있었다(느려서 실패한 턴이 통계에서 사라짐).

M-I — `_finalize_chat_turn` 예외 시 done 이벤트가 전송되지 않아 클라이언트가
      타임아웃까지 매달렸다.
"""

import asyncio
import json
import types

import pytest

from app import chat_service
from app.chat_service import StreamDone
from app.circuit_breaker import CircuitOpenError
from app.models import ChatRequest, HistoryMessage, ReplyPart
from app.routers import chat as chat_router


# ══════════════════════════════════════════════════════════════════════════
# stream_reply (H3 / M-G)
# ══════════════════════════════════════════════════════════════════════════


class _FakeChunk:
    def __init__(self, content, usage=None):
        if content is None:
            self.choices = []
        else:
            self.choices = [types.SimpleNamespace(delta=types.SimpleNamespace(content=content))]
        self.usage = usage


class _FakeStream:
    def __init__(self, tokens):
        self._tokens = list(tokens)

    def __aiter__(self):
        self._it = iter([_FakeChunk(t) for t in self._tokens])
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


class _FakeClient:
    def __init__(self, tokens):
        async def _create(**kwargs):
            return _FakeStream(tokens)

        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=_create))


@pytest.fixture
def stream_ctx(monkeypatch):
    """stream_reply/generate_reply 공용 목킹.

    - create_tracked_task는 (name, coro)로 캡처만 하고 실행하지 않는다.
    - _record_turn_latency_event는 kwargs를 기록하는 목으로 교체해
      outcome 필드를 직접 검증한다.
    """
    ctx = types.SimpleNamespace(
        tracked=[],
        latency=[],
        affinity_cancelled=False,
        affinity_started=asyncio.Event(),
        affinity_delay=30.0,
    )

    def _capture(coro, name=""):
        ctx.tracked.append((name, coro))
        return None

    async def _fake_latency(**kwargs):
        ctx.latency.append(kwargs)

    async def _slow_affinity(*a, **k):
        ctx.affinity_started.set()
        try:
            # 기본값은 "취소되지 않으면 영원히 매달리는" 태스크 —
            # 취소 누락을 테스트가 확실히 잡아낸다.
            await asyncio.sleep(ctx.affinity_delay)
            return 3
        except asyncio.CancelledError:
            ctx.affinity_cancelled = True
            raise

    async def _fake_resolve(model_id, ab_variant):
        return model_id, ""

    async def _fake_mem_ctx(*a, **k):
        return ""

    def apply(tokens, affinity_delay=30.0):
        ctx.affinity_delay = affinity_delay
        monkeypatch.setattr(chat_service, "client", _FakeClient(tokens))
        monkeypatch.setattr(chat_service, "analyze_affinity_with_llm", _slow_affinity)
        monkeypatch.setattr(chat_service, "build_memory_context", _fake_mem_ctx)
        monkeypatch.setattr(chat_service, "resolve_model_endpoint", _fake_resolve)
        monkeypatch.setattr(chat_service, "get_store", lambda: None)
        monkeypatch.setattr(chat_service, "create_tracked_task", _capture)
        monkeypatch.setattr(chat_service, "quick_score", lambda *a, **k: 0.9)
        monkeypatch.setattr(chat_service, "check_content", lambda text: (True, ""))
        monkeypatch.setattr(chat_service, "_record_turn_latency_event", _fake_latency)
        return ctx

    ctx.apply = apply
    yield ctx
    for _name, coro in ctx.tracked:
        try:
            coro.close()
        except Exception:
            pass


def _kwargs(**over):
    kw = dict(
        message="안녕",
        mbti="ENFP",
        speech_style="반말",
        relationship="친구",
        nickname="유저",
        affinity_level=3,
        conversation_history=[HistoryMessage(role="user", content="이전")],
        character_name="캐릭터",
        character_id="char-life",
        room_id="room-life",
    )
    kw.update(over)
    return kw


# 말풍선 2개 — 첫 번째를 받은 뒤 제너레이터가 yield 지점에 멈춰 있게 한다.
_TWO_BUBBLES = ['[{"text":"안녕","emotion":"HAPPY"},', '{"text":"반가워","emotion":"LOVE"}]']


async def _settle():
    """이벤트 루프에 제어권을 넘겨 태스크 시작/취소가 반영되게 한다."""
    for _ in range(5):
        await asyncio.sleep(0)


async def _assert_no_leaked_tasks(before: set):
    """호출 전 스냅샷 이후 새로 생긴 태스크 중 미완인 것이 없어야 한다."""
    await _settle()
    leaked = [t for t in asyncio.all_tasks() if t not in before and not t.done()]
    assert not leaked, f"고아 태스크가 남았다: {[t.get_coro() for t in leaked]}"


async def _latency_kwargs(ctx):
    """캡처된 turn-latency 태스크를 실행해 기록된 kwargs를 반환."""
    coro = next((c for n, c in ctx.tracked if n == "turn-latency"), None)
    if coro is None:
        return None
    await coro
    ctx.tracked = [(n, c) for n, c in ctx.tracked if c is not coro]
    return ctx.latency[-1]


@pytest.mark.asyncio
async def test_early_close_cancels_affinity_task(stream_ctx):
    """H3: 클라 조기 종료(aclose) 시 병렬 호감도 태스크가 취소돼야 한다."""
    ctx = stream_ctx.apply(_TWO_BUBBLES)

    before = set(asyncio.all_tasks())
    gen = chat_service.stream_reply(**_kwargs())
    first = await gen.__anext__()
    assert isinstance(first, ReplyPart)

    # 호감도 태스크가 실제로 실행 중인 상태를 만든다(그래야 취소가 의미를 갖는다)
    await _settle()
    assert ctx.affinity_started.is_set()
    assert ctx.affinity_cancelled is False

    await gen.aclose()
    await _settle()

    assert ctx.affinity_cancelled is True, "조기 종료 시 affinity_task가 고아로 남으면 안 된다"
    await _assert_no_leaked_tasks(before)


@pytest.mark.asyncio
async def test_early_close_still_records_turn_latency_as_aborted(stream_ctx):
    """H3+M-G: 조기 종료 턴도 계측을 남긴다(outcome='aborted')."""
    ctx = stream_ctx.apply(_TWO_BUBBLES)

    gen = chat_service.stream_reply(**_kwargs())
    await gen.__anext__()
    assert not any(n == "turn-latency" for n, _ in ctx.tracked)

    await gen.aclose()

    payload = await _latency_kwargs(ctx)
    assert payload is not None, "조기 종료에도 turn_latency가 스케줄돼야 한다"
    assert payload["outcome"] == "aborted"
    assert payload["streaming"] is True
    assert payload["room_id"] == "room-life"


@pytest.mark.asyncio
async def test_normal_stream_records_outcome_ok_once(stream_ctx):
    """mutation 방어: 정상 경로는 outcome='ok'로 정확히 1회만 기록한다."""
    ctx = stream_ctx.apply(_TWO_BUBBLES, affinity_delay=0)

    parts = []
    done = None
    async for item in chat_service.stream_reply(**_kwargs()):
        if isinstance(item, StreamDone):
            done = item
        else:
            parts.append(item)

    assert done is not None
    assert [p.text for p in parts] == ["안녕", "반가워"]
    assert len([n for n, _ in ctx.tracked if n == "turn-latency"]) == 1

    payload = await _latency_kwargs(ctx)
    assert payload["outcome"] == "ok"


@pytest.mark.asyncio
async def test_stream_error_records_outcome_error(stream_ctx):
    """M-G: 스트리밍 예외 턴도 turn_latency를 남긴다(생존편향 제거)."""
    ctx = stream_ctx.apply([])

    async def _boom(**kwargs):
        raise RuntimeError("stream boom")

    chat_service.client.chat.completions.create = _boom

    parts = []
    done = None
    async for item in chat_service.stream_reply(**_kwargs()):
        if isinstance(item, StreamDone):
            done = item
        else:
            parts.append(item)

    assert done is not None
    assert parts[0].emotion == "SURPRISED"

    payload = await _latency_kwargs(ctx)
    assert payload is not None, "실패 턴도 turn_latency를 남겨야 한다"
    assert payload["outcome"] == "error"


@pytest.mark.asyncio
async def test_stream_circuit_open_records_outcome_circuit_open(stream_ctx, monkeypatch):
    """M-G: 서킷 OPEN 턴도 turn_latency를 남긴다."""
    ctx = stream_ctx.apply(_TWO_BUBBLES)

    class _OpenCircuit:
        async def call(self, coro):
            coro.close()
            raise CircuitOpenError("open")

    monkeypatch.setattr(chat_service, "get_openai_circuit", lambda: _OpenCircuit())

    before = set(asyncio.all_tasks())
    done = None
    async for item in chat_service.stream_reply(**_kwargs()):
        if isinstance(item, StreamDone):
            done = item

    assert done is not None
    payload = await _latency_kwargs(ctx)
    assert payload is not None
    assert payload["outcome"] == "circuit_open"
    # 서킷 오픈 early-return 경로에서도 병렬 태스크가 정리돼야 한다
    await _assert_no_leaked_tasks(before)


@pytest.mark.asyncio
async def test_generate_reply_error_records_outcome_error(stream_ctx):
    """M-G(논스트림): generate_reply 실패 턴도 turn_latency를 남긴다."""
    ctx = stream_ctx.apply([])

    async def _boom(**kwargs):
        raise RuntimeError("nonstream boom")

    chat_service.client.chat.completions.create = _boom

    before = set(asyncio.all_tasks())
    replies, delta = await chat_service.generate_reply(**_kwargs())
    assert replies and replies[0].emotion == "SURPRISED"
    assert delta == 0

    payload = await _latency_kwargs(ctx)
    assert payload is not None
    assert payload["outcome"] == "error"
    assert payload["streaming"] is False
    await _assert_no_leaked_tasks(before)


@pytest.mark.asyncio
async def test_generate_reply_circuit_open_records_outcome(stream_ctx, monkeypatch):
    ctx = stream_ctx.apply(_TWO_BUBBLES)

    class _OpenCircuit:
        async def call(self, coro):
            coro.close()
            raise CircuitOpenError("open")

    monkeypatch.setattr(chat_service, "get_openai_circuit", lambda: _OpenCircuit())

    before = set(asyncio.all_tasks())
    replies, _ = await chat_service.generate_reply(**_kwargs())
    assert replies

    payload = await _latency_kwargs(ctx)
    assert payload is not None
    assert payload["outcome"] == "circuit_open"
    # 서킷 오픈 early-return 경로는 이전에 태스크를 정리하지 않아 고아가 남았다
    await _assert_no_leaked_tasks(before)


@pytest.mark.asyncio
async def test_turn_latency_payload_carries_outcome(monkeypatch):
    """payload 계약: outcome 필드 추가, 기존 필드는 불변."""
    recorded = []

    async def _fake_record_event_async(event_type, room_id="", character_id="", user_id="", payload=None):
        recorded.append((event_type, payload or {}))

    monkeypatch.setattr(chat_service, "record_event_async", _fake_record_event_async)

    await chat_service._record_turn_latency_event(
        room_id="r", character_id="c", model_id="gpt-4.1-mini", streaming=True,
        t_memory_ms=1.0, t_rag_ms=2.0, t_first_token_ms=3.0,
    )
    await chat_service._record_turn_latency_event(
        room_id="r", character_id="c", model_id="gpt-4.1-mini", streaming=False,
        t_memory_ms=1.0, t_rag_ms=2.0, t_first_token_ms=3.0, outcome="circuit_open",
    )

    assert recorded[0][1]["outcome"] == "ok", "기본값은 ok — 기존 호출부 동작 불변"
    assert recorded[1][1]["outcome"] == "circuit_open"
    for key in ("model_id", "streaming", "t_memory_ms", "t_rag_ms", "t_first_token_ms",
                "complexity", "crisis_tier", "t_memory_cache_hit", "t_gate_ms"):
        assert key in recorded[0][1]


# ══════════════════════════════════════════════════════════════════════════
# _openai_event_generator (H3 ② / M-I)
# ══════════════════════════════════════════════════════════════════════════


def _fake_state(turn_count=3, next_hook="다음 흐름", next_goal="다음 목표"):
    return types.SimpleNamespace(
        turn_count=turn_count,
        next_hook=next_hook,
        next_goal=next_goal,
        character_id="ENFP",
    )


@pytest.fixture
def router_ctx(monkeypatch):
    """_openai_event_generator를 DB/LLM 없이 돌리기 위한 목킹."""
    ctx = types.SimpleNamespace(events=[], tracked=[], persists=[])

    async def _fake_record_event_async(**kwargs):
        ctx.events.append(kwargs)

    def _fake_tracked(coro, name=""):
        ctx.tracked.append((name, coro))
        return None

    async def _fake_persist(uid, character_mbti, user_message, assistant_text):
        ctx.persists.append((uid, user_message, assistant_text))

    monkeypatch.setattr(chat_router, "record_event_async", _fake_record_event_async)
    monkeypatch.setattr(chat_router, "create_tracked_task", _fake_tracked)
    monkeypatch.setattr(chat_router, "_persist_chat_data", _fake_persist)
    monkeypatch.setattr(chat_router, "mark_callback_used", lambda *a, **k: None)
    monkeypatch.setattr(chat_router, "get_story_state", lambda *a, **k: _fake_state())
    monkeypatch.setattr(chat_router, "bump_turn_and_get_state", lambda *a, **k: _fake_state())
    monkeypatch.setattr(chat_router, "maybe_build_callback_hint", lambda state: (None, ""))
    monkeypatch.setattr(chat_router, "build_story_memory_items", lambda state, hint: [])

    ctx.inner_closed = False

    def install_stream(parts, affinity_delta=4):
        async def _fake_stream_reply(**kwargs):
            try:
                for part in parts:
                    yield part
                yield StreamDone(
                    affinity_delta=affinity_delta,
                    full_text=" ".join(p.text for p in parts),
                )
            finally:
                # stream_reply의 finally(태스크 취소·계측)에 해당하는 지점
                ctx.inner_closed = True

        monkeypatch.setattr(chat_router, "stream_reply", _fake_stream_reply)

    ctx.install_stream = install_stream
    yield ctx
    for _name, coro in ctx.tracked:
        try:
            coro.close()
        except Exception:
            pass


async def _no_crisis(room_id: str) -> None:
    return None


def _gen(user=None):
    req = ChatRequest(message="안녕", mbti="ENFP", nickname="유저")
    return chat_router._openai_event_generator(
        req,
        user or {"uid": "uid-life"},
        None,
        _no_crisis,
        chat_router._sse_message_event,
        chat_router._sse_done_event,
    )


@pytest.mark.asyncio
async def test_finalize_runs_even_when_client_aborts_mid_stream(router_ctx):
    """H3②: 조기 종료여도 후처리(_finalize_chat_turn)가 보장돼야 한다."""
    router_ctx.install_stream(
        [ReplyPart(text="안녕", emotion="HAPPY"), ReplyPart(text="반가워", emotion="LOVE")]
    )

    gen = _gen()
    first = await gen.__anext__()
    assert first["event"] == "message"
    assert not any(n == "finalize-chat-turn" for n, _ in router_ctx.tracked)

    await gen.aclose()

    finalize = next((c for n, c in router_ctx.tracked if n == "finalize-chat-turn"), None)
    assert finalize is not None, "조기 종료 시 후처리가 스케줄돼야 한다"
    await finalize

    turn_events = [e for e in router_ctx.events if e["event_type"] == "chat_turn"]
    assert len(turn_events) == 1, "chat_turn 이벤트가 유실되면 안 된다"
    assert turn_events[0]["user_id"] == "uid-life"


@pytest.mark.asyncio
async def test_inner_stream_generator_is_closed_on_abort(router_ctx):
    """H3: 내부 stream_reply의 finally가 GC 타이밍이 아니라 즉시 실행돼야 한다."""
    router_ctx.install_stream(
        [ReplyPart(text="안녕", emotion="HAPPY"), ReplyPart(text="반가워", emotion="LOVE")]
    )

    gen = _gen()
    await gen.__anext__()
    assert router_ctx.inner_closed is False

    await gen.aclose()

    close_task = next((c for n, c in router_ctx.tracked if n == "close-stream-reply"), None)
    assert close_task is not None, "조기 종료 시 내부 스트림 aclose가 스케줄돼야 한다"
    await close_task
    assert router_ctx.inner_closed is True


@pytest.mark.asyncio
async def test_normal_path_does_not_double_finalize(router_ctx):
    """mutation 방어: 정상 완주 시 후처리를 두 번 실행하면 안 된다."""
    router_ctx.install_stream([ReplyPart(text="안녕", emotion="HAPPY")])

    events = [e async for e in _gen()]
    assert [e["event"] for e in events] == ["message", "done"]

    assert not any(n == "finalize-chat-turn" for n, _ in router_ctx.tracked)
    assert len([e for e in router_ctx.events if e["event_type"] == "chat_turn"]) == 1


@pytest.mark.asyncio
async def test_done_is_sent_even_when_finalize_raises(router_ctx, monkeypatch):
    """M-I: 후처리 예외에도 done을 반드시 보내 클라 타임아웃을 막는다."""
    router_ctx.install_stream([ReplyPart(text="안녕", emotion="HAPPY")])

    async def _boom_finalize(*a, **k):
        raise RuntimeError("night diary boom")

    monkeypatch.setattr(chat_router, "_finalize_chat_turn", _boom_finalize)

    events = [e async for e in _gen()]

    assert [e["event"] for e in events] == ["message", "done"]
    done = json.loads(events[-1]["data"])
    assert set(done) == {
        "affinity_delta",
        "night_diary_generated",
        "next_hook",
        "next_goal",
        "room_id",
    }
    # 최소 meta: affinity_delta는 스트림에서 받은 값 그대로 유지
    assert done["affinity_delta"] == 4
    assert done["night_diary_generated"] is False
    assert done["room_id"] == "uid-life:ENFP:유저"


@pytest.mark.asyncio
async def test_done_carries_real_meta_when_finalize_succeeds(router_ctx):
    """mutation 방어: 정상 경로의 done은 최소 meta가 아니라 실제 메타여야 한다."""
    router_ctx.install_stream([ReplyPart(text="안녕", emotion="HAPPY")])

    events = [e async for e in _gen()]
    done = json.loads(events[-1]["data"])
    assert done["next_hook"] == "다음 흐름"
    assert done["next_goal"] == "다음 목표"
    assert done["affinity_delta"] == 4
