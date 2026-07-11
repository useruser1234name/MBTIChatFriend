"""Firebase 토큰 검증 미들웨어"""

import logging
from typing import Optional

from fastapi import Depends, Header, HTTPException

from .config import ENVIRONMENT, INTERNAL_API_TOKEN, REQUIRE_AUTH

logger = logging.getLogger(__name__)

# Firebase Admin SDK (선택적)
try:
    from firebase_admin import auth

    _firebase_auth_available = True
except ImportError:
    _firebase_auth_available = False


async def require_auth_always(
    authorization: Optional[str] = Header(default=None),
) -> dict:
    """
    관리자/민감 엔드포인트용 — REQUIRE_AUTH 설정과 무관하게 항상 인증 요구.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="인증이 필요합니다.")

    if not _firebase_auth_available:
        raise HTTPException(status_code=503, detail="인증 서비스를 사용할 수 없습니다.")

    try:
        token = authorization[7:] if authorization.startswith("Bearer ") else authorization
        decoded = auth.verify_id_token(token)
        return decoded
    except Exception as e:
        logger.warning(f"Token verification failed (strict): {e}")
        raise HTTPException(status_code=401, detail="유효하지 않은 인증 토큰입니다.")


async def require_internal_token(
    x_internal_token: Optional[str] = Header(default=None),
) -> bool:
    """배치/스케줄러/관리자 전용 엔드포인트 보호.

    INTERNAL_API_TOKEN과 X-Internal-Token 헤더 일치를 요구한다.
    - 토큰 미설정 시: production은 거부(503), development는 허용(경고).
    """
    if not INTERNAL_API_TOKEN:
        if ENVIRONMENT == "production":
            logger.error("[auth] INTERNAL_API_TOKEN 미설정 — production 내부 엔드포인트 거부")
            raise HTTPException(status_code=503, detail="내부 엔드포인트가 구성되지 않았습니다.")
        logger.warning("[auth] INTERNAL_API_TOKEN 미설정 — 개발 환경 통과")
        return True
    if not x_internal_token or x_internal_token != INTERNAL_API_TOKEN:
        raise HTTPException(status_code=403, detail="내부 토큰이 유효하지 않습니다.")
    return True


async def verify_firebase_token(
    authorization: Optional[str] = Header(default=None),
) -> Optional[dict]:
    """
    Firebase ID 토큰 검증.

    - REQUIRE_AUTH=true (production 기본값): 토큰 없으면 401 반환
    - REQUIRE_AUTH=false (development 기본값): 토큰 없으면 None 반환 (점진적 마이그레이션)
    """
    if not authorization:
        if REQUIRE_AUTH:
            raise HTTPException(status_code=401, detail="인증이 필요합니다.")
        return None

    if not _firebase_auth_available:
        logger.debug("Firebase Auth not available, skipping token verification")
        if REQUIRE_AUTH:
            raise HTTPException(status_code=503, detail="인증 서비스를 사용할 수 없습니다.")
        return None

    try:
        # "Bearer <token>" 형식에서 토큰 추출
        if authorization.startswith("Bearer "):
            token = authorization[7:]
        else:
            token = authorization

        decoded = auth.verify_id_token(token)
        logger.debug(f"Token verified for uid: {decoded.get('uid', 'unknown')}")
        return decoded
    except Exception as e:
        logger.warning(f"Token verification failed: {e}")
        if REQUIRE_AUTH:
            raise HTTPException(status_code=401, detail="유효하지 않은 인증 토큰입니다.")
        return None


# ── 소유권 검사 idiom 단일화 (S18) ────────────────────────────────
# 과거 community.py/referral.py/billing.py/subscription.py에 각기 다른
# 형태("토큰 uid == 대상 user_id" 검사)로 산재해 있던 것을 이 두 함수로 통일.
# 각 호출부의 기존 상태코드(403/401)와 detail 문구는 그대로 재현한다
# (billing.py/subscription.py는 community.py와 detail 문구가 달라 detail
# 파라미터로 흡수).


def _assert_owner(
    user: dict,
    user_id: str,
    detail: str = "본인 계정으로만 수행할 수 있습니다.",
) -> None:
    """인증 토큰의 uid가 요청의 user_id와 일치하는지 검증 (IDOR 방지)."""
    token_uid = user.get("uid")
    if not token_uid or token_uid != user_id:
        raise HTTPException(status_code=403, detail=detail)


async def get_uid(user: Optional[dict] = Depends(verify_firebase_token)) -> str:
    """Firebase 인증 토큰에서 uid 추출. 인증 실패 시 401."""
    if not user or not user.get("uid"):
        raise HTTPException(status_code=401, detail="인증이 필요합니다.")
    return user["uid"]
