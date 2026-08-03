"""P0-S3 회귀 테스트: 위기 감지 결과가 실제 생성 경로까지 배선되는지 검증.

수정 전 결함(2026-08-03 회의):
1. routers/chat.py가 select_model_for_crisis 결과를 로그·이벤트 payload에만
   쓰고 generate_reply/stream_reply에 넘기지 않아, Tier1 자해 신호 턴도
   복잡도 분류에 따라 mini로 처리될 수 있었다.
2. _build_crisis_hint가 만든 위기 대응 지침(검증/마음챙김/마이크로 행동)이
   LoRA 제너레이터에만 전달됐고 그 경로는 ab_variant 부재로 도달 불가라,
   위기 지침이 실질적으로 어디에도 적용되지 않았다 — 사용자에게 가는 건
   응답 앞에 붙는 정형 문구뿐이고 캐릭터 응답 자체는 위기를 몰랐다.

수정 후 계약:
- crisis_tier>=1 이면 복잡도/A/B/파인튜닝 판정과 무관하게 LLM_MODEL_COMPLEX
- crisis_hint는 system 메시지 **맨 끝**(safety_prompt 뒤)에 주입
- crisis_tier=0 & crisis_hint="" 이면 프롬프트가 기존과 바이트 단위로 동일
- 논스트림/스트림 라우터 경로 모두에서 실제로 전달된다
"""

import types

import pytest

from app import chat_service
from app.config import LLM_MODEL_COMPLEX, LLM_MODEL_SIMPLE
from app.models import ChatRequest, HistoryMessage, ReplyPart
from app.routers import chat as chat_router

# detect_crisis_v2 → (True, 1) 이고 classify_crisis_type → self_criticism 인 입력
# (즉 _build_crisis_hint가 비어있지 않은 지침을 만든다)
CRISIS_MESSAGE = "자해하고 싶어. 나는 왜 이래"
SIMPLE_MESSAGE = "ㅇㅇ"


# ── 1. 모델 승격 (라우팅 단위) ──────────────────────────────────────────────


def test_crisis_tier1_promotes_simple_message_to_complex_model():
    """simple로 분류되는 짧은 메시지라도 crisis_tier>=1이면 상위 모델을 쓴다."""
    model_id, _variant, complexity = chat_service._route_model_with_complexity(
        "", SIMPLE_MESSAGE, 0, crisis_tier=1
    )
    assert complexity == "simple", "복잡도 분류기 원판정은 그대로 보존되어야 함"
    assert model_id == LLM_MODEL_COMPLEX


def test_no_crisis_keeps_complexity_routing_result():
    """crisis_tier=0이면 기존 복잡도 라우팅 결과 그대로(회귀 방지)."""
    model_id, _variant, complexity = chat_service._route_model_with_complexity(
        "", SIMPLE_MESSAGE, 0, crisis_tier=0
    )
    assert complexity == "simple"
    assert model_id == LLM_MODEL_SIMPLE


def test_crisis_tier2_also_promotes():
    model_id, _v, _c = chat_service._route_model_with_complexity(
        "", SIMPLE_MESSAGE, 0, crisis_tier=2
    )
    assert model_id == LLM_MODEL_COMPLEX


def test_crisis_overrides_finetuned_model(monkeypatch):
    """파인튜닝 모델이 선택돼도 위기 턴은 상위 모델로 승격(select_model_for_crisis 의도)."""
    monkeypatch.setattr(
        chat_service, "get_model_for_character", lambda cid, *a, **k: "ft:mbti-custom-v1"
    )
    # 대조: 비위기 턴은 기존대로 파인튜닝 모델 우선
    base_model, _v, _c = chat_service._route_model_with_complexity(
        "char-1", SIMPLE_MESSAGE, 0, crisis_tier=0
    )
    assert base_model == "ft:mbti-custom-v1"

    crisis_model, _v2, _c2 = chat_service._route_model_with_complexity(
        "char-1", SIMPLE_MESSAGE, 0, crisis_tier=1
    )
    assert crisis_model == LLM_MODEL_COMPLEX


def test_unknown_tier_never_demotes():
    """알 수 없는 tier 값이 상위 모델을 하위로 강등시키면 안 된다(안전 방향만 허용)."""
    model_id, _v, _c = chat_service._route_model_with_complexity(
        "", "요즘 진짜 고민이 많아서 너무 힘들어... 어떻게 해야 할지 모르겠어", 3, crisis_tier=9
    )
    assert model_id == LLM_MODEL_COMPLEX


# ── 2. 프롬프트 주입 (_build_chat_messages) ────────────────────────────────


