"""구독 플랜 엔드포인트"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from ..auth_middleware import require_auth_always, verify_firebase_token, _assert_owner
from ..models import SubscriptionStatusResponse, SubscriptionUpgradeRequest
from ..postgres_async import get_async_db
from ..subscription import get_subscription_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["subscription"])


@router.get("/subscription/status", response_model=SubscriptionStatusResponse)
async def get_subscription_status(
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """현재 구독 플랜, 일일 메시지 사용량, 제한값 반환.

    인증된 사용자만 조회 가능. 비인증 요청은 FREE 기본값 반환.
    """
    from ..subscription import PLAN_LIMITS, Plan

    sub_mgr = get_subscription_manager()

    if not user:
        free_limits = PLAN_LIMITS[Plan.FREE]
        return SubscriptionStatusResponse(
            plan="free",
            daily_messages_used=0,
            daily_messages_limit=free_limits["daily_messages"],
            max_characters=free_limits["max_characters"],
            max_memories=free_limits["max_memories"],
            max_affinity_level=free_limits["max_affinity_level"],
            expression_set=free_limits["expression_set"],
            night_diary=free_limits["night_diary"],
            night_diary_weekly_limit=free_limits.get("night_diary_weekly_limit", 0),
        )

    uid = user.get("uid", "")
    plan = sub_mgr.get_plan(uid)
    limits = sub_mgr.get_limits(uid)

    # 오늘 사용한 메시지 수 조회 (api_usage 행 기준)
    db = get_async_db()
    daily_used = 0
    if db.available and uid:
        try:
            row = await db.fetchone(
                """
                SELECT COUNT(*) AS msg_count
                FROM api_usage
                WHERE room_id LIKE $1
                  AND created_at >= CURRENT_DATE
                """,
                f"{uid}:%",
            )
            daily_used = int(row["msg_count"]) if row else 0
        except Exception as e:
            logger.error(f"[Subscription] 메시지 사용량 조회 실패: {e}")

    # expires_at 조회
    expires_at_str: Optional[str] = None
    try:
        from ..postgres import fetchone as pg_fetchone, postgres_enabled
        if postgres_enabled() and uid:
            exp_row = pg_fetchone(
                "SELECT expires_at FROM user_subscriptions WHERE user_id = %s",
                (uid,),
            )
            if exp_row and exp_row.get("expires_at"):
                expires_at_str = exp_row["expires_at"].isoformat()
    except Exception as e:
        logger.error(f"[Subscription] expires_at 조회 실패: {e}")

    return SubscriptionStatusResponse(
        plan=plan.value,
        daily_messages_used=daily_used,
        daily_messages_limit=limits["daily_messages"],
        max_characters=limits["max_characters"],
        max_memories=limits["max_memories"],
        max_affinity_level=limits["max_affinity_level"],
        expression_set=limits["expression_set"],
        night_diary=limits["night_diary"],
        night_diary_weekly_limit=limits.get("night_diary_weekly_limit", 0),
        expires_at=expires_at_str,
    )


@router.post("/subscription/upgrade")
async def upgrade_subscription(
    req: SubscriptionUpgradeRequest,
    user: dict = Depends(require_auth_always),
):
    """구독 플랜 변경 엔드포인트.

    보안(P0-2): 인증 필수 + 토큰 uid 일치 검증.
    프리미엄 등 유료 플랜으로의 업그레이드는 이 엔드포인트로 처리하지 않는다.
    유료 결제는 반드시 /api/v1/billing/verify-purchase(영수증 서버 검증)를 거친다.
    여기서는 본인 계정의 무료 플랜 다운그레이드(해지)만 허용한다.
    """
    from ..postgres import execute as pg_exec_sub, postgres_enabled

    _assert_owner(user, req.user_id, detail="user_id가 인증 토큰과 일치하지 않습니다")

    # 유료 플랜 업그레이드는 결제 검증 경로(billing/verify-purchase)로만 허용
    if str(req.plan).lower() not in ("free", "basic"):
        raise HTTPException(
            status_code=402,
            detail="유료 플랜은 /api/v1/billing/verify-purchase 로 결제 검증 후 활성화됩니다",
        )

    if not postgres_enabled():
        # DB 미연결 환경에서도 mock 응답 반환 (개발 편의)
        return {
            "status": "ok",
            "user_id": req.user_id,
            "plan": req.plan,
            "note": "DB 미연결 — mock 응답 (실제 저장되지 않음)",
        }

    try:
        pg_exec_sub(
            """
            INSERT INTO user_subscriptions (user_id, plan, started_at, expires_at)
            VALUES (%s, %s, NOW(), NULL)
            ON CONFLICT (user_id)
            DO UPDATE SET
                plan = EXCLUDED.plan,
                started_at = NOW(),
                expires_at = NULL
            """,
            (req.user_id, req.plan),
        )
        # P3: 60초 TTL 플랜 캐시가 이전 플랜을 반환하지 않도록 즉시 무효화
        get_subscription_manager().invalidate_plan_cache(req.user_id)
        logger.info(
            f"[Subscription] 플랜 업그레이드 완료: user_id={req.user_id}, plan={req.plan}"
        )
    except Exception as e:
        logger.error(f"[Subscription] 플랜 업그레이드 실패: {e}")
        raise HTTPException(status_code=500, detail="플랜 업그레이드 중 오류가 발생했습니다.")

    return {
        "status": "ok",
        "user_id": req.user_id,
        "plan": req.plan,
        "message": "플랜이 업데이트되었습니다. 다음 스프린트에서 실제 결제 연동 예정.",
    }
