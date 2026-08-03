"""generate_reply 특성화(characterization) 테스트 — 논스트림 채팅 생성 경로.

목적: 리팩토링 전 현재 동작을 고정해 회귀를 잡아낸다. 라이브 LLM 없이 가짜
AsyncOpenAI 클라이언트로 검증한다. 목킹 스타일은 test_stream_reply.py의
patch_deps 픽스처(monkeypatch로 chat_service 모듈 속성을 직접 패치)를 따른다.
"""

import types

import pytest

from app import chat_service
from app.models import ReplyPart


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeUsage:
    def __init__(self, prompt_tokens=10, completion_tokens=5, total_tokens=15):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]
        self.usage = _FakeUsage()


class _FakeCompletions:
    """contents: 매 create() 호출마다 순서대로 반환할 content 문자열 목록.

    호출 횟수가 목록 길이를 넘으면 마지막 값을 재사용한다. call_count로
    실제 LLM 호출 횟수(정상 1회 vs 품질 게이트 재생성 2회)를 검증한다.
    """

    def __init__(self, contents):
        self._contents = list(contents)
        self.call_count = 0

    async def create(self, **kwargs):
        idx = min(self.call_count, len(self._contents) - 1)
        content = self._contents[idx]
        self.call_count += 1
        return _FakeResponse(content)


class _FakeClient:
    def __init__(self, contents):
        self.chat = types.SimpleNamespace(completions=_FakeCompletions(contents))


@pytest.fixture
def patch_common(monkeypatch):
    """generate_reply 특성화 테스트 공통 의존성 목킹."""

    async def _fake_affinity(*a, **k):
        return 3

    async def _fake_mem_ctx(*a, **k):
        return ""

    async def _fake_resolve(model_id, ab_variant):
        return model_id, ""  # base_url 빈값 → active_client = client

    def _fake_rag_search_sync(scope_id, message):
        return [], []

    def _fake_tracked(coro, name=""):
        # 백그라운드 태스크 실행 방지: 코루틴을 닫아 경고만 억제
        try:
            coro.close()
        except Exception:
            pass
        return None

    monkeypatch.setattr(chat_service, "analyze_affinity_with_llm", _fake_affinity)
    monkeypatch.setattr(chat_service, "build_memory_context", _fake_mem_ctx)
    monkeypatch.setattr(chat_service, "resolve_model_endpoint", _fake_resolve)
    monkeypatch.setattr(chat_service, "_rag_search_sync", _fake_rag_search_sync)
    monkeypatch.setattr(chat_service, "create_tracked_task", _fake_tracked)
    monkeypatch.setattr(chat_service, "quick_score", lambda *a, **k: 1.0)
    monkeypatch.setattr(chat_service, "check_content", lambda text: (True, ""))


def _base_kwargs(**over):
    kw = dict(
        message="안녕",
        mbti="INFP",
        speech_style="반말",
        relationship="친구",
        nickname="테스트",
        affinity_level=2,
        conversation_history=[],
    )
    kw.update(over)
    return kw


@pytest.mark.asyncio
async def test_generate_reply_happy_path(patch_common, monkeypatch):
    """정상 경로: LLM 1회 호출, JSON 파싱 성공, LLM 호감도 분석값 채택."""
    fake_client = _FakeClient(['[{"text": "안녕!", "emotion": "HAPPY"}]'])
    monkeypatch.setattr(chat_service, "client", fake_client)

    parts, delta = await chat_service.generate_reply(**_base_kwargs())

    assert parts[0].text == "안녕!"
    assert parts[0].emotion == "HAPPY"
    assert delta == 3
    assert fake_client.chat.completions.call_count == 1


@pytest.mark.asyncio
async def test_generate_reply_no_client_fallback(patch_common, monkeypatch):
    """클라이언트 없음(API 키 미설정) → _mock_reply 폴백 경로."""
    monkeypatch.setattr(chat_service, "client", None)

    parts, delta = await chat_service.generate_reply(**_base_kwargs())

    assert len(parts) > 0
    assert all(isinstance(p, ReplyPart) for p in parts)
    assert isinstance(delta, int)


