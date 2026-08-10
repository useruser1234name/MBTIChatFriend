"""H2(2026-08-04 점검): 삭제된 기억이 계속 주입되는 결함 회귀 테스트.

배경:
- `postgres_async.delete_conversation`(routers/data.py 삭제 엔드포인트가 호출)은
  DB 행만 지우고 memory_service의 인메모리 캐시를 무효화하지 않았다.
- `_load_from_db`는 positive 캐시 히트 시 조기 반환하므로, 프로세스가 살아 있는
  동안 **삭제된 요약·팩트가 계속 프롬프트에 들어갔다**.
- positive 캐시에는 만료가 없어(FIFO eviction만 존재) 멀티 워커에서는 다른
  워커가 삭제/갱신한 내용을 무기한 못 봤다.

수정:
① memory_service.invalidate_memory_cache() 공개 함수
② 대화 삭제 경로(routers/data.py + postgres_async.delete_conversation)에서 호출
③ positive 캐시 TTL(_POSITIVE_TTL_SECONDS) 도입 — 만료 시 무효화가 아니라 재검증
"""

import time
import types

import pytest

from app import memory_service
from app.routers import data as data_router


@pytest.fixture(autouse=True)
def _clean_memory_caches():
    def _clear():
        memory_service._conversation_summaries.clear()
        memory_service._character_memories.clear()
        memory_service._negative_until.clear()
        memory_service._positive_loaded_at.clear()

    _clear()
    yield
    _clear()


@pytest.fixture
def db_calls(monkeypatch):
    """postgres 활성화 + fetchone 호출 카운터. rows[key]로 응답을 제어한다."""
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


async def _ctx(room_id: str) -> str:
    return await memory_service.build_memory_context("캐릭터", "유저", room_id=room_id)


# ── 1. invalidate_memory_cache ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invalidate_forces_db_requery_and_drops_deleted_memory(db_calls):
    room_id = "uid-h2:ENFP"
    key = _key(room_id)
    db_calls.rows[key] = {
        "summary": "삭제될 요약",
        "facts": [{"key": "이름", "value": "철수"}],
    }

    assert "삭제될 요약" in await _ctx(room_id)
    assert len(db_calls.fetchone_params) == 1

    # 삭제: DB 행 제거 + 캐시 무효화
    db_calls.rows.pop(key)
    removed = memory_service.invalidate_memory_cache(room_id=room_id, character_id="ENFP")
    assert removed >= 1
    assert key not in memory_service._conversation_summaries
    assert key not in memory_service._character_memories
    assert key not in memory_service._positive_loaded_at

    # 다음 조회는 DB를 다시 읽고(카운트 증가), 삭제된 요약/팩트를 주입하지 않는다.
    assert await _ctx(room_id) == ""
    assert len(db_calls.fetchone_params) == 2


@pytest.mark.asyncio
async def test_invalidate_also_clears_negative_marking(db_calls):
    """네거티브 마킹까지 지워야 삭제 직후 재생성된 기억이 즉시 보인다."""
    room_id = "uid-h2b:ENFP"
    key = _key(room_id)

    await _ctx(room_id)  # 행 없음 → 네거티브 마킹
    assert key in memory_service._negative_until

    memory_service.invalidate_memory_cache(room_id=room_id)
    assert key not in memory_service._negative_until


@pytest.mark.asyncio
async def test_invalidate_sweeps_keys_matching_delete_like_fragment(db_calls):
    """DB 삭제가 memory_key LIKE '%fragment%' 이므로 캐시도 같은 범위를 비운다."""
    room_id = "uid-h2c:ENFP"
    legacy_key = f"legacy::{room_id}::v1"  # 같은 fragment를 포함하는 다른 표기
    memory_service._conversation_summaries[legacy_key] = "레거시 요약"
    memory_service._touch_positive(legacy_key)

    memory_service.invalidate_memory_cache(room_id=room_id)
    assert legacy_key not in memory_service._conversation_summaries


@pytest.mark.asyncio
async def test_invalidate_does_not_touch_other_rooms(db_calls):
    """mutation 방어: 무관한 방의 캐시까지 날리면 안 된다."""
    keep_room = "uid-other:ENFP"
    db_calls.rows[_key(keep_room)] = {"summary": "남아야 할 요약", "facts": []}
    assert "남아야 할 요약" in await _ctx(keep_room)

    memory_service.invalidate_memory_cache(room_id="uid-h2d:ENFP")

    before = len(db_calls.fetchone_params)
    assert "남아야 할 요약" in await _ctx(keep_room)
    assert len(db_calls.fetchone_params) == before, "다른 방은 캐시 히트를 유지해야 함"


# ── 2. 삭제 엔드포인트 배선 ───────────────────────────────────────────────


class _FakeAsyncDB:
    def __init__(self):
        self.calls = []

    async def delete_conversation(self, room_id: str, character_id: str = "") -> int:
        self.calls.append((room_id, character_id))
        return 3


@pytest.mark.asyncio
async def test_delete_endpoint_invalidates_memory_cache(db_calls, monkeypatch):
    room_id = "uid-del:ENFP"
    key = _key(room_id)
    db_calls.rows[key] = {"summary": "삭제될 요약", "facts": []}
    assert "삭제될 요약" in await _ctx(room_id)

    fake_db = _FakeAsyncDB()
    monkeypatch.setattr(data_router, "get_async_db", lambda: fake_db)

    result = await data_router.delete_conversation(
        room_id=room_id, character_id="ENFP", user={"uid": "uid-del"}
    )

    assert result["status"] == "deleted"
    assert fake_db.calls == [(room_id, "ENFP")]
    # DB 삭제와 캐시 무효화는 반드시 짝을 이룬다
    assert key not in memory_service._conversation_summaries

    db_calls.rows.pop(key)
    assert await _ctx(room_id) == ""


