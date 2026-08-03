"""P1-S4: 기억 컨텍스트 네거티브 캐시 + 재조회 제거 회귀 테스트.

배경(2026-08-03 회의 P1-S4):
- `_load_from_db`가 캐시 히트일 때만 조기 반환하고, DB에 행이 없으면(= 첫 요약
  이전의 모든 신규 방) 아무것도 캐싱하지 않아 **매 턴** DB를 다시 조회했다.
- `build_memory_context`가 summary/facts를 각각 로드해 턴당 fetchone 2회.
- chat_service의 `if not mem_ctx:` 폴백이, 기억이 없어 빈 문자열이 정당한
  결과인 신규 방에서 build_memory_context를 TTFT 직렬 경로에서 한 번 더 호출.

아래 테스트가 세 가지 재발을 모두 막는다.
"""

import time
import types

import pytest

from app import chat_service, memory_service
from app.models import HistoryMessage


@pytest.fixture(autouse=True)
def _clean_memory_caches():
    """테스트 간 캐시 격리 (모듈 전역 캐시)."""
    memory_service._conversation_summaries.clear()
    memory_service._character_memories.clear()
    memory_service._negative_until.clear()
    yield
    memory_service._conversation_summaries.clear()
    memory_service._character_memories.clear()
    memory_service._negative_until.clear()


@pytest.fixture
def db_calls(monkeypatch):
    """postgres 활성화 + fetchone 호출 카운터. rows[key] 로 응답을 제어한다."""
    state = types.SimpleNamespace(fetchone_params=[], rows={}, executed=[])

    def _fake_fetchone(sql, params=None):
        state.fetchone_params.append(params)
        key = params[0] if params else None
        return state.rows.get(key)

    def _fake_execute(sql, params=None):
        state.executed.append(params)
        return 1

    monkeypatch.setattr(memory_service, "postgres_enabled", lambda: True)
    monkeypatch.setattr(memory_service, "fetchone", _fake_fetchone)
    monkeypatch.setattr(memory_service, "execute", _fake_execute)
    return state


def _key(room_id: str) -> str:
    return memory_service.get_memory_key("캐릭터", "유저", room_id=room_id)


# ── 1. 미스 → 네거티브 캐시 → 재조회 없음 ──────────────────────────────────


@pytest.mark.asyncio
async def test_miss_records_negative_cache_and_skips_further_db_reads(db_calls):
    room_id = "room-neg-1"
    key = _key(room_id)

    ctx1 = await memory_service.build_memory_context("캐릭터", "유저", room_id=room_id)
    assert ctx1 == ""
    # 신규 방(행 없음): 1턴에 fetchone 1회 — summary/facts 각각 조회하던 2회가 아니다.
    assert len(db_calls.fetchone_params) == 1
    assert key in memory_service._negative_until

    # TTL 안에서는 몇 번을 불러도 DB를 다시 치지 않는다.
    for _ in range(5):
        assert await memory_service.build_memory_context("캐릭터", "유저", room_id=room_id) == ""
    assert len(db_calls.fetchone_params) == 1


@pytest.mark.asyncio
async def test_negative_cache_ttl_is_60_seconds(db_calls):
    room_id = "room-neg-ttl"
    before = time.monotonic()
    await memory_service.build_memory_context("캐릭터", "유저", room_id=room_id)
    deadline = memory_service._negative_until[_key(room_id)]
    # 영구 캐시가 아니라 짧은 TTL(다중 워커 stale 방지)
    assert 59.0 <= deadline - before <= 61.0
    assert memory_service._NEGATIVE_TTL_SECONDS == 60.0


