"""이미지 라우터: generate, expression_set"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth_middleware import verify_firebase_token
from ..config import ENVIRONMENT, OPENAI_API_KEY
from ..content_filter import check_content
from ..image_service import generate_and_upload_base, get_task_status, start_expression_set_task
from ..models import (
    ImageGenerateRequest,
    ImageGenerateResponse,
    ImageSetRequest,
    ImageSetResponse,
    ImageSetStatusResponse,
)
from ..shared import limiter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/image/generate", response_model=ImageGenerateResponse)
@limiter.limit("10/minute")
async def generate_image(
    request: Request,
    req: ImageGenerateRequest,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """gpt-image-1 이미지 생성 → Firebase Storage 업로드"""
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")

    is_safe, reason = check_content(req.prompt)
    if not is_safe:
        raise HTTPException(status_code=400, detail="부적절한 표현이 포함된 프롬프트입니다.")

    try:
        import uuid
        character_id = str(uuid.uuid4())
        url, revised = await generate_and_upload_base(
            prompt=req.prompt,
            character_id=character_id,
            size=req.size,
            quality=req.quality,
        )
        return ImageGenerateResponse(url=url, revised_prompt=revised)
    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        detail = str(e) if ENVIRONMENT != "production" else "서버 내부 오류가 발생했습니다"
        raise HTTPException(status_code=500, detail=detail)


@router.post("/image/generate-set", response_model=ImageSetResponse)
@limiter.limit("5/minute")
async def generate_image_set(
    request: Request,
    req: ImageSetRequest,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """표정 세트 15장 백그라운드 생성 시작"""
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")

    is_safe, reason = check_content(req.base_prompt)
    if not is_safe:
        raise HTTPException(status_code=400, detail="부적절한 표현이 포함된 프롬프트입니다.")

    try:
        task_id = start_expression_set_task(
            base_prompt=req.base_prompt,
            character_id=req.character_id,
            size=req.size,
        )
        return ImageSetResponse(status="processing", task_id=task_id)
    except Exception as e:
        logger.error(f"Expression set generation failed: {e}")
        detail = str(e) if ENVIRONMENT != "production" else "서버 내부 오류가 발생했습니다"
        raise HTTPException(status_code=500, detail=detail)


@router.get("/image/set-status/{task_id}", response_model=ImageSetStatusResponse)
async def get_image_set_status(
    task_id: str,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """표정 세트 생성 진행 상황 조회"""
    status = get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")

    return ImageSetStatusResponse(
        status=status["status"],
        completed=status["completed"],
        total=status["total"],
        urls=status["urls"],
    )
