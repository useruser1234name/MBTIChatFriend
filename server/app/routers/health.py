"""Health & circuit-breaker 엔드포인트"""

from fastapi import APIRouter, Depends

from ..auth_middleware import require_auth_always
from ..circuit_breaker import get_db_circuit, get_openai_circuit

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.get("/health/circuit-status")
async def circuit_status(user: dict = Depends(require_auth_always)):
    """Circuit Breaker 상태 모니터링 엔드포인트 — 인증 필요.

    DB 및 OpenAI circuit breaker 상태를 반환한다.
    3차 스프린트 P0: 운영 안정성 확보 (CTO-C 이서연).
    S-5: 내부 상태 노출 방지를 위해 require_auth_always 추가.
    """
    db_status = get_db_circuit().get_status()
    openai_status = get_openai_circuit().get_status()
    overall = (
        "ok"
        if db_status["state"] == "CLOSED" and openai_status["state"] == "CLOSED"
        else "degraded"
    )
    return {
        "overall": overall,
        "circuits": {
            "db": db_status,
            "openai": openai_status,
        },
    }
