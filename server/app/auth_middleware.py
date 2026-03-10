"""Firebase 토큰 검증 미들웨어"""

import logging
from typing import Optional

from fastapi import Header, HTTPException

from .config import REQUIRE_AUTH

logger = logging.getLogger(__name__)

# Firebase Admin SDK (선택적)
try:
    from firebase_admin import auth

    _firebase_auth_available = True
except ImportError:
    _firebase_auth_available = False


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
