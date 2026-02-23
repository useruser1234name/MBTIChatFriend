"""Firebase 토큰 검증 미들웨어"""

import logging
from typing import Optional

from fastapi import Header

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
    Firebase ID 토큰 검증 (선택적 적용).

    - Authorization 헤더가 없으면 None 반환 (점진적 마이그레이션 지원)
    - Firebase가 설정되지 않았으면 None 반환
    - 토큰이 유효하면 decoded token dict 반환
    """
    if not authorization:
        return None

    if not _firebase_auth_available:
        logger.debug("Firebase Auth not available, skipping token verification")
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
        return None