def _msg_kwargs(**over):
    kw = dict(
        mbti="INFP",
        speech_style="반말",
        relationship="친구",
        nickname="유저",
        character_name="캐릭터",
        affinity_level=2,
        user_mbti="ENFP",
        persona_raw="",
        persona_summary="",
        dialogue_prompt="",
        visual_prompt="",
        memory_dicts=None,
        mem_ctx="",
        episode_context="",
        mood=None,
        conversation_history=[],
        message="안녕",
    )
    kw.update(over)
    return kw


def test_crisis_hint_appended_at_end_of_system_message():
    hint = "\n\n[위기 응답 지침 - 테스트]\n검증하고 마음챙김을 유도한다."
    base = chat_service._build_chat_messages(**_msg_kwargs())
    with_hint = chat_service._build_chat_messages(**_msg_kwargs(crisis_hint=hint))

    base_sys = base[0]["content"]
    hinted_sys = with_hint[0]["content"]

    assert hinted_sys.endswith(hint), "위기 지침은 system 메시지 맨 끝에 와야 한다"
    # safety_prompt 뒤에 붙어야 한다 = 기존 프롬프트 전체가 그대로 앞에 남는다
    assert hinted_sys == base_sys + hint
    # system 메시지 외 다른 메시지는 영향 없음
    assert base[1:] == with_hint[1:]


def test_empty_crisis_hint_is_byte_identical():
    """빈 hint는 기존 프롬프트와 바이트 단위로 동일해야 한다(골든 테스트 불변)."""
    base = chat_service._build_chat_messages(**_msg_kwargs())
    empty = chat_service._build_chat_messages(**_msg_kwargs(crisis_hint=""))
    assert base == empty
    assert base[0]["content"].encode("utf-8") == empty[0]["content"].encode("utf-8")


# ── 3. generate_reply / stream_reply 통합 ─────────────────────────────────


class _FakeCompletions:
    """create() 호출 kwargs를 캡처하는 논스트림 목."""

    def __init__(self, content='[{"text": "괜찮아?", "emotion": "WORRIED"}]'):
        self.calls = []
        self._content = content

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(
                message=types.SimpleNamespace(content=self._content)
            )],
            usage=types.SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )


class _FakeStream:
    def __init__(self, tokens):
        self._tokens = list(tokens)

    def __aiter__(self):
        self._it = iter([
            types.SimpleNamespace(
                choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content=t))],
                usage=None,
            )
            for t in self._tokens
        ])
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


class _FakeStreamCompletions:
    def __init__(self, tokens):
        self.calls = []
        self._tokens = tokens

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeStream(self._tokens)


@pytest.fixture
def patch_service(monkeypatch):
    """chat_service 공통 의존성 목킹 (test_stream_reply.py 패턴)."""

    async def _fake_affinity(*a, **k):
        return 3

    async def _fake_mem_ctx(*a, **k):
        return ""

    async def _fake_resolve(model_id, ab_variant):
        return model_id, ""

    def _fake_tracked(coro, name=""):
        try:
            coro.close()
        except Exception:
            pass
        return None

    monkeypatch.setattr(chat_service, "analyze_affinity_with_llm", _fake_affinity)
    monkeypatch.setattr(chat_service, "build_memory_context", _fake_mem_ctx)
    monkeypatch.setattr(chat_service, "resolve_model_endpoint", _fake_resolve)
    monkeypatch.setattr(chat_service, "get_store", lambda: None)
    monkeypatch.setattr(chat_service, "create_tracked_task", _fake_tracked)
    monkeypatch.setattr(chat_service, "quick_score", lambda *a, **k: 0.9)
    monkeypatch.setattr(chat_service, "check_content", lambda text: (True, ""))

    def _install(completions):
        monkeypatch.setattr(
            chat_service, "client",
            types.SimpleNamespace(chat=types.SimpleNamespace(completions=completions)),
        )
        return completions

    return _install


def _gen_kwargs(**over):
    kw = dict(
        message=SIMPLE_MESSAGE,
        mbti="INFP",
        speech_style="반말",
        relationship="친구",
        nickname="유저",
        affinity_level=2,
        conversation_history=[],
        character_name="캐릭터",
        character_id="",
        room_id="room-crisis",
    )
    kw.update(over)
    return kw


@pytest.mark.asyncio
async def test_generate_reply_uses_complex_model_and_injects_hint(patch_service):
    hint = "\n\n[위기 응답 지침 - 테스트]\n검증부터 하라."
    comps = patch_service(_FakeCompletions())

    replies, _delta = await chat_service.generate_reply(
        **_gen_kwargs(crisis_tier=1, crisis_hint=hint)
    )

    assert replies
    assert len(comps.calls) == 1
    call = comps.calls[0]
    assert call["model"] == LLM_MODEL_COMPLEX, "위기 턴은 상위 모델로 승격되어야 함"
    assert call["messages"][0]["content"].endswith(hint)


