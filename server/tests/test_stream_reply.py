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

    def apply(tokens):
        monkeypatch.setattr(chat_service, "client", _FakeClient(tokens))
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
