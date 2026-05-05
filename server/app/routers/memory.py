"""메모리 라우터: extract, get"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from ..auth_middleware import require_auth_always, verify_firebase_token
from ..chat_service import extract_memories
from ..models import MemoryExtractRequest, MemoryExtractResponse, MemoryListResponse
from ..memory_service import get_existing_summary, get_existing_facts
from ..postgres import fetchone as pg_fetchone, postgres_enabled
from ..scopes import build_room_id
from ..shared import limiter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/memory/extract", response_model=MemoryExtractResponse)
@limiter.limit("10/minute")
async def extract_memory(
    request: Request,
    req: MemoryExtractRequest,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """대화에서 장기 기억 추출"""
    memories = await extract_memories(
        character_name=req.character_name,
        nickname=req.nickname,
        conversation_history=req.conversation_history,
        character_id=req.character_id,
        room_id=build_room_id(
            user=user,
            character_id=req.character_id,
            character_name=req.character_name,
        ),
    )
    return MemoryExtractResponse(memories=memories)


@router.get("/memory/{character_name}/{nickname}", response_model=MemoryListResponse)
@limiter.limit("10/minute")
async def get_memories(
    request: Request,
    character_name: str,
    nickname: str,
    character_id: str = Query(default=""),
    user: dict = Depends(require_auth_always),
):
    """캐릭터의 사용자에 대한 기억 조회 (인증 필요, 본인 데이터만 조회 가능)"""
    scoped_room_id = build_room_id(
        user=user,
        character_id=character_id,
        character_name=character_name,
    )

    summary = await get_existing_summary(
        character_name,
        nickname,
        user=user,
        room_id=scoped_room_id,
        character_id=character_id,
    )
    facts = await get_existing_facts(
        character_name,
        nickname,
        user=user,
        room_id=scoped_room_id,
        character_id=character_id,
    )

    total_conversations = 0
    try:
        if postgres_enabled():
            row = await asyncio.to_thread(
                pg_fetchone,
                "SELECT COUNT(*) as cnt FROM metric_events WHERE event_type = 'chat_turn' AND room_id = %s",
                (scoped_room_id,),
            )
            if row:
                total_conversations = row.get("cnt", 0)
    except Exception as e:
        logger.warning(f"대화 수 조회 실패: {e}")

    return MemoryListResponse(
        summary=summary,
        facts=facts,
        total_conversations=total_conversations,
    )
