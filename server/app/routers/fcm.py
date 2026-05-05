"""FCM 라우터: register, send"""

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth_middleware import require_auth_always
from ..firebase_service import get_token, register_token, send_push_notification
from ..models import FcmSendRequest, FcmTokenRequest
from ..shared import limiter

router = APIRouter()


@router.post("/fcm/register")
@limiter.limit("10/minute")
async def register_fcm_token(
    request: Request,
    req: FcmTokenRequest,
    user: dict = Depends(require_auth_always),
):
    """FCM 토큰 등록 (인증된 사용자 본인 토큰만 등록 가능)"""
    uid = user["uid"]
    register_token(uid, req.token)
    return {"status": "ok"}


@router.post("/fcm/send")
@limiter.limit("10/minute")
async def send_fcm_notification(
    request: Request,
    req: FcmSendRequest,
    user: dict = Depends(require_auth_always),
):
    """FCM 푸시 알림 발송 (본인 user_id에만 발송 가능)"""
    uid = user["uid"]
    if req.user_id != uid:
        raise HTTPException(status_code=403, detail="다른 사용자에게 푸시 알림을 발송할 수 없습니다.")

    token = get_token(req.user_id)
    if not token:
        raise HTTPException(status_code=404, detail="FCM token not found for user")

    data = {}
    if req.character_name:
        data["character_name"] = req.character_name
    if req.character_id:
        data["character_id"] = str(req.character_id)
    data["message"] = req.body

    success = send_push_notification(
        token=token,
        title=req.title,
        body=req.body,
        data=data,
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to send notification")

    return {"status": "sent"}