@pytest.mark.asyncio
async def test_generate_reply_without_crisis_unchanged(patch_service):
    """crisis 인자 미지정 = 기존 동작(simple 모델 + 지침 없는 프롬프트)."""
    comps = patch_service(_FakeCompletions())

    await chat_service.generate_reply(**_gen_kwargs())

    call = comps.calls[0]
    assert call["model"] == LLM_MODEL_SIMPLE
    assert "[위기 응답 지침" not in call["messages"][0]["content"]


@pytest.mark.asyncio
async def test_stream_reply_uses_complex_model_and_injects_hint(patch_service):
    hint = "\n\n[위기 응답 지침 - 테스트]\n마음챙김을 유도하라."
    comps = patch_service(_FakeStreamCompletions(['[{"text":"괜찮아?","emotion":"WORRIED"}]']))

    parts = []
    async for item in chat_service.stream_reply(**_gen_kwargs(crisis_tier=1, crisis_hint=hint)):
        if not isinstance(item, chat_service.StreamDone):
            parts.append(item)

    assert parts
    assert len(comps.calls) == 1
    call = comps.calls[0]
    assert call["model"] == LLM_MODEL_COMPLEX
    assert call["messages"][0]["content"].endswith(hint)


@pytest.mark.asyncio
async def test_stream_reply_without_crisis_unchanged(patch_service):
    comps = patch_service(_FakeStreamCompletions(['[{"text":"ㅇㅇ","emotion":"NEUTRAL"}]']))

    async for _ in chat_service.stream_reply(**_gen_kwargs()):
        pass

    call = comps.calls[0]
    assert call["model"] == LLM_MODEL_SIMPLE
    assert "[위기 응답 지침" not in call["messages"][0]["content"]


@pytest.mark.asyncio
async def test_turn_latency_payload_reports_crisis_tier(monkeypatch):
    recorded = []

    async def _fake_record(event_type, room_id="", character_id="", user_id="", payload=None):
        recorded.append((event_type, payload or {}))

    monkeypatch.setattr(chat_service, "record_event_async", _fake_record)

    await chat_service._record_turn_latency_event(
        room_id="r", character_id="c", model_id=LLM_MODEL_COMPLEX, streaming=False,
        t_memory_ms=1.0, t_rag_ms=2.0, t_first_token_ms=3.0,
        complexity="simple", crisis_tier=1,
    )

    assert recorded[0][0] == "turn_latency"
    payload = recorded[0][1]
    # complexity는 분류기 원판정 그대로, crisis_tier로 승격 여부를 식별
    assert payload["complexity"] == "simple"
    assert payload["crisis_tier"] == 1
    assert payload["model_id"] == LLM_MODEL_COMPLEX


# ── 4. 라우터 배선 ─────────────────────────────────────────────────────────


def _unwrap(fn):
    """slowapi @limiter.limit 데코레이터를 벗겨 원 함수를 얻는다."""
    return getattr(fn, "__wrapped__", fn)


def _req(**over) -> ChatRequest:
    kw = dict(message=CRISIS_MESSAGE, mbti="INFP", nickname="유저", affinity_level=1)
    kw.update(over)
    return ChatRequest(**kw)


@pytest.fixture
def patch_router(monkeypatch):
    """라우터 경로용 공통 목킹(DB/외부 I/O 제거)."""

    async def _fake_prepare(req, user):
        return {
            "room_id": "room-1",
            "state": types.SimpleNamespace(turn_count=1, next_hook="", next_goal="", character_id="INFP"),
            "effective_character_id": "INFP",
            "callback_key": None,
            "merged_memories": [],
        }

    async def _fake_finalize(req, user, **kwargs):
        return {
            "room_id": kwargs.get("room_id", "room-1"),
            "replies": kwargs.get("replies", []),
            "affinity_delta": kwargs.get("affinity_delta", 0),
            "night_diary_generated": False,
            "next_hook": "",
            "next_goal": "",
        }

    async def _fake_record_event_async(**kwargs):
        return None

    async def _fake_gate(req, user, request):
        return None

    monkeypatch.setattr(chat_router, "_prepare_chat_turn", _fake_prepare)
    monkeypatch.setattr(chat_router, "_finalize_chat_turn", _fake_finalize)
    monkeypatch.setattr(chat_router, "record_event_async", _fake_record_event_async)
    monkeypatch.setattr(chat_router, "create_tracked_task", lambda coro, name="": coro.close())
    monkeypatch.setattr(chat_router, "_gate_user", _fake_gate)


