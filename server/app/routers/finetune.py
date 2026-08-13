"""Fine-tuning 엔드포인트"""

from typing import Optional

from fastapi import APIRouter, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..auth_middleware import verify_firebase_token
from ..finetune_service import (
    prepare_and_start_finetune,
    check_finetune_status,
    activate_model,
)
from ..models import (
    FinetuneRequest,
    FinetuneResponse,
    FinetuneStatusResponse,
    FinetuneActivateRequest,
)

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api/v1", tags=["finetune"])


@router.post("/finetune/start", response_model=FinetuneResponse)
@limiter.limit("5/minute")
async def start_finetune(
    request: Request,
    req: FinetuneRequest,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """대화 데이터 수집 → OpenAI Fine-tuning 잡 시작"""
    owner_uid = (user or {}).get("uid", "") if user else ""
    result = await prepare_and_start_finetune(
        character_id=req.character_id,
        owner_uid=owner_uid,
        character_name=req.character_name,
        mbti=req.mbti,
        speech_style=req.speech_style,
        relationship=req.relationship,
        nickname=req.nickname,
        affinity_level=req.affinity_level,
        conversations=req.conversations,
    )
    return FinetuneResponse(**result)


@router.get("/finetune/status/{job_id}", response_model=FinetuneStatusResponse)
async def get_finetune_status(
    job_id: str,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """Fine-tuning 잡 진행 상태 조회"""
    owner_uid = (user or {}).get("uid", "") if user else ""
    result = await check_finetune_status(job_id, owner_uid)
    return FinetuneStatusResponse(**result)


@router.post("/finetune/activate")
async def activate_finetune(
    req: FinetuneActivateRequest,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """완료된 파인튜닝 모델을 캐릭터에 활성화"""
    owner_uid = (user or {}).get("uid", "") if user else ""
    activate_model(req.character_id, req.model_id, owner_uid)
    return {"status": "ok", "character_id": req.character_id, "model_id": req.model_id}
