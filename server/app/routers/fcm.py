"""FCM 푸시 알림 엔드포인트"""

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..auth_middleware import require_auth_always
from ..firebase_service import register_token, get_token, send_push_notification
from ..models import FcmTokenRequest, FcmSendRequest

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api/v1", tags=["fcm"])


@router.post("/fcm/register")
@limiter.limit("10/minute")
async def register_fcm_token(
    request: Request,
    req: FcmTokenRequest,
    user: dict = Depends(require_auth_always),
):
    """FCM 토큰 등록 — 인증된 사용자의 uid에 귀속 (IDOR/토큰 하이재킹 방지).

    require_auth_always를 사용해 REQUIRE_AUTH 설정과 무관하게 항상 인증을 요구한다.
    클라이언트가 보낸 req.user_id는 신뢰하지 않고 토큰 uid만 사용한다.
    """
    user_id = user["uid"]
    register_token(user_id, req.token)
    return {"status": "ok"}


@router.post("/fcm/send")
@limiter.limit("30/minute")
async def send_fcm_notification(
    request: Request,
    req: FcmSendRequest,
    user: dict = Depends(require_auth_always),
):
    """FCM 푸시 알림 발송 — 본인에게만 허용 (IDOR 방지).

    require_auth_always를 사용해 REQUIRE_AUTH 설정과 무관하게 항상 인증을 요구한다.
    타 사용자 대상 발송(스케줄러 등)은 이 HTTP 엔드포인트가 아니라
    firebase_service 내부 호출 경로를 사용한다.
    """
    # 대상은 항상 인증된 본인. 클라이언트가 타인 user_id를 지정하면 거부한다.
    uid = user["uid"]
    if req.user_id and req.user_id != uid:
        raise HTTPException(status_code=403, detail="본인에게만 푸시를 발송할 수 있습니다.")
    target_uid = uid
    token = get_token(target_uid)
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