@pytest.mark.asyncio
async def test_run_chat_pipeline_forwards_crisis_args(patch_router, monkeypatch):
    captured = {}

    async def _fake_generate_reply(**kwargs):
        captured.update(kwargs)
        return [ReplyPart(text="괜찮아?", emotion="WORRIED")], 0

    monkeypatch.setattr(chat_router, "generate_reply", _fake_generate_reply)

    await chat_router._run_chat_pipeline(
        _req(), None, crisis_tier=1, crisis_hint="HINT-NONSTREAM"
    )

    assert captured["crisis_tier"] == 1
    assert captured["crisis_hint"] == "HINT-NONSTREAM"


@pytest.mark.asyncio
async def test_openai_event_generator_forwards_crisis_args(patch_router, monkeypatch):
    captured = {}

    async def _fake_stream_reply(**kwargs):
        captured.update(kwargs)
        yield ReplyPart(text="괜찮아?", emotion="WORRIED")
        yield chat_service.StreamDone(affinity_delta=0, full_text="괜찮아?")

    monkeypatch.setattr(chat_router, "stream_reply", _fake_stream_reply)

    async def _noop_record(room_id):
        return None

    gen = chat_router._openai_event_generator(
        _req(), None, None, _noop_record,
        lambda p: {"event": "message", "data": "{}"},
        lambda m: {"event": "done", "data": "{}"},
        crisis_tier=1, crisis_hint="HINT-STREAM",
    )
    async for _ in gen:
        pass

    assert captured["crisis_tier"] == 1
    assert captured["crisis_hint"] == "HINT-STREAM"


@pytest.mark.asyncio
async def test_send_message_endpoint_wires_detected_crisis(patch_router, monkeypatch):
    """실제 detect_crisis_v2/_build_crisis_hint 결과가 파이프라인까지 전달된다."""
    captured = {}

    async def _fake_pipeline(req, user, crisis_tier=0, crisis_hint="", **_kwargs):
        captured["crisis_tier"] = crisis_tier
        captured["crisis_hint"] = crisis_hint
        return {
            "room_id": "room-1",
            "replies": [ReplyPart(text="괜찮아?", emotion="WORRIED")],
            "affinity_delta": 0,
            "night_diary_generated": False,
            "next_hook": "",
            "next_goal": "",
        }

    monkeypatch.setattr(chat_router, "_run_chat_pipeline", _fake_pipeline)

    resp = await _unwrap(chat_router.send_message)(None, _req(), None)

    assert captured["crisis_tier"] == 1, "Tier1 위기가 파이프라인에 전달되어야 함"
    assert "[위기 응답 지침" in captured["crisis_hint"], "위기 지침이 생성·전달되어야 함"
    # 기존 동작(정형 안내 문구 선두 삽입)도 유지
    assert resp.replies[0].emotion == "SAD"


@pytest.mark.asyncio
async def test_send_message_endpoint_no_crisis_passes_defaults(patch_router, monkeypatch):
    captured = {}

    async def _fake_pipeline(req, user, crisis_tier=0, crisis_hint="", **_kwargs):
        captured["crisis_tier"] = crisis_tier
        captured["crisis_hint"] = crisis_hint
        return {
            "room_id": "room-1",
            "replies": [ReplyPart(text="안녕!", emotion="HAPPY")],
            "affinity_delta": 0,
            "night_diary_generated": False,
            "next_hook": "",
            "next_goal": "",
        }

    monkeypatch.setattr(chat_router, "_run_chat_pipeline", _fake_pipeline)

    await _unwrap(chat_router.send_message)(None, _req(message="오늘 날씨 좋다"), None)

    assert captured["crisis_tier"] == 0
    assert captured["crisis_hint"] == ""


@pytest.mark.asyncio
async def test_stream_message_endpoint_wires_detected_crisis(patch_router, monkeypatch):
    captured = {}

    async def _fake_generator(req, user, crisis_reply, record_crisis, message_event,
                              done_event, crisis_tier=0, crisis_hint="", **_kwargs):
        captured["crisis_tier"] = crisis_tier
        captured["crisis_hint"] = crisis_hint
        if False:
            yield None

    monkeypatch.setattr(chat_router, "_openai_event_generator", _fake_generator)

    resp = await _unwrap(chat_router.stream_message)(None, _req(), None)
    # EventSourceResponse가 감싼 제너레이터를 실제로 소비해 인자를 확정
    async for _ in resp.body_iterator:
        pass

    assert captured["crisis_tier"] == 1
    assert "[위기 응답 지침" in captured["crisis_hint"]
