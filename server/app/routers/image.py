"""이미지 생성 엔드포인트"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..auth_middleware import verify_firebase_token
from ..config import OPENAI_API_KEY
from ..image_service import (
    generate_and_upload_base,
    start_expression_set_task,
    get_task_status,
)
from ..models import (
    ImageGenerateRequest,
    ImageGenerateResponse,
    ImageSetRequest,
    ImageSetResponse,
    ImageSetStatusResponse,
)

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api/v1", tags=["image"])


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
        raise HTTPException(status_code=500, detail=str(e))


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

    try:
        task_id = start_expression_set_task(
            base_prompt=req.base_prompt,
            character_id=req.character_id,
            size=req.size,
        )
        return ImageSetResponse(status="processing", task_id=task_id)
    except Exception as e:
        logger.error(f"Expression set generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
