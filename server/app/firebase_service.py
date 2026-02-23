"""Firebase Admin SDK 서비스 - FCM 푸시 알림 및 토큰 관리"""

import json
import logging
from pathlib import Path
from typing import Optional

from .config import FIREBASE_CREDENTIALS_PATH

logger = logging.getLogger(__name__)

# Firebase Admin SDK (선택적 의존성)
_firebase_initialized = False
_TOKEN_FILE = Path(__file__).parent.parent / "fcm_tokens.json"

try:
    import firebase_admin
    from firebase_admin import credentials, messaging

    _firebase_available = True
except ImportError:
    _firebase_available = False
    logger.warning("firebase-admin not installed, FCM features disabled")


def _load_tokens() -> dict[str, str]:
    """파일에서 FCM 토큰 로드"""
    try:
        if _TOKEN_FILE.exists():
            return json.loads(_TOKEN_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Failed to load FCM tokens: {e}")
    return {}


def _save_tokens(tokens: dict[str, str]) -> None:
    """FCM 토큰을 파일에 저장"""
    try:
        _TOKEN_FILE.write_text(
            json.dumps(tokens, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning(f"Failed to save FCM tokens: {e}")


# 시작 시 파일에서 로드
_token_store: dict[str, str] = _load_tokens()


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
    """FCM 토큰을 등록하고 파일에 영속화"""
    _token_store[user_id] = token
    _save_tokens(_token_store)
    logger.info(f"FCM token registered for user: {user_id[:8]}...")


def get_token(user_id: str) -> Optional[str]:
    """사용자의 FCM 토큰 조회"""
    return _token_store.get(user_id)


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