@pytest.mark.asyncio
async def test_negative_cache_expiry_triggers_requery(db_calls):
    room_id = "room-neg-2"
    key = _key(room_id)

    await memory_service.build_memory_context("캐릭터", "유저", room_id=room_id)
    assert len(db_calls.fetchone_params) == 1

    # TTL 만료 시뮬레이션: 마감 시각을 과거로 되돌린다.
    memory_service._negative_until[key] = time.monotonic() - 1.0

    # 만료 후에는 다시 조회하고, 그 사이 다른 워커가 저장한 값을 본다.
    db_calls.rows[key] = {"summary": "새 요약", "facts": [{"key": "직업", "value": "학생"}]}
    ctx = await memory_service.build_memory_context("캐릭터", "유저", room_id=room_id)
    assert len(db_calls.fetchone_params) == 2
    assert "새 요약" in ctx
    assert "직업" in ctx
    # 만료 항목은 정리되고 positive 캐시로 승격
    assert key not in memory_service._negative_until
    assert key in memory_service._conversation_summaries


@pytest.mark.asyncio
async def test_cache_hit_after_row_found_needs_no_db(db_calls):
    room_id = "room-neg-3"
    db_calls.rows[_key(room_id)] = {"summary": "기존 요약", "facts": []}

    assert "기존 요약" in await memory_service.build_memory_context("캐릭터", "유저", room_id=room_id)
    assert len(db_calls.fetchone_params) == 1
    await memory_service.build_memory_context("캐릭터", "유저", room_id=room_id)
    assert len(db_calls.fetchone_params) == 1


# ── 2. 저장 시 네거티브 마킹 해제 ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_save_clears_negative_marking_so_new_value_is_visible(db_calls):
    room_id = "room-neg-save"
    key = _key(room_id)

    # 신규 방: 미스 → 네거티브 마킹
    await memory_service.build_memory_context("캐릭터", "유저", room_id=room_id)
    assert key in memory_service._negative_until

    # 요약 저장 경로(summarize_conversation/extract_facts가 하는 일과 동일)
    memory_service._conversation_summaries[key] = "방금 저장한 요약"
    await memory_service._save_to_db(key)
    assert key not in memory_service._negative_until, "저장 시 네거티브 마킹이 즉시 해제되어야 함"

    # positive 캐시가 evict된 뒤에도(=다른 워커/재기동 상황) 네거티브 마킹이
    # 남아 새 값을 가리지 않는다.
    memory_service._conversation_summaries.pop(key, None)
    db_calls.rows[key] = {"summary": "방금 저장한 요약", "facts": []}
    ctx = await memory_service.build_memory_context("캐릭터", "유저", room_id=room_id)
    assert "방금 저장한 요약" in ctx


@pytest.mark.asyncio
async def test_negative_cache_is_bounded(db_calls):
    for i in range(memory_service._MAX_NEGATIVE + 50):
        await memory_service.build_memory_context("캐릭터", "유저", room_id=f"room-bound-{i}")
    assert len(memory_service._negative_until) <= memory_service._MAX_NEGATIVE


# ── 3. is_memory_cached (계측용) ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_is_memory_cached_reflects_negative_and_positive_cache(db_calls):
    room_id = "room-cachehit"
    assert memory_service.is_memory_cached("캐릭터", "유저", room_id=room_id) is False
    await memory_service.build_memory_context("캐릭터", "유저", room_id=room_id)
    # 네거티브 캐시도 "DB 왕복 없이 처리됨"이므로 hit
    assert memory_service.is_memory_cached("캐릭터", "유저", room_id=room_id) is True


def test_is_memory_cached_true_when_postgres_disabled(monkeypatch):
    monkeypatch.setattr(memory_service, "postgres_enabled", lambda: False)
    assert memory_service.is_memory_cached("캐릭터", "유저", room_id="room-nopg") is True


# ── 4. chat_service: 정당한 빈 결과는 재조회하지 않는다 ────────────────────


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


class _FakeClient:
    def __init__(self, tokens):
        async def _create(**kwargs):
            return _FakeStream(tokens)

        self.chat = types.SimpleNamespace(
            completions=types.SimpleNamespace(create=_create)
        )


