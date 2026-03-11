import base64
import json as _json
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from ..subscription import SubscriptionManager, Plan
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
async def rtdn_webhook(body: RTDNMessage):
    """
    Google Play 구독 이벤트 실시간 처리.

    지원 이벤트:
    - SUBSCRIPTION_RENEWED (2): 갱신 → plan 유지
    - SUBSCRIPTION_CANCELED (3): 취소 → expires_at 업데이트
    - SUBSCRIPTION_EXPIRED (13): 만료 → plan = 'free'
    - SUBSCRIPTION_PURCHASED (4): 신규 구매
    """
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
async def verify_purchase(req: PurchaseVerifyRequest):
    """
    Google Play 영수증 검증 후 user_subscriptions 업데이트.
    실제 환경: Google Play Developer API 호출.
    현재: Mock 검증 (purchase_token 비어있지 않으면 성공).
    """
    if not req.purchase_token:
        raise HTTPException(status_code=400, detail="purchase_token이 없습니다")

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
    return {"success": True, "plan": "premium", "user_id": req.user_id}
