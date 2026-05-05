"""FCM 푸시 알림 엔드포인트"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from ..auth_middleware import verify_firebase_token
from ..firebase_service import register_token, get_token, send_push_notification
from ..models import FcmTokenRequest, FcmSendRequest

router = APIRouter(prefix="/api/v1", tags=["fcm"])


@router.post("/fcm/register")
async def register_fcm_token(
    req: FcmTokenRequest,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """FCM 토큰 등록"""
    user_id = req.user_id or "anonymous"
    register_token(user_id, req.token)
    return {"status": "ok"}


@router.post("/fcm/send")
async def send_fcm_notification(
    req: FcmSendRequest,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """FCM 푸시 알림 발송"""
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
