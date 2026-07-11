from fastapi import APIRouter, Depends, HTTPException
import asyncio
import secrets
import string
import time
from pydantic import BaseModel, Field
from ..postgres_async import get_async_db
from ..auth_middleware import require_internal_token, get_uid

router = APIRouter(prefix="/api/v1/referral", tags=["referral"])


class RedeemRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=32)


def _generate_code(length: int = 8) -> str:
    chars = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))


async def _get_or_create_referral_code(uid: str, db) -> str:
    """레퍼럴 코드 조회 또는 신규 생성 (내부 헬퍼)."""
    existing = await db.fetchone(
        "SELECT code FROM referral_codes WHERE inviter_id = $1 AND expires_at > now() AND redeemed_by IS NULL LIMIT 1",
        uid,
    )
    if existing:
        return existing["code"]
    code = _generate_code()
    await db.execute(
        "INSERT INTO referral_codes (code, inviter_id) VALUES ($1, $2)",
        code,
        uid,
    )
    return code


@router.post("/link")
async def generate_referral_link(uid: str = Depends(get_uid), db=Depends(get_async_db)):
    """Firebase Dynamic Link 레퍼럴 URL 생성"""
    code = await _get_or_create_referral_code(uid, db)
    dl_url = f"https://mbtichat.page.link/invite?code={code}&utm_source=referral&utm_medium=app"
    cta_text = "친구에게 7일 무료 선물하기"
    return {"referral_link": dl_url, "referral_code": code, "cta_text": cta_text}


@router.post("/generate")
async def generate_referral_code(uid: str = Depends(get_uid), db=Depends(get_async_db)):
    """초대 코드 생성(본인). 기존 유효 코드 있으면 반환."""
    # 기존 코드 확인
    existing = await db.fetchone(
        "SELECT code FROM referral_codes WHERE inviter_id = $1 AND expires_at > now() AND redeemed_by IS NULL LIMIT 1",
        uid,
    )
    if existing:
        return {"code": existing["code"]}
    # 신규 생성
    code = _generate_code()
    await db.execute(
        "INSERT INTO referral_codes (code, inviter_id) VALUES ($1, $2)",
        code,
        uid,
    )
    return {"code": code}


@router.post("/redeem")
async def redeem_referral_code(body: RedeemRequest, uid: str = Depends(get_uid)):
    """초대 코드 사용(인증된 본인). 수신자 trial 3일 + 발신자 trial 7일 연장 및 FCM 알림."""
    from ..firebase_service import send_notification_with_record

    code = body.code
    new_user_id = uid
    db = get_async_db()
    row = await db.fetchone(
        "SELECT inviter_id FROM referral_codes WHERE code = $1 AND expires_at > now() AND redeemed_by IS NULL",
        code,
    )
    if not row:
        raise HTTPException(status_code=404, detail="유효하지 않은 초대 코드입니다.")
    inviter_id = row["inviter_id"]
    if inviter_id == new_user_id:
        raise HTTPException(status_code=400, detail="본인 코드는 사용할 수 없습니다.")
    # 코드 사용 처리
    await db.execute(
        "UPDATE referral_codes SET redeemed_by = $1, redeemed_at = now() WHERE code = $2",
        new_user_id,
        code,
    )
    # 수신자(new_user_id): trial 3일 부여
    await db.execute(
        """
        INSERT INTO user_subscriptions (user_id, plan, trial_expires_at)
        VALUES ($1, 'trial', now() + INTERVAL '3 days')
        ON CONFLICT (user_id) DO UPDATE
          SET trial_expires_at = GREATEST(user_subscriptions.trial_expires_at, now() + INTERVAL '3 days')
        """,
        new_user_id,
    )
    # 발신자(inviter_id): trial +7일 연장
    await db.execute(
        """
        INSERT INTO user_subscriptions (user_id, plan, trial_expires_at)
        VALUES ($1, 'trial', now() + INTERVAL '7 days')
        ON CONFLICT (user_id) DO UPDATE
          SET trial_expires_at = GREATEST(user_subscriptions.trial_expires_at, now() + INTERVAL '7 days')
        """,
        inviter_id,
    )
    # 발신자에게 FCM 알림 발송
    try:
        await send_notification_with_record(
            user_id=inviter_id,
            title="친구가 초대를 수락했어요!",
            body="초대한 친구가 가입했어요. 보상으로 7일이 연장되었습니다.",
            notification_type="referral_accepted",
            data={"code": code},
            deep_link="mbtichat://settings/referral",
        )
    except Exception:
        pass
    return {"status": "ok", "inviter_id": inviter_id}