def _patch_chat_deps(monkeypatch, mem_ctx_fn):
    async def _fake_affinity(*a, **k):
        return 3

    async def _fake_resolve(model_id, ab_variant):
        return model_id, ""

    monkeypatch.setattr(
        chat_service, "client", _FakeClient(['[{"text":"안녕","emotion":"HAPPY"}]'])
    )
    monkeypatch.setattr(chat_service, "analyze_affinity_with_llm", _fake_affinity)
    monkeypatch.setattr(chat_service, "build_memory_context", mem_ctx_fn)
    monkeypatch.setattr(chat_service, "resolve_model_endpoint", _fake_resolve)
    monkeypatch.setattr(chat_service, "get_store", lambda: None)
    monkeypatch.setattr(chat_service, "create_tracked_task", lambda coro, name="": coro.close())
    monkeypatch.setattr(chat_service, "quick_score", lambda *a, **k: 0.9)
    monkeypatch.setattr(chat_service, "check_content", lambda text: (True, ""))


def _stream_kwargs():
    return dict(
        message="안녕",
        mbti="ENFP",
        speech_style="반말",
        relationship="친구",
        nickname="유저",
        affinity_level=3,
        conversation_history=[HistoryMessage(role="user", content="이전 메시지")],
        character_name="캐릭터",
        character_id="",
        room_id="room-recall",
    )


async def _drain(gen):
    async for _ in gen:
        pass


@pytest.mark.asyncio
async def test_stream_reply_does_not_recall_memory_when_empty_is_legit(monkeypatch):
    calls = []

    async def _empty_mem(*a, **k):
        calls.append(1)
        return ""

    _patch_chat_deps(monkeypatch, _empty_mem)
    await _drain(chat_service.stream_reply(**_stream_kwargs()))
    assert len(calls) == 1, "기억 없는 방에서 build_memory_context를 두 번 부르면 안 됨"


@pytest.mark.asyncio
async def test_generate_reply_does_not_recall_memory_when_empty_is_legit(monkeypatch):
    calls = []

    async def _empty_mem(*a, **k):
        calls.append(1)
        return ""

    _patch_chat_deps(monkeypatch, _empty_mem)

    async def _fake_create(**kwargs):
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(
                message=types.SimpleNamespace(content='[{"text":"안녕","emotion":"HAPPY"}]')
            )],
            usage=types.SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )

    monkeypatch.setattr(chat_service.client.chat.completions, "create", _fake_create)

    replies, _ = await chat_service.generate_reply(**_stream_kwargs())
    assert replies
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_stream_reply_still_retries_memory_on_failure(monkeypatch):
    """실패(예외) 시의 방어적 폴백은 보존되어야 한다."""
    calls = []

    async def _flaky_mem(*a, **k):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("memory down")
        return "## 이전 대화에서 기억하는 것 (내 시점)\n복구된 기억"

    _patch_chat_deps(monkeypatch, _flaky_mem)
    await _drain(chat_service.stream_reply(**_stream_kwargs()))
    assert len(calls) == 2, "병렬 조회가 예외로 실패하면 폴백 재조회가 남아 있어야 함"


# ── 5. turn_latency payload에 t_memory_cache_hit ───────────────────────────


@pytest.mark.asyncio
async def test_turn_latency_payload_has_memory_cache_hit(monkeypatch):
    recorded = []

    async def _fake_record_event_async(event_type, room_id="", character_id="", user_id="", payload=None):
        recorded.append((event_type, payload or {}))

    monkeypatch.setattr(chat_service, "record_event_async", _fake_record_event_async)

    await chat_service._record_turn_latency_event(
        room_id="r", character_id="c", model_id="gpt-4.1-mini", streaming=True,
        t_memory_ms=1.0, t_rag_ms=2.0, t_first_token_ms=3.0,
        complexity="simple", crisis_tier=0, memory_cache_hit=True,
    )

    assert recorded
    event_type, payload = recorded[0]
    assert event_type == "turn_latency"
    assert payload["t_memory_cache_hit"] is True
    # 기존 필드 불변
    for key in ("model_id", "streaming", "t_memory_ms", "t_rag_ms",
                "t_first_token_ms", "complexity", "crisis_tier"):
        assert key in payload
