"""A/B 테스트 엔드포인트"""

from typing import Optional

from fastapi import APIRouter, Depends

from ..auth_middleware import verify_firebase_token

router = APIRouter(prefix="/api/v1", tags=["ab-test"])


@router.get("/ab-test/{experiment_id}/summary")
async def ab_test_summary(
    experiment_id: str,
    days: int = 7,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """A/B 테스트 실험 결과 요약 조회.

    experiment_id: 실험 식별자 (예: "model_routing")
    days: 집계 기간 (기본 7일)

    Returns:
        experiment_id, period_days, config, variants(metric 통계)
    """
    from ..ab_test import get_ab_manager
    summary = get_ab_manager().get_experiment_summary(experiment_id, days=days)
    return summary
