"""파인튜닝 라우터: start, status, activate"""

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth_middleware import require_auth_always
from ..finetune_service import activate_model, check_finetune_status, prepare_and_start_finetune
from ..models import (
    FinetuneActivateRequest,
    FinetuneRequest,
    FinetuneResponse,
    FinetuneStatusResponse,
)
from ..shared import limiter

router = APIRouter()


@router.post("/finetune/start", response_model=FinetuneResponse)
@limiter.limit("5/minute")
async def start_finetune(
    request: Request,
    req: FinetuneRequest,
    user: dict = Depends(require_auth_always),
):
    """대화 데이터 수집 → OpenAI Fine-tuning 잡 시작"""
    result = await prepare_and_start_finetune(
        character_id=req.character_id,
        owner_uid=user["uid"],
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
@limiter.limit("5/minute")
async def get_finetune_status(
    request: Request,
    job_id: str,
    user: dict = Depends(require_auth_always),
):
    """Fine-tuning 잡 진행 상태 조회"""
    try:
        result = await check_finetune_status(job_id, user["uid"])
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return FinetuneStatusResponse(**result)


@router.post("/finetune/activate")
@limiter.limit("5/minute")
async def activate_finetune(
    request: Request,
    req: FinetuneActivateRequest,
    user: dict = Depends(require_auth_always),
):
    """완료된 파인튜닝 모델을 캐릭터에 활성화"""
    activate_model(req.character_id, req.model_id, user["uid"])
    return {"status": "ok", "character_id": req.character_id, "model_id": req.model_id}
