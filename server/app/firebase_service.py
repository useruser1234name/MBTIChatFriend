"""Firebase Admin SDK 서비스 - FCM 푸시 알림 및 토큰 관리"""

import logging
from typing import Optional

from .config import FIREBASE_CREDENTIALS_PATH
from .postgres import execute, fetchone, postgres_enabled

logger = logging.getLogger(__name__)

# Firebase Admin SDK (선택적 의존성)
_firebase_initialized = False

try:
    import firebase_admin
    from firebase_admin import credentials, messaging

    _firebase_available = True
except ImportError:
    _firebase_available = False
    logger.warning("firebase-admin not installed, FCM features disabled")

# PostgreSQL 미사용 시 메모리 폴백
_memory_store: dict[str, str] = {}


def _db_load_token(user_id: str) -> Optional[str]:
    """PostgreSQL에서 FCM 토큰 조회"""
    if not postgres_enabled():
        return _memory_store.get(user_id)
    row = fetchone(
        "SELECT token FROM fcm_tokens WHERE user_id = %s",
        (user_id,),
    )
    return row["token"] if row else None


def _db_save_token(user_id: str, token: str) -> None:
    """PostgreSQL에 FCM 토큰 저장 (upsert)"""
    if not postgres_enabled():
        _memory_store[user_id] = token
        return
    execute(
        """
        INSERT INTO fcm_tokens (user_id, token, updated_at)
        VALUES (%s, %s, NOW())
        ON CONFLICT (user_id) DO UPDATE SET
            token = EXCLUDED.token,
            updated_at = NOW()
        """,
        (user_id, token),
    )


def init_firebase() -> bool:
    """Firebase Admin SDK 초기화. 서비스 계정 키가 없으면 skip."""
    global _firebase_initialized

    if not _firebase_available:
        logger.info("Firebase Admin SDK not available, skipping initialization")
        return False

    if _firebase_initialized:
        return True

    if not FIREBASE_CREDENTIALS_PATH:
        logger.info("FIREBASE_CREDENTIALS_PATH not set, Firebase disabled")
        return False

    try:
        cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred)
        _firebase_initialized = True
        logger.info("Firebase Admin SDK initialized successfully")
        return True
    except Exception as e:
        logger.warning(f"Firebase initialization failed: {e}")
        return False


def register_token(user_id: str, token: str) -> None:
    """FCM 토큰을 등록하고 DB에 영속화"""
    _db_save_token(user_id, token)
    logger.info(f"FCM token registered for user: {user_id[:8]}...")


def get_token(user_id: str) -> Optional[str]:
    """사용자의 FCM 토큰 조회"""
    return _db_load_token(user_id)


def send_push_notification(
    token: str,
    title: str,
    body: str,
    data: Optional[dict] = None,
) -> bool:
    """FCM 푸시 알림 발송"""
    if not _firebase_initialized or not _firebase_available:
        logger.warning("Firebase not initialized, cannot send push notification")
        return False

    try:
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
            token=token,
        )
        response = messaging.send(message)
        logger.info(f"Push notification sent: {response}")
        return True
    except Exception as e:
        logger.error(f"Failed to send push notification: {e}")
        return False
