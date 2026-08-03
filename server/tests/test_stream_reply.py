"""stream_reply 유닛테스트 — 말풍선 점진 스트리밍 생성기.

라이브 LLM 없이 목 스트림으로 검증:
- 토큰이 임의 경계로 쪼개져도 말풍선을 순차 방출
- 형식 파괴 시 _parse_reply 폴백
- 콘텐츠 안전 차단
- 항상 StreamDone(affinity_delta) 으로 종료
"""

import types

import pytest

from app import chat_service
from app.chat_service import StreamDone
from app.models import HistoryMessage, ReplyPart


class _FakeChunk:
    def __init__(self, content, usage=None):
        # 실제 OpenAI usage 청크는 choices가 빈 리스트다(콘텐츠 없이 usage만
        # 실려 온다) — content=None이면 그 형태를 재현한다.
        if content is None:
            self.choices = []
        else:
            self.choices = [types.SimpleNamespace(delta=types.SimpleNamespace(content=content))]
        self.usage = usage


class _FakeStream:
    def __init__(self, tokens, usage=None):
        self._tokens = list(tokens)
        self._usage = usage  # P7: 마지막에 usage-only 청크를 덧붙이기 위함

    def __aiter__(self):
        chunks = [_FakeChunk(t) for t in self._tokens]
        if self._usage is not None:
            chunks.append(_FakeChunk(None, usage=self._usage))
        self._it = iter(chunks)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


class _FakeCompletions:
    def __init__(self, tokens, usage=None):
        self._tokens = tokens
        self._usage = usage

    async def create(self, **kwargs):
        return _FakeStream(self._tokens, usage=self._usage)


class _FakeClient:
    def __init__(self, tokens, usage=None):
        self.chat = types.SimpleNamespace(completions=_FakeCompletions(tokens, usage=usage))


@pytest.fixture
def patch_deps(monkeypatch):
    """공통 의존성 목킹. tokens 리스트로 스트림을 구성해 반환하는 팩토리."""

    async def _fake_affinity(*a, **k):
        return 3

    async def _fake_mem_ctx(*a, **k):
        return ""

    async def _fake_resolve(model_id, ab_variant):
        return model_id, ""  # base_url 빈값 → active_client = client

    tracked_names = []

    def _fake_tracked(coro, name=""):
        # 백그라운드 태스크 실행 방지: 이름만 기록하고 코루틴 닫아 경고 억제
        tracked_names.append(name)
        try:
            coro.close()
        except Exception:
            pass
        return None

    def apply(tokens, usage=None):
        monkeypatch.setattr(chat_service, "client", _FakeClient(tokens, usage=usage))
        monkeypatch.setattr(chat_service, "analyze_affinity_with_llm", _fake_affinity)
        monkeypatch.setattr(chat_service, "build_memory_context", _fake_mem_ctx)
        monkeypatch.setattr(chat_service, "resolve_model_endpoint", _fake_resolve)
        monkeypatch.setattr(chat_service, "get_store", lambda: None)
        monkeypatch.setattr(chat_service, "create_tracked_task", _fake_tracked)
        monkeypatch.setattr(chat_service, "quick_score", lambda *a, **k: 0.9)
        monkeypatch.setattr(chat_service, "check_content", lambda text: (True, ""))
        return tracked_names  # 테스트가 스케줄된 백그라운드 태스크 이름을 검사

    return apply


async def _collect(gen):
    parts, done = [], None
    async for item in gen:
        if isinstance(item, StreamDone):
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
    )
    kw.update(over)
    return kw


@pytest.mark.asyncio
async def test_streams_bubbles_incrementally(patch_deps):
    # 두 말풍선이 담긴 JSON 배열을 여러 토큰으로 쪼갬 (객체 경계 중간 포함)
    tokens = ['[{"text":"안', '녕!","emotion":"HA', 'PPY"},',
              '{"text":"반가워","emotion":"LOVE"}]']
    patch_deps(tokens)
    parts, done = await _collect(chat_service.stream_reply(**_base_kwargs()))

    assert [p.text for p in parts] == ["안녕!", "반가워"]
    assert [p.emotion for p in parts] == ["HAPPY", "LOVE"]
    assert isinstance(done, StreamDone)
    assert done.affinity_delta == 3
    assert "안녕!" in done.full_text and "반가워" in done.full_text


@pytest.mark.asyncio
async def test_broken_format_falls_back_to_parse_reply(patch_deps):
    # JSON 아님 → 증분 파서 0개 방출 → _parse_reply 폴백으로 최소 1개 방출
    patch_deps(["그냥 평범한 응답 텍스트"])
    parts, done = await _collect(chat_service.stream_reply(**_base_kwargs()))

    assert len(parts) >= 1
    assert all(isinstance(p, ReplyPart) for p in parts)
    assert done is not None
    assert done.full_text != ""


@pytest.mark.asyncio
async def test_unsafe_input_blocked(patch_deps, monkeypatch):
    patch_deps(['[{"text":"x","emotion":"HAPPY"}]'])
    # 입력을 위험으로 판정
    monkeypatch.setattr(chat_service, "check_content", lambda text: (False, "unsafe"))
    parts, done = await _collect(chat_service.stream_reply(**_base_kwargs()))

    assert len(parts) == 1
    assert parts[0].emotion == "SAD"
    assert done.affinity_delta == -2


