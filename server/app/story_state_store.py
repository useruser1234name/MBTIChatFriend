"""Story state store backed by PostgreSQL."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .models import MemoryItem
from .postgres import fetchone, execute, postgres_enabled


@dataclass
class StoryState:
    room_id: str
    character_id: str = ""
    chapter: str = ""
    current_goal: str = ""
    unresolved_hook: str = ""
    promise: str = ""
    trust_score: int = 0
    last_callback_at_turn: int = 0
    last_callback_key: str = ""
    turn_count: int = 0
    next_hook: str = ""
    next_goal: str = ""


def _empty_state(room_id: str, character_id: str = "") -> StoryState:
    return StoryState(room_id=room_id, character_id=character_id or "")


def _row_to_state(row: Optional[dict], room_id: str, character_id: str = "") -> StoryState:
    if not row:
        return _empty_state(room_id, character_id)
    return StoryState(
        room_id=row.get("room_id", room_id),
        character_id=row.get("character_id", character_id or ""),
        chapter=row.get("chapter", ""),
        current_goal=row.get("current_goal", ""),
        unresolved_hook=row.get("unresolved_hook", ""),
        promise=row.get("promise", ""),
        trust_score=int(row.get("trust_score", 0)),
        last_callback_at_turn=int(row.get("last_callback_at_turn", 0)),
        last_callback_key=row.get("last_callback_key", ""),
        turn_count=int(row.get("turn_count", 0)),
        next_hook=row.get("next_hook", ""),
        next_goal=row.get("next_goal", ""),
    )


def _upsert_returning_sql() -> str:
    return """
    INSERT INTO story_state (room_id, character_id)
    VALUES (%s, %s)
    ON CONFLICT (room_id) DO UPDATE SET
        character_id = CASE
            WHEN story_state.character_id = '' AND EXCLUDED.character_id <> '' THEN EXCLUDED.character_id
            ELSE story_state.character_id
        END,
        updated_at = NOW()
    RETURNING
        room_id, character_id, chapter, current_goal, unresolved_hook, promise,
        trust_score, last_callback_at_turn, last_callback_key, turn_count,
        next_hook, next_goal
    """


def _upsert_turn_returning_sql() -> str:
    return """
    INSERT INTO story_state (room_id, character_id, turn_count)
    VALUES (%s, %s, 1)
    ON CONFLICT (room_id) DO UPDATE SET
        character_id = CASE
            WHEN story_state.character_id = '' AND EXCLUDED.character_id <> '' THEN EXCLUDED.character_id
            ELSE story_state.character_id
        END,
        turn_count = story_state.turn_count + 1,
        updated_at = NOW()
    RETURNING
        room_id, character_id, chapter, current_goal, unresolved_hook, promise,
        trust_score, last_callback_at_turn, last_callback_key, turn_count,
        next_hook, next_goal
    """


def get_story_state(room_id: str, character_id: str = "") -> StoryState:
    if not room_id:
        return _empty_state("", character_id)
    if not postgres_enabled():
        return _empty_state(room_id, character_id)

    row = fetchone(_upsert_returning_sql(), (room_id, character_id or ""))
    return _row_to_state(row, room_id, character_id)


def bump_turn_and_get_state(room_id: str, character_id: str = "") -> StoryState:
    if not room_id:
        return _empty_state("", character_id)
    if not postgres_enabled():
        state = _empty_state(room_id, character_id)
        state.turn_count = 1
        return state

    row = fetchone(_upsert_turn_returning_sql(), (room_id, character_id or ""))
    return _row_to_state(row, room_id, character_id)


# Low-2(2026-08-04 점검): ProactiveChatRequest.hook의 max_length=300 계약과
# 저장 시점에서도 정합시킨다. 안드로이드 클라이언트가 이미 hook을 300자로
# 절단해 전송하지만, 그건 "다음 요청 조립" 시점의 방어일 뿐 — 저장 원천
# (여기)에서도 절단해 둬야 다른 경로/클라이언트가 절단 없이 이 값을 읽어가는
# 경우까지 이중으로 방어된다.
_HOOK_MAX_LEN = 300


def apply_diary_outcome(
    room_id: str,
    character_id: str,
    next_hook: str,
    next_goal: str,
) -> None:
    if not room_id:
        return

    next_hook = (next_hook or "")[:_HOOK_MAX_LEN]
    next_goal = (next_goal or "")[:_HOOK_MAX_LEN]

    state = get_story_state(room_id, character_id)

    execute(
        """
        UPDATE story_state
        SET
            next_hook = %s,
            next_goal = %s,
            unresolved_hook = CASE
                WHEN unresolved_hook = '' THEN %s
                ELSE unresolved_hook
            END,
            current_goal = CASE
                WHEN current_goal = '' THEN %s
                ELSE current_goal
            END,
            updated_at = NOW()
        WHERE room_id = %s
        """,
        (
            next_hook or "",
            next_goal or "",
            next_hook or state.unresolved_hook,
            next_goal or state.current_goal,
            room_id,
        ),
    )


def maybe_build_callback_hint(
    state: StoryState,
    min_turn_gap: int = 6,
) -> tuple[Optional[str], Optional[str]]:
    if state.turn_count <= 0:
        return None, None
    if state.turn_count - state.last_callback_at_turn < min_turn_gap:
        return None, None

    candidates: list[tuple[str, str, str]] = []
    if state.unresolved_hook:
        candidates.append(("unresolved_hook", state.unresolved_hook, "아직 회수되지 않은 떡밥"))
    if state.promise:
        candidates.append(("promise", state.promise, "이전에 한 약속"))
    if state.next_hook:
        candidates.append(("next_hook", state.next_hook, "다음 만남에 이어갈 단서"))

    if not candidates:
        return None, None

    non_repeat = [c for c in candidates if c[0] != state.last_callback_key]
    callback_key, callback_value, label = (non_repeat or candidates)[0]
    callback_text = f"{label}: {callback_value}"
    return callback_key, callback_text


def mark_callback_used(room_id: str, callback_key: str, turn_count: int) -> None:
    if not room_id or not callback_key:
        return
    execute(
        """
        UPDATE story_state
        SET
            last_callback_at_turn = %s,
            last_callback_key = %s,
            updated_at = NOW()
        WHERE room_id = %s
        """,
        (turn_count, callback_key, room_id),
    )


def update_trust_score(room_id: str, delta: int) -> None:
    """trust_score를 delta만큼 증감 (0~100 범위)"""
    if not room_id or not postgres_enabled():
        return
    execute(
        """
        UPDATE story_state
        SET
            trust_score = GREATEST(0, LEAST(100, trust_score + %s)),
            updated_at = NOW()
        WHERE room_id = %s
        """,
        (delta, room_id),
    )


def set_promise(room_id: str, promise: str) -> None:
    """캐릭터가 한 약속을 저장"""
    if not room_id or not postgres_enabled():
        return
    execute(
        """
        UPDATE story_state
        SET
            promise = %s,
            updated_at = NOW()
        WHERE room_id = %s
        """,
        (promise or "", room_id),
    )


def build_story_memory_items(state: StoryState, callback_hint: str = "") -> list[MemoryItem]:
    items: list[MemoryItem] = []

    if state.current_goal:
        items.append(MemoryItem(key="story_current_goal", value=state.current_goal))
    if state.unresolved_hook:
        items.append(MemoryItem(key="story_unresolved_hook", value=state.unresolved_hook))
    if state.promise:
        items.append(MemoryItem(key="story_promise", value=state.promise))
    if state.next_hook:
        items.append(MemoryItem(key="story_next_hook", value=state.next_hook))
    if state.next_goal:
        items.append(MemoryItem(key="story_next_goal", value=state.next_goal))
    if callback_hint:
        items.append(MemoryItem(key="story_callback_hint", value=callback_hint))

    # LLM이 관계 강도를 함께 참고할 수 있도록 숫자 상태도 전달
    items.append(MemoryItem(key="story_trust_score", value=str(state.trust_score)))

    return items
