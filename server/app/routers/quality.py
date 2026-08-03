"""품질 관련 엔드포인트"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..auth_middleware import require_auth_always, verify_firebase_token
from ..metrics_service import get_session_stats
from ..models import FeedbackRequest, QualityDashboardResponse
from ..postgres import execute as pg_execute
from ..postgres_async import get_async_db
from ..quality_service import get_diversity_report, get_quality_dashboard

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api/v1", tags=["quality"])


@router.post("/feedback/submit")
@limiter.limit("30/minute")
async def submit_feedback(
    request: Request,
    req: FeedbackRequest,
    user: dict = Depends(require_auth_always),
):
    """사용자 피드백 제출 (thumbs_up / thumbs_down).

    P0-4: user_id는 인증 토큰에서 채운다(클라 위조 방지 — events.py 라우터와 동일 패턴).
    """
    uid = user.get("uid", "")
    try:
        pg_execute(
            """
            INSERT INTO response_feedback
                (room_id, character_id, message_id, feedback_type, feedback_detail, user_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                req.room_id,
                req.character_id,
                req.message_id,
                req.feedback_type,
                req.feedback_detail,
                uid,
            ),
        )
    except Exception as e:
        logger.error(f"피드백 저장 실패: {e}")
        raise HTTPException(status_code=500, detail="피드백 저장에 실패했습니다.")

    return {"status": "ok"}


@router.get("/quality/dashboard", response_model=QualityDashboardResponse)
async def quality_dashboard(
    character_id: str = "",
    days: int = 30,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """품질 대시보드 조회"""
    data = get_quality_dashboard(character_id, days)
    return QualityDashboardResponse(**data)


@router.get("/quality/diversity/{character_id}")
async def diversity_report(
    character_id: str,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """다양성 리포트 조회"""
    return get_diversity_report(character_id)


@router.get("/quality/diversity-weekly/{character_id}")
async def weekly_diversity_report(
    character_id: str,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """주간 다양성 리포트 — W2-2 자동 평가 파이프라인.

    최근 50개 응답의 bigram diversity score를 산출하고,
    임계값(0.55) 이하 시 metric_events에 경고를 기록한다.
    DATA-C 권도현 + DATA-A 오재원 설계.
    """
    from ..diversity_monitor import get_diversity_monitor
    return await get_diversity_monitor().weekly_report(character_id)


class SessionFeedbackRequest(BaseModel):
    session_id: str
    room_id: str
    rating: int  # 1-5
    text: Optional[str] = None


@router.post("/session-feedback")
@limiter.limit("30/minute")
async def submit_session_feedback(
    request: Request,
    req: SessionFeedbackRequest,
    user: dict = Depends(require_auth_always),
):
    """QS 충족 세션 종료 시 인앱 별점 + 피드백 수집.

    P0-4: user_id는 인증 토큰에서 채운다(클라 위조 방지 — events.py 라우터와 동일 패턴).
    """
    if not (1 <= req.rating <= 5):
        raise HTTPException(status_code=400, detail="rating must be 1-5")
    uid = user.get("uid", "")
    db = get_async_db()
    await db.execute(
        """
        INSERT INTO session_feedback (session_id, room_id, rating, text, user_id)
        VALUES ($1, $2, $3, $4, $5)
        """,
        req.session_id,
        req.room_id,
        req.rating,
        req.text,
        uid,
    )
    return {"status": "ok"}


@router.get("/session-feedback/summary/{room_id}")
async def get_feedback_summary(room_id: str):
    """room_id 기준 피드백 집계"""
    db = get_async_db()
    row = await db.fetchone(
        """
        SELECT COUNT(*) as count, ROUND(AVG(rating), 2) as avg_rating
        FROM session_feedback WHERE room_id = $1
        """,
        room_id,
    )
    return {"count": row["count"] if row else 0, "avg_rating": row["avg_rating"] if row else None}


@router.get("/metrics/session-stats")
async def session_stats(
    days: int = 7,
    group_by: str = "room",
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """세션 통계 조회 — 30분 gap 휴리스틱으로 metric_events(chat_turn/app_open)에서
    세션을 파생(P3, 2026-08-03 회의). 신규 계측 없이 조회 계층에서만 집계한다.

    group_by: "room"(room_id 기준) 또는 "user"(user_id 기준).
    """
    if group_by not in ("room", "user"):
        raise HTTPException(status_code=400, detail="group_by must be 'room' or 'user'")
    return get_session_stats(days=days, group_by=group_by)


@router.get("/finetune/audit")
async def finetune_audit(
    character_id: str = "",
    limit: int = 500,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """파인튜닝 데이터 품질 감사 — DB에 저장된 AI 응답 기반.

    FT-C 전영석 + FT-A 노재민 설계 (W1-5).
    MBTI 분포, 다양성, 자기강화 루프 여부를 자동 산출한다.
    """
    from ..finetune_audit import run_audit_from_db
    report = run_audit_from_db(character_id=character_id, limit=min(limit, 2000))
    return {
        "total_samples": report.total_samples,
        "mbti_distribution": report.mbti_distribution,
        "mbti_imbalance_score": round(report.mbti_imbalance_score, 4),
        "synthetic_ratio": round(report.synthetic_ratio, 4),
        "diversity_score": round(report.diversity_score, 4),
        "avg_internal_diversity": round(report.avg_internal_diversity, 4),
        "cross_novelty": round(report.cross_novelty, 4),
        "repetition_rate": round(report.repetition_rate, 4),
        "self_reinforcement_detected": report.self_reinforcement_detected,
        "top_repeated": report.top_repeated,
        "warnings": report.warnings,
    }