@pytest.mark.asyncio
async def test_generate_reply_blocked_input(patch_common, monkeypatch):
    """입력 차단 경로(check_content=False): 고정 거절 문구 + delta=-2.

    chat_service.py 약 741-747줄 관측 동작을 그대로 고정한다.
    """
    monkeypatch.setattr(chat_service, "check_content", lambda text: (False, "unsafe"))
    # 클라이언트가 있어도 입력 필터가 최우선으로 차단해 LLM을 호출하지 않아야 함
    fake_client = _FakeClient(['[{"text": "안녕!", "emotion": "HAPPY"}]'])
    monkeypatch.setattr(chat_service, "client", fake_client)

    parts, delta = await chat_service.generate_reply(**_base_kwargs())

    assert len(parts) == 1
    assert parts[0].text == "그런 표현은 사용하지 말아줘요... 다른 이야기 해볼까요?"
    assert parts[0].emotion == "SAD"
    assert parts[0].delay == 2000
    assert delta == -2
    assert fake_client.chat.completions.call_count == 0


@pytest.mark.asyncio
async def test_generate_reply_quality_gate_regenerates(patch_common, monkeypatch):
    """품질 게이트: 1차 점수 0.2(<=0.2 형식 강제 재시도) → 2차 점수 0.9(>=1차) → 재생성 채택.

    chat_service.py 약 928-992줄 현재 재생성 동작을 고정한다: quick_score가
    임계값(0.4) 미만이면 재생성하고, 재시도 점수가 원본 이상이면 재시도를 채택한다.
    """
    fake_client = _FakeClient([
        '[{"text": "음...", "emotion": "NEUTRAL"}]',
        '[{"text": "안녕! 반가워", "emotion": "HAPPY"}]',
    ])
    monkeypatch.setattr(chat_service, "client", fake_client)

    scores = [0.2, 0.9]
    calls = {"n": 0}

    def _fake_quick_score(*a, **k):
        idx = min(calls["n"], len(scores) - 1)
        calls["n"] += 1
        return scores[idx]

    monkeypatch.setattr(chat_service, "quick_score", _fake_quick_score)

    parts, delta = await chat_service.generate_reply(**_base_kwargs())

    assert fake_client.chat.completions.call_count == 2
    assert parts[0].text == "안녕! 반가워"
    assert parts[0].emotion == "HAPPY"


# 2026-08-03 P2(회의 항목2): usage.prompt_tokens_details.cached_tokens를 아무도
# 읽지 않아 prefix cache 히트율이 완전 미지였다. _emit_background_metrics가
# _record_usage에 cached_tokens를 안전 추출해 전달하는지 검증한다.
@pytest.mark.asyncio
async def test_generate_reply_forwards_cached_tokens_to_record_usage(patch_common, monkeypatch):
    class _UsageWithCache(_FakeUsage):
        def __init__(self):
            super().__init__()
            self.prompt_tokens_details = types.SimpleNamespace(cached_tokens=256)

    class _ResponseWithCache(_FakeResponse):
        def __init__(self, content):
            self.choices = [_FakeChoice(content)]
            self.usage = _UsageWithCache()

    class _CompletionsWithCache:
        async def create(self, **kwargs):
            return _ResponseWithCache('[{"text": "안녕!", "emotion": "HAPPY"}]')

    fake_client = types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=_CompletionsWithCache())
    )
    monkeypatch.setattr(chat_service, "client", fake_client)

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

    parts, delta = await chat_service.generate_reply(**_base_kwargs())
    assert parts

    usage_task = next((c for n, c in tracked if n == "record-usage"), None)
    assert usage_task is not None
    await usage_task

    for name, coro in tracked:
        if name != "record-usage":
            try:
                coro.close()
            except Exception:
                pass

    assert recorded == [{"cached_tokens": 256}]


@pytest.mark.asyncio
async def test_generate_reply_cached_tokens_defaults_to_zero_without_details(patch_common, monkeypatch):
    """usage에 prompt_tokens_details가 없으면(구버전 응답 등) 0으로 안전 기록."""
    fake_client = _FakeClient(['[{"text": "안녕!", "emotion": "HAPPY"}]'])
    monkeypatch.setattr(chat_service, "client", fake_client)

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

    parts, delta = await chat_service.generate_reply(**_base_kwargs())
    assert parts

    usage_task = next((c for n, c in tracked if n == "record-usage"), None)
    assert usage_task is not None
    await usage_task

    for name, coro in tracked:
        if name != "record-usage":
            try:
                coro.close()
            except Exception:
                pass

    assert recorded == [{"cached_tokens": 0}]
