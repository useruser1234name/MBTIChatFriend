"""품질/피드백 라우터: dashboard, diversity, feedback"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..auth_middleware import require_auth_always, verify_firebase_token
from ..models import FeedbackRequest, QualityDashboardResponse
from ..postgres import execute as pg_execute
from ..quality_service import get_diversity_report, get_quality_dashboard
from ..scopes import build_room_id
from ..shared import limiter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/feedback/submit")
@limiter.limit("30/minute")
async def submit_feedback(
    request: Request,
    req: FeedbackRequest,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """사용자 피드백 제출 (thumbs_up / thumbs_down)"""
    try:
        scoped_room_id = build_room_id(
            user=user,
            room_id=req.room_id,
            character_id=req.character_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        await asyncio.to_thread(
            pg_execute,
            """
            INSERT INTO response_feedback
                (room_id, character_id, message_id, feedback_type, feedback_detail)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                scoped_room_id,
                req.character_id,
                req.message_id,
                req.feedback_type,
                req.feedback_detail,
            ),
        )
    except Exception as e:
        logger.error(f"피드백 저장 실패: {e}")
        raise HTTPException(status_code=500, detail="피드백 저장에 실패했습니다.")

    return {"status": "ok"}


@router.get("/quality/dashboard", response_model=QualityDashboardResponse)
@limiter.limit("10/minute")
async def quality_dashboard(
    request: Request,
    character_id: str = "",
    days: int = Query(default=30, ge=1, le=365),
    user: dict = Depends(require_auth_always),
):
    """품질 대시보드 조회 (항상 인증 필요)"""
    if not character_id:
        raise HTTPException(status_code=400, detail="character_id가 필요합니다.")

    scoped_room_id = build_room_id(user=user, character_id=character_id)
    data = get_quality_dashboard(character_id, days, room_id=scoped_room_id)
    return QualityDashboardResponse(**data)


@router.get("/quality/diversity/{character_id}")
@limiter.limit("10/minute")
async def diversity_report(
    request: Request,
    character_id: str,
    user: dict = Depends(require_auth_always),
):
    """다양성 리포트 조회"""
    scoped_room_id = build_room_id(user=user, character_id=character_id)
    return get_diversity_report(character_id, room_id=scoped_room_id)
