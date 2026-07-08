"""구독 관리 엔드포인트 (36차 스프린트 — premium IAP 연동)"""

import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from ..auth_middleware import verify_firebase_token
from ..play_billing import verify_subscription_purchase
from ..postgres_async import get_async_db

router = APIRouter(prefix="/api/v1/subscriptions", tags=["subscriptions"])


async def get_uid(user: Optional[dict] = Depends(verify_firebase_token)) -> str:
    """Firebase 인증 토큰에서 uid 추출."""
    if not user or not user.get("uid"):
        raise HTTPException(status_code=401, detail="인증이 필요합니다.")
    return user["uid"]


@router.post("/premium")
async def subscribe_premium(
    purchase_token: str,
    product_id: str = "premium_monthly",
    uid: str = Depends(get_uid),
    conn=Depends(get_async_db),
):
    """프리미엄 구독 처리 (30일).

    보안(P0-2): purchase_token을 Google Play Developer API로 서버측 검증 후에만
    플랜을 부여한다. 미검증/미구성 시 production에서 거부.
    """
    result = verify_subscription_purchase(product_id, purchase_token)
    if not result.ok:
        raise HTTPException(status_code=402, detail=f"영수증 검증 실패: {result.reason}")
    expires = datetime.datetime.utcnow() + datetime.timedelta(days=30)
    await conn.execute("""
        INSERT INTO user_subscriptions(user_id, plan, expires_at, purchase_token)
        VALUES($1,'premium',$2,$3)
        ON CONFLICT(user_id) DO UPDATE SET plan='premium', expires_at=$2, purchase_token=$3
    """, uid, expires, purchase_token)
    return {"status": "premium", "expires_at": expires.isoformat()}


@router.get("/status")
async def get_subscription_status(
    uid: str = Depends(get_uid),
    conn=Depends(get_async_db),
):
    """구독 상태 조회"""
    row = await conn.fetchrow(
        "SELECT plan, expires_at FROM user_subscriptions WHERE user_id=$1", uid
    )
    if not row or (row["expires_at"] and row["expires_at"] < datetime.datetime.utcnow()):
        return {"plan": "free"}
    return {"plan": row["plan"], "expires_at": row["expires_at"]}