@router.get("/stats")
async def get_referral_stats_me(uid: str = Depends(get_uid), db=Depends(get_async_db)):
    """내 레퍼럴 현황 조회 (인증 필요). 초대 친구 수 및 보상 일수 반환."""
    invited = await db.fetchval(
        """
        SELECT COUNT(*)
        FROM referral_codes rc
        WHERE rc.inviter_id = $1
          AND rc.redeemed_by IS NOT NULL
        """,
        uid,
    )
    invited = invited or 0
    return {"invited_count": invited, "reward_days": invited * 7}


@router.get("/stats/{user_id}")
async def get_referral_stats(user_id: str, uid: str = Depends(get_uid)):
    """초대 현황 조회(본인만)."""
    if uid != user_id:
        raise HTTPException(status_code=403, detail="본인의 현황만 조회할 수 있습니다.")
    db = get_async_db()
    row = await db.fetchone(
        """
        SELECT
            COUNT(*) FILTER (WHERE redeemed_by IS NOT NULL) AS redeemed_count,
            COUNT(*) AS total_count
        FROM referral_codes WHERE inviter_id = $1
        """,
        user_id,
    )
    return {
        "total_issued": row["total_count"] if row else 0,
        "redeemed": row["redeemed_count"] if row else 0,
    }


@router.get("/pending-notifications")
async def get_pending_referral_notifications(
    db=Depends(get_async_db),
    _: bool = Depends(require_internal_token),
):
    """
    만료 D-2(48시간 이내) 미사용 코드 조회.
    FCM 배치 스케줄러(매일 자정)가 호출 — 내부 토큰 필요.
    반환: 수신자 초대 대상 + 발신자(inviter) 재공유 유도 목록.
    """
    start = time.monotonic()
    try:
        async with asyncio.timeout(300):
            query = """
                SELECT code, inviter_id, expires_at
                FROM referral_codes
                WHERE redeemed_by IS NULL
                  AND expires_at BETWEEN now() AND now() + INTERVAL '48 hours'
            """
            rows = await db.fetch(query)

            notifications = []
            for row in rows:
                notifications.append({
                    "code": row["code"],
                    "inviter_id": row["inviter_id"],
                    "expires_at": row["expires_at"].isoformat() if row["expires_at"] else None,
                    "notification_type": "d2_expiry",
                })

            return {
                "pending_count": len(notifications),
                "notifications": notifications,
                "batch_duration_seconds": round(time.monotonic() - start, 3),
            }
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Batch timeout after 300 seconds")


@router.post("/send-d2-notifications")
async def send_d2_referral_notifications(
    db=Depends(get_async_db),
    _: bool = Depends(require_internal_token),
):
    """
    만료 D-2 미사용 코드 보유자에게 FCM 알림 발송.
    배치 스케줄러(매일 자정)가 호출 — 내부 토큰 필요. deep_link로 레퍼럴 설정 화면 이동.
    """
    from ..firebase_service import send_notification_with_record

    start = time.monotonic()
    query = """
        SELECT code, inviter_id, expires_at
        FROM referral_codes
        WHERE redeemed_by IS NULL
          AND expires_at BETWEEN now() AND now() + INTERVAL '48 hours'
    """
    rows = await db.fetch(query)

    sent_count = 0
    for row in rows:
        try:
            await send_notification_with_record(
                user_id=row["inviter_id"],
                title="초대 코드가 곧 만료돼요",
                body=f"초대 코드 {row['code']}가 48시간 후 만료됩니다. 지금 친구를 초대해보세요!",
                notification_type="d2_expiry",
                data={"code": row["code"]},
                deep_link="mbtichat://settings/referral",
            )
            sent_count += 1
        except Exception:
            pass

    return {
        "sent_count": sent_count,
        "batch_duration_seconds": round(time.monotonic() - start, 3),
    }
