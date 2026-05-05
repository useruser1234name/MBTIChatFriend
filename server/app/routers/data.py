"""데이터 관리 라우터: delete_conversation, session_start"""

import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth_middleware import require_auth_always
from ..chat_service import calculate_affinity_decay, calculate_return_bonus
from ..metrics_service import record_event
from ..models import (
    DeleteConversationRequest,
    DeleteConversationResponse,
    SessionStartRequest,
    SessionStartResponse,
)
from ..postgres import _async_pool_ready, get_conn
from ..scopes import build_legacy_cleanup_warnings, build_memory_key, build_room_id
from ..vector_store import get_store
from ..shared import limiter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/session/start", response_model=SessionStartResponse)
@limiter.limit("30/minute")
async def session_start(
    request: Request,
    req: SessionStartRequest,
    user: dict = Depends(require_auth_always),
):
    """세션 시작 시 호감도 감쇠 계산 및 복귀 보너스 적용"""
    from datetime import timezone as tz

    last_chat_time = None
    days_inactive = 0

    if req.last_chat_iso:
        try:
            last_chat_time = datetime.fromisoformat(req.last_chat_iso)
            if last_chat_time.tzinfo is None:
                last_chat_time = last_chat_time.replace(tzinfo=tz.utc)
            days_inactive = (datetime.now(tz.utc) - last_chat_time).days
        except ValueError:
            pass

    adjusted_score = calculate_affinity_decay(
        current_score=req.current_affinity_score,
        current_level=req.current_affinity_level,
        last_chat_time=last_chat_time,
    )

    return_bonus = 0
    if adjusted_score < req.current_affinity_score and days_inactive > 7:
        return_bonus = calculate_return_bonus(req.current_affinity_score, adjusted_score)
        adjusted_score = min(adjusted_score + return_bonus, req.current_affinity_score)

    await asyncio.to_thread(
        record_event,
        event_type="session_start",
        character_id=req.character_id,
        user_id=user["uid"],
        payload={
            "original_score": req.current_affinity_score,
            "adjusted_score": adjusted_score,
            "return_bonus": return_bonus,
            "days_inactive": days_inactive,
        },
    )

    return SessionStartResponse(
        adjusted_score=adjusted_score,
        return_bonus=return_bonus,
        original_score=req.current_affinity_score,
        days_inactive=days_inactive,
    )


@router.post("/data/delete-conversation", response_model=DeleteConversationResponse)
@limiter.limit("5/minute")
async def delete_conversation(
    request: Request,
    req: DeleteConversationRequest,
    user: dict = Depends(require_auth_always),
):
    """대화 기록 삭제 (사용자 데이터 삭제 요청, 본인 데이터만 삭제 가능)"""
    if not req.room_id and not req.character_id:
        raise HTTPException(status_code=400, detail="room_id 또는 character_id가 필요합니다.")

    uid = user["uid"]
    try:
        scoped_room_id = build_room_id(
            user=user,
            room_id=req.room_id,
            character_id=req.character_id,
            character_name=req.character_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    if req.room_id:
        segments = req.room_id.split(":", maxsplit=1)
        if len(segments) < 2 or segments[0] != uid:
            raise HTTPException(status_code=403, detail="본인의 대화 기록만 삭제할 수 있습니다.")

    memory_keys = list(dict.fromkeys(filter(None, [
        build_memory_key(
            user=user,
            room_id=scoped_room_id,
            character_id=req.character_id,
            character_name=req.character_name,
            nickname=req.nickname,
        ),
        build_memory_key(
            user=user,
            character_id=req.character_id,
            character_name=req.character_name,
            nickname=req.nickname,
        ),
        build_memory_key(
            user=user,
            character_name=req.character_name,
            nickname=req.nickname,
        ),
    ])))
    cleanup_warnings = build_legacy_cleanup_warnings(
        character_id=req.character_id,
        character_name=req.character_name,
        nickname=req.nickname,
    )

    async def _do_delete_async() -> list[str]:
        """asyncpg 트랜잭션으로 사용자 스코프 데이터 삭제."""
        from ..postgres import _pool
        tables: list[str] = []

        async with _pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM story_state WHERE room_id = $1", scoped_room_id)
                tables.append("story_state")
                await conn.execute("DELETE FROM diary_entries WHERE room_id = $1", scoped_room_id)
                tables.append("diary_entries")
                await conn.execute("DELETE FROM metric_events WHERE room_id = $1", scoped_room_id)
                tables.append("metric_events")
                await conn.execute("DELETE FROM response_feedback WHERE room_id = $1", scoped_room_id)
                tables.append("response_feedback")
                for memory_key in memory_keys:
                    await conn.execute("DELETE FROM conversation_memory WHERE memory_key = $1", memory_key)
                if memory_keys:
                    tables.append("conversation_memory")

        return tables

    def _do_delete_sync() -> list[str]:
        """psycopg 수동 트랜잭션으로 사용자 스코프 데이터 삭제."""
        tables: list[str] = []

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM story_state WHERE room_id = %s", (scoped_room_id,))
                tables.append("story_state")
                cur.execute("DELETE FROM diary_entries WHERE room_id = %s", (scoped_room_id,))
                tables.append("diary_entries")
                cur.execute("DELETE FROM metric_events WHERE room_id = %s", (scoped_room_id,))
                tables.append("metric_events")
                cur.execute("DELETE FROM response_feedback WHERE room_id = %s", (scoped_room_id,))
                tables.append("response_feedback")
                for memory_key in memory_keys:
                    cur.execute("DELETE FROM conversation_memory WHERE memory_key = %s", (memory_key,))
                if memory_keys:
                    tables.append("conversation_memory")

        return tables

    try:
        if _async_pool_ready():
            deleted_tables = await _do_delete_async()
        else:
            deleted_tables = await asyncio.to_thread(_do_delete_sync)

        await asyncio.to_thread(
            record_event,
            event_type="data_deletion",
            room_id=scoped_room_id,
            character_id=req.character_id or "",
            user_id=uid,
            payload={
                "deletion_type": "conversation",
                "tables": deleted_tables,
                "cleanup_warnings": cleanup_warnings,
            },
        )

        # 벡터 스토어(ChromaDB) 데이터도 함께 삭제
        store = get_store()
        if store and scoped_room_id:
            store.delete_character(scoped_room_id)
            deleted_tables.append("vector_store")

        logger.info(
            "Conversation data deleted: room_id=%s, character_id=%s, tables=%s, cleanup_warnings=%s",
            scoped_room_id,
            req.character_id,
            deleted_tables,
            cleanup_warnings,
        )
    except Exception as e:
        logger.error(f"대화 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail="데이터 삭제에 실패했습니다.")

    return DeleteConversationResponse(
        deleted_count=len(deleted_tables),
        status="ok",
        deleted_targets=deleted_tables,
        cleanup_warnings=cleanup_warnings,
    )