@pytest.mark.asyncio
async def test_always_ends_with_stream_done_even_on_empty(patch_deps):
    # 빈 배열 → 아무 말풍선 없음 → 안전 기본 응답 + StreamDone
    patch_deps(["[]"])
    parts, done = await _collect(chat_service.stream_reply(**_base_kwargs()))

    assert done is not None
    assert len(parts) >= 1  # 안전 기본 응답 보장


def _history(n):
    # user/assistant 번갈아 n개
    return [
        HistoryMessage(role="user" if i % 2 == 0 else "assistant", content=f"메시지{i}")
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_schedules_memory_extraction_at_interval(patch_deps):
    # 원본 히스토리 길이 10 → 기억 추출 백그라운드 태스크 스케줄
    tracked = patch_deps(['[{"text":"응","emotion":"HAPPY"}]'])
    _, done = await _collect(
        chat_service.stream_reply(**_base_kwargs(conversation_history=_history(10)))
    )
    assert "memory-extraction" in tracked
    assert done is not None


@pytest.mark.asyncio
async def test_no_memory_extraction_off_interval(patch_deps):
    # 원본 길이 11 → 추출 미발동 (트림 길이 10으로 매턴 발동하던 회귀 방지)
    tracked = patch_deps(['[{"text":"응","emotion":"HAPPY"}]'])
    _, _ = await _collect(
        chat_service.stream_reply(**_base_kwargs(conversation_history=_history(11)))
    )
    assert "memory-extraction" not in tracked


@pytest.mark.asyncio
async def test_llm_error_yields_fallback_and_done(patch_deps, monkeypatch):
    patch_deps([])

    async def _boom(**kwargs):
        raise RuntimeError("stream boom")

    monkeypatch.setattr(chat_service.client.chat.completions, "create", _boom)
    parts, done = await _collect(chat_service.stream_reply(**_base_kwargs()))

    assert done is not None
    assert len(parts) == 1
    assert parts[0].emotion == "SURPRISED"


# P0-3: 스트리밍 경로 A/B 결과 기록 회귀 테스트.
# 논스트림 generate_reply만 _record_ab_result를 호출하고 stream_reply는 누락되어
# 스트리밍으로 전환된 트래픽의 A/B 데이터가 전혀 쌓이지 않던 결함 검증.
@pytest.mark.asyncio
async def test_streaming_records_ab_result_when_character_id_set(patch_deps, monkeypatch):
    patch_deps(['[{"text":"안녕","emotion":"HAPPY"}]'])

    # create_tracked_task를 가로채되, 이번 테스트는 코루틴을 즉시 닫지 않고
    # record-ab-result 태스크만 직접 await 해 내부 record_result 호출을 검증한다.
    tracked: list[tuple[str, object]] = []

    def _capture_tracked(coro, name=""):
        tracked.append((name, coro))
        return None

    monkeypatch.setattr(chat_service, "create_tracked_task", _capture_tracked)

    from app.ab_test import ABTestManager

    recorded: list[dict] = []

    def _fake_record_result(self, experiment_id, variant, metric_name, value, user_id="", character_id=""):
        recorded.append(
            dict(
                experiment_id=experiment_id,
                variant=variant,
                metric_name=metric_name,
                value=value,
                user_id=user_id,
                character_id=character_id,
            )
        )

    monkeypatch.setattr(ABTestManager, "record_result", _fake_record_result)

    parts, done = await _collect(
        chat_service.stream_reply(**_base_kwargs(character_id="test-char-ab"))
    )
    assert done is not None

    ab_task = next((c for n, c in tracked if n == "record-ab-result"), None)
    assert ab_task is not None, "character_id가 있으면 record-ab-result 태스크가 스케줄되어야 함"
    await ab_task

    # 2026-08-03 P0-S2: 라우팅 계측 메트릭 2종(complexity_complex/used_complex_model)이
    # 추가되어 기존 2종 → 4종으로 늘었다.
    assert len(recorded) == 4
    for rec in recorded:
        # mutation 방어: user_id/character_id가 빈 문자열이 아닌 실제 값이어야 함
        assert rec["user_id"] == "test-char-ab"
        assert rec["character_id"] == "test-char-ab"
        assert rec["experiment_id"] == "model_routing"
    assert {r["metric_name"] for r in recorded} == {
        "total_tokens",
        "response_time_ms",
        "complexity_complex",
        "used_complex_model",
    }
    # "안녕"(simple) 턴이므로 분류기 판정은 complex가 아니어야 한다.
    by_metric = {r["metric_name"]: r["value"] for r in recorded}
    assert by_metric["complexity_complex"] == 0.0

    for name, coro in tracked:
        if name != "record-ab-result":
            coro.close()


@pytest.mark.asyncio
async def test_streaming_skips_ab_result_without_character_id(patch_deps):
    """character_id 미지정(웹 MVP 등)이면 A/B 기록을 스케줄하지 않는다."""
    tracked = patch_deps(['[{"text":"안녕","emotion":"HAPPY"}]'])
    _, done = await _collect(chat_service.stream_reply(**_base_kwargs(character_id="")))

    assert done is not None
    assert "record-ab-result" not in tracked


# P7: 스트림 경로도 api_usage를 기록해야 한다(이전에는 전혀 기록하지 않아
# _gate_user의 일일 예산/한도 계산이 SSE 트래픽을 누락하던 결함).
@pytest.mark.asyncio
async def test_streaming_records_api_usage_when_usage_chunk_present(patch_deps, monkeypatch):
    usage = types.SimpleNamespace(prompt_tokens=120, completion_tokens=40, total_tokens=160)
    patch_deps(['[{"text":"안녕","emotion":"HAPPY"}]'], usage=usage)

    # create_tracked_task를 다시 가로채(패턴: test_streaming_records_ab_result_...와 동일)
    # 이번엔 코루틴을 즉시 닫지 않고 record-usage 태스크만 직접 await 한다.
    tracked: list[tuple[str, object]] = []

    def _capture_tracked(coro, name=""):
        tracked.append((name, coro))
        return None

    monkeypatch.setattr(chat_service, "create_tracked_task", _capture_tracked)

    recorded: list[dict] = []

    async def _fake_record_usage(
        room_id, character_id, model_id, prompt_tokens, completion_tokens,
        endpoint="chat", cached_tokens=0,
    ):
        recorded.append(dict(
            room_id=room_id,
            character_id=character_id,
            model_id=model_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            endpoint=endpoint,
            cached_tokens=cached_tokens,
        ))

    monkeypatch.setattr(chat_service, "_record_usage", _fake_record_usage)

    parts, done = await _collect(
        chat_service.stream_reply(**_base_kwargs(room_id="room-usage", character_id="char-usage"))
    )
    assert done is not None
    assert parts

    usage_task = next((c for n, c in tracked if n == "record-usage"), None)
    assert usage_task is not None, "usage 청크가 있으면 record-usage 태스크가 스케줄되어야 함"
    await usage_task

    assert len(recorded) == 1
    rec = recorded[0]
    assert rec["room_id"] == "room-usage"
    assert rec["character_id"] == "char-usage"
    assert rec["prompt_tokens"] == 120
    assert rec["completion_tokens"] == 40
    # 스트림 경로는 반드시 endpoint="stream"으로 구분 기록해야 한다
    # (generate_reply의 기본값 "chat"과 혼동되면 안 됨).
    assert rec["endpoint"] == "stream"
    # 2026-08-03 P2(회의 항목2): usage에 prompt_tokens_details가 없으면(구버전
    # SDK/이 테스트의 usage처럼) cached_tokens는 안전하게 0으로 기록된다.
    assert rec["cached_tokens"] == 0

    for name, coro in tracked:
        if name != "record-usage":
            coro.close()


# 2026-08-03 P2(회의 항목2): usage.prompt_tokens_details.cached_tokens가 있으면
# _record_usage에 cached_tokens로 그대로 전달돼야 한다(prefix cache 히트율 계측).
@pytest.mark.asyncio
async def test_streaming_records_cached_tokens_when_present(patch_deps, monkeypatch):
    usage = types.SimpleNamespace(
        prompt_tokens=500,
        completion_tokens=40,
        total_tokens=540,
        prompt_tokens_details=types.SimpleNamespace(cached_tokens=384),
    )
    patch_deps(['[{"text":"안녕","emotion":"HAPPY"}]'], usage=usage)

    tracked: list[tuple[str, object]] = []

    def _capture_tracked(coro, name=""):
        tracked.append((name, coro))
        return None

    monkeypatch.setattr(chat_service, "create_tracked_task", _capture_tracked)

    recorded: list[dict] = []

    async def _fake_record_usage(
        room_id, character_id, model_id, prompt_tokens, completion_tokens,
        endpoint="chat", cached_tokens=0,
    ):
        recorded.append(dict(cached_tokens=cached_tokens))

    monkeypatch.setattr(chat_service, "_record_usage", _fake_record_usage)

    parts, done = await _collect(
        chat_service.stream_reply(**_base_kwargs(room_id="room-cache", character_id="char-cache"))
    )
    assert done is not None
    assert parts

    usage_task = next((c for n, c in tracked if n == "record-usage"), None)
    assert usage_task is not None
    await usage_task

    assert recorded == [{"cached_tokens": 384}]

    for name, coro in tracked:
        if name != "record-usage":
            coro.close()


@pytest.mark.asyncio
async def test_streaming_skips_api_usage_without_usage_chunk(patch_deps):
    """usage 청크가 없는 스트림(예: LoRA 엔드포인트)에서는 record-usage를 스케줄하지 않는다."""
    tracked = patch_deps(['[{"text":"안녕","emotion":"HAPPY"}]'])  # usage=None(기본값)

    _, done = await _collect(
        chat_service.stream_reply(**_base_kwargs(character_id="char-no-usage"))
    )

    assert done is not None
    assert "record-usage" not in tracked
