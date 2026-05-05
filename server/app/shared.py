"""공유 의존성: limiter, 공통 헬퍼 함수"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from .chat_service import (
    generate_reply,
    generate_night_diary,
    calculate_affinity_decay,
    calculate_return_bonus,
)
from .diary_store import has_night_diary, night_bucket_date, save_night_diary
from .metrics_service import record_event
from .models import ChatRequest, MemoryItem, ReplyPart
from .scopes import build_room_id
from .story_state_store import (
    apply_diary_outcome,
    build_story_memory_items,
    bump_turn_and_get_state,
    get_story_state,
    mark_callback_used,
    maybe_build_callback_hint,
)

logger = logging.getLogger(__name__)


def _rate_limit_key(request: Request) -> str:
    """인증된 사용자는 uid 기반, 미인증은 IP 기반 rate limit.

    request.state.user가 설정된 경우 우선 사용하고, 없으면
    Authorization 헤더에서 토큰을 파싱하여 uid를 추출한다.
    토큰 파싱 실패 시 IP 기반으로 폴백한다.
    """
    # 미들웨어가 이미 request.state.user를 설정한 경우 우선 사용
    user = getattr(request.state, "user", None)
    if user and user.get("uid"):
        return f"uid:{user['uid']}"

    # Authorization 헤더에서 직접 uid 추출 (Firebase JWT payload 파싱)
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            import base64
            import json as _json

            token = auth_header[7:]
            parts = token.split(".")
            if len(parts) == 3:
                # JWT payload 디코딩 (서명 검증 없이 uid만 추출 — rate limit 목적)
                padded = parts[1] + "=" * (-len(parts[1]) % 4)
                payload = _json.loads(base64.urlsafe_b64decode(padded))
                uid = payload.get("user_id") or payload.get("sub")
                if uid:
                    return f"uid:{uid}"
        except Exception:
            pass

    return get_remote_address(request)


limiter = Limiter(key_func=_rate_limit_key)


def _handle_crisis_response(
    is_crisis: bool,
    tier: int,
    intervention: str,
    replies: list,
) -> None:
    """Tier 2 위기 감지 시 상담 안내 메시지를 replies 목록 뒤에 추가.
    Tier 1은 이 함수를 호출하지 않고 호출 측에서 즉시 반환한다.
    """
    if is_crisis and tier == 2:
        replies.append(ReplyPart(text=intervention, emotion="WORRIED", delay=1000))


def _resolve_room_id(req: ChatRequest, user: Optional[dict]) -> str:
    try:
        return build_room_id(
            user=user,
            room_id=req.room_id,
            character_id=req.character_id,
            character_name=req.character_name,
            mbti=req.mbti,
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def _is_night_window(client_local_hour: Optional[int]) -> bool:
    if client_local_hour is None:
        return False
    return (22 <= client_local_hour <= 23) or (0 <= client_local_hour <= 4)


def _merge_memories(base: list[MemoryItem], extra: list[MemoryItem]) -> list[MemoryItem]:
    merged: list[MemoryItem] = []
    seen_keys: set[str] = set()

    for item in (base or []) + (extra or []):
        key = item.key.strip()
        value = item.value.strip()
        if not key or not value:
            continue
        if key in seen_keys:
            continue
        seen_keys.add(key)
        merged.append(MemoryItem(key=key, value=value))

    return merged


async def _run_chat_pipeline(req: ChatRequest, user: Optional[dict]) -> dict:
    room_id = _resolve_room_id(req, user)
    character_id = req.character_id or ""
    uid = (user or {}).get("uid", "")

    state = await asyncio.to_thread(bump_turn_and_get_state, room_id, character_id)
    effective_character_id = character_id or state.character_id
    callback_key, callback_hint = maybe_build_callback_hint(state)
    story_memories = build_story_memory_items(state, callback_hint or "")
    merged_memories = _merge_memories(req.memories or [], story_memories)

    replies, affinity_delta = await generate_reply(
        message=req.message,
        mbti=req.mbti,
        speech_style=req.speech_style,
        relationship=req.relationship,
        nickname=req.nickname,
        affinity_level=req.affinity_level,
        conversation_history=req.conversation_history,
        user_mbti=req.user_mbti,
        character_name=req.character_name,
        character_id=effective_character_id,
        persona_raw=req.persona_raw,
        persona_summary=req.persona_summary,
        dialogue_prompt=req.dialogue_prompt,
        visual_prompt=req.visual_prompt,
        memories=merged_memories,
        mood=req.mood,
        room_id=room_id,
        owner_uid=uid,
    )

    if callback_key:
        await asyncio.to_thread(mark_callback_used, room_id, callback_key, state.turn_count)

    night_diary_generated = False
    next_hook = state.next_hook
    next_goal = state.next_goal

    if req.end_of_session and _is_night_window(req.client_local_hour):
        diary_date = night_bucket_date(req.client_local_hour)
        if not await asyncio.to_thread(has_night_diary, room_id, effective_character_id, diary_date):
            diary_text, diary_emotion, diary_next_hook, diary_next_goal = await generate_night_diary(
                character_name=req.character_name,
                mbti=req.mbti,
                speech_style=req.speech_style,
                nickname=req.nickname,
                affinity_level=req.affinity_level,
                conversation_history=req.conversation_history,
            )
            saved = await asyncio.to_thread(
                lambda: save_night_diary(
                    room_id=room_id,
                    character_id=effective_character_id,
                    diary_date=diary_date,
                    diary_text=diary_text,
                    emotion=diary_emotion,
                    next_hook=diary_next_hook,
                    next_goal=diary_next_goal,
                )
            )
            if saved:
                night_diary_generated = True
                await asyncio.to_thread(apply_diary_outcome, room_id, effective_character_id, diary_next_hook, diary_next_goal)
                next_hook = diary_next_hook
                next_goal = diary_next_goal
                await asyncio.to_thread(lambda: record_event(
                    event_type="night_diary_generated",
                    room_id=room_id,
                    character_id=effective_character_id,
                    user_id=uid,
                    payload={
                        "diary_date": diary_date.isoformat(),
                        "emotion": diary_emotion,
                        "next_hook": diary_next_hook,
                        "next_goal": diary_next_goal,
                    },
                ))

    if not next_hook or not next_goal:
        latest = await asyncio.to_thread(get_story_state, room_id, effective_character_id)
        next_hook = next_hook or latest.next_hook
        next_goal = next_goal or latest.next_goal

    await asyncio.to_thread(lambda: record_event(
        event_type="chat_turn",
        room_id=room_id,
        character_id=effective_character_id,
        user_id=uid,
        payload={
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "turn_count": state.turn_count,
            "affinity_delta": affinity_delta,
            "callback_used": bool(callback_key),
            "end_of_session": req.end_of_session,
            "night_diary_generated": night_diary_generated,
            "client_local_hour": req.client_local_hour,
        },
    ))

    return {
        "room_id": room_id,
        "replies": replies,
        "affinity_delta": affinity_delta,
        "night_diary_generated": night_diary_generated,
        "next_hook": next_hook or "",
        "next_goal": next_goal or "",
    }
