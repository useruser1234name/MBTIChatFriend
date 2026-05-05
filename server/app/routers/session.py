"""Self-Regulation 세션 엔드포인트"""

from typing import Optional

from fastapi import APIRouter, Depends

from ..auth_middleware import verify_firebase_token
from ..models import SessionCheckRequest, SessionCheckResponse
from ..session_guard import check_session_limit, check_consecutive_days

router = APIRouter(prefix="/api/v1", tags=["session"])


@router.post("/session/check", response_model=SessionCheckResponse)
async def session_check(
    req: SessionCheckRequest,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """사용 시간 자기조절 점검 엔드포인트.

    - 오늘 세션 사용 시간 초과 여부 확인 (일반 90분 / 미성년자 60분)
    - 7일 연속 접속 여부 확인 → 현실 관계 유도 메시지 반환
    - FOMO 기반 알림 전면 금지 원칙에 따라 푸시 알림 없이 인앱 표시용 데이터만 제공

    PSY-B 최은혜 + PM-B 손민준 설계 (3차 회의 윤리 기준 합의).
    """
    session_result = check_session_limit(
        room_id=req.room_id,
        user_birth_year=req.user_birth_year,
    )
    consecutive_result = check_consecutive_days(room_id=req.room_id)

    return SessionCheckResponse(
        should_warn=session_result["should_warn"],
        elapsed_minutes=session_result["elapsed_minutes"],
        limit_minutes=session_result["limit_minutes"],
        message=session_result["message"],
        consecutive_days=consecutive_result["consecutive_days"],
        should_show_reality_nudge=consecutive_result["should_show_reality_nudge"],
        nudge_message=consecutive_result["nudge_message"],
    )
