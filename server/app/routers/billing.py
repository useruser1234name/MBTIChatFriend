import base64
import json as _json
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from ..auth_middleware import require_auth_always
from ..play_billing import verify_rtdn_token, verify_subscription_purchase
from ..postgres_async import get_async_db

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])

class PurchaseVerifyRequest(BaseModel):
    user_id: str
    purchase_token: str
    order_id: str
    product_id: str  # "premium_monthly" or "premium_yearly"

class RTDNMessage(BaseModel):
    """Google Play Real-time Developer Notification Pub/Sub 메시지."""
    message: dict  # {"data": base64, "messageId": str, ...}
    subscription: str


@router.post("/rtdn-webhook")
async def rtdn_webhook(
    body: RTDNMessage,
    authorization: Optional[str] = Header(default=None),
):
    """
    Google Play 구독 이벤트 실시간 처리.

    보안(P0-2): Pub/Sub push OIDC 토큰을 검증한다. production에서 PLAY_RTDN_AUDIENCE
    미설정 시 webhook을 거부한다.

    지원 이벤트:
    - SUBSCRIPTION_RENEWED (2): 갱신 → plan 유지
    - SUBSCRIPTION_CANCELED (3): 취소 → expires_at 업데이트
    - SUBSCRIPTION_EXPIRED (13): 만료 → plan = 'free'
    - SUBSCRIPTION_PURCHASED (4): 신규 구매
    """
    verification = verify_rtdn_token(authorization)
    if not verification.ok:
        raise HTTPException(status_code=401, detail=f"RTDN 검증 실패: {verification.reason}")

    try:
        data_b64 = body.message.get("data", "")
        payload = _json.loads(base64.b64decode(data_b64).decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="RTDN 메시지 파싱 실패")

    notification_type = payload.get("subscriptionNotification", {}).get("notificationType")
    purchase_token = payload.get("subscriptionNotification", {}).get("purchaseToken", "")

    db = get_async_db()

    if notification_type in (2, 4):  # RENEWED, PURCHASED
        # 구독 유지 — verified_at 갱신
        await db.execute(
            """
            UPDATE user_subscriptions
            SET plan = 'premium', verified_at = NOW()
            WHERE purchase_token = $1
            """,
            purchase_token,
        )
    elif notification_type == 3:  # CANCELED — 기간 만료까지 유지
        await db.execute(
            """
            UPDATE user_subscriptions
            SET expires_at = NOW() + INTERVAL '30 days'
            WHERE purchase_token = $1
            """,
            purchase_token,
        )
    elif notification_type == 13:  # EXPIRED — 무료로 다운그레이드
        await db.execute(
            """
            UPDATE user_subscriptions
            SET plan = 'free', expires_at = NOW()
            WHERE purchase_token = $1
            """,
            purchase_token,
        )

    return {"status": "ok", "notification_type": notification_type}


@router.post("/verify-purchase")
async def verify_purchase(
    req: PurchaseVerifyRequest,
    user=Depends(require_auth_always),
):
    """
    Google Play 영수증 검증 후 user_subscriptions 업데이트.

    보안(P0-2):
    - 인증 필수(require_auth_always). 토큰 uid와 req.user_id 일치 검증.
    - 영수증은 Google Play Developer API로 서버측 검증(play_billing). 미구성 시
      production에서는 프리미엄 부여를 거부한다.
    """
    token_uid = user.get("uid")
    if not token_uid or token_uid != req.user_id:
        raise HTTPException(status_code=403, detail="user_id가 인증 토큰과 일치하지 않습니다")

    result = verify_subscription_purchase(req.product_id, req.purchase_token)
    if not result.ok:
        raise HTTPException(status_code=402, detail=f"영수증 검증 실패: {result.reason}")

    db = get_async_db()
    # user_subscriptions 업데이트
    await db.execute(
        """
        INSERT INTO user_subscriptions (user_id, plan, purchase_token, order_id, verified_at)
        VALUES ($1, 'premium', $2, $3, NOW())
        ON CONFLICT (user_id) DO UPDATE
        SET plan = 'premium', purchase_token = $2, order_id = $3, verified_at = NOW()
        """,
        req.user_id,
        req.purchase_token,
        req.order_id,
    )
    return {"success": True, "plan": "premium", "user_id": req.user_id, "mock": result.mock}