@pytest.mark.asyncio
async def test_delete_endpoint_still_rejects_other_users_room(db_calls, monkeypatch):
    """mutation 방어: 소유권 검사는 그대로 살아 있어야 한다(캐시도 안 지워짐)."""
    from fastapi import HTTPException

    victim_room = "uid-victim:ENFP"
    db_calls.rows[_key(victim_room)] = {"summary": "피해자 요약", "facts": []}
    await _ctx(victim_room)

    monkeypatch.setattr(data_router, "get_async_db", lambda: _FakeAsyncDB())

    with pytest.raises(HTTPException) as exc:
        await data_router.delete_conversation(
            room_id=victim_room, character_id="", user={"uid": "uid-attacker"}
        )
    assert exc.value.status_code == 403
    assert _key(victim_room) in memory_service._conversation_summaries


# ── 3. positive 캐시 TTL 재검증 ───────────────────────────────────────────


def test_positive_ttl_is_five_minutes():
    assert memory_service._POSITIVE_TTL_SECONDS == 300.0


@pytest.mark.asyncio
async def test_positive_cache_hits_within_ttl(db_calls):
    room_id = "room-ttl-hit"
    db_calls.rows[_key(room_id)] = {"summary": "요약", "facts": []}

    for _ in range(5):
        assert "요약" in await _ctx(room_id)
    assert len(db_calls.fetchone_params) == 1, "TTL 안에서는 DB를 다시 읽지 않는다"


@pytest.mark.asyncio
async def test_positive_cache_revalidates_after_ttl(db_calls):
    room_id = "room-ttl-exp"
    key = _key(room_id)
    db_calls.rows[key] = {"summary": "오래된 요약", "facts": []}
    assert "오래된 요약" in await _ctx(room_id)
    assert len(db_calls.fetchone_params) == 1

    # TTL 경과 시뮬레이션 + 그 사이 다른 워커가 대화를 삭제
    memory_service._positive_loaded_at[key] = (
        time.monotonic() - memory_service._POSITIVE_TTL_SECONDS - 1.0
    )
    db_calls.rows.pop(key)

    assert await _ctx(room_id) == "", "만료 후 재검증에서 삭제가 반영돼야 함"
    assert len(db_calls.fetchone_params) == 2
    assert key not in memory_service._conversation_summaries
    # 행이 없으므로 네거티브 마킹으로 전환
    assert key in memory_service._negative_until


@pytest.mark.asyncio
async def test_ttl_revalidation_picks_up_other_workers_update(db_calls):
    room_id = "room-ttl-upd"
    key = _key(room_id)
    db_calls.rows[key] = {"summary": "구버전 요약", "facts": []}
    await _ctx(room_id)

    memory_service._positive_loaded_at[key] = (
        time.monotonic() - memory_service._POSITIVE_TTL_SECONDS - 1.0
    )
    db_calls.rows[key] = {"summary": "다른 워커가 갱신한 요약", "facts": []}

    ctx = await _ctx(room_id)
    assert "다른 워커가 갱신한 요약" in ctx
    assert "구버전 요약" not in ctx


@pytest.mark.asyncio
async def test_save_to_db_resets_ttl_clock(db_calls):
    """방금 이 워커가 쓴 값은 최신 — 저장 직후 재검증이 일어나면 안 된다."""
    room_id = "room-ttl-save"
    key = _key(room_id)
    await _ctx(room_id)  # 미스 → 네거티브
    memory_service._conversation_summaries[key] = "방금 쓴 요약"
    await memory_service._save_to_db(key)

    before = len(db_calls.fetchone_params)
    assert "방금 쓴 요약" in await _ctx(room_id)
    assert len(db_calls.fetchone_params) == before


# ── 4. t_memory_cache_hit(S4 계측) 의미 보존 ──────────────────────────────


@pytest.mark.asyncio
async def test_is_memory_cached_false_after_ttl_expiry(db_calls):
    """만료된 항목은 다음 턴에 DB를 치므로 cache_hit이 아니어야 한다."""
    room_id = "room-ttl-metric"
    key = _key(room_id)
    db_calls.rows[key] = {"summary": "요약", "facts": []}
    await _ctx(room_id)
    assert memory_service.is_memory_cached("캐릭터", "유저", room_id=room_id) is True

    memory_service._positive_loaded_at[key] = (
        time.monotonic() - memory_service._POSITIVE_TTL_SECONDS - 1.0
    )
    assert memory_service.is_memory_cached("캐릭터", "유저", room_id=room_id) is False


@pytest.mark.asyncio
async def test_is_memory_cached_false_after_invalidate(db_calls):
    room_id = "room-inv-metric"
    db_calls.rows[_key(room_id)] = {"summary": "요약", "facts": []}
    await _ctx(room_id)
    assert memory_service.is_memory_cached("캐릭터", "유저", room_id=room_id) is True

    memory_service.invalidate_memory_cache(room_id=room_id)
    assert memory_service.is_memory_cached("캐릭터", "유저", room_id=room_id) is False
