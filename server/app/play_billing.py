"""Google Play 결제/구독 서버측 검증.

설계 원칙(보안 회의 2026-06-01 P0-2):
- 영수증(purchase_token)은 반드시 서버에서 Google Play Developer API로 검증한다.
- 검증 라이브러리/서비스 계정이 미구성이면:
    * production → 프리미엄 부여 거부 (mock 우회 차단)
    * development → BILLING_ALLOW_MOCK=true일 때만 mock 허용(경고 로그)
- RTDN(Pub/Sub push) 메시지는 OIDC 토큰을 검증한다.

google-api-python-client / google-auth 미설치 환경에서도 import 가능하도록
의존성은 함수 내부에서 지연 로딩한다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from .config import (
    BILLING_ALLOW_MOCK,
    ENVIRONMENT,
    GOOGLE_PLAY_PACKAGE_NAME,
    GOOGLE_PLAY_SERVICE_ACCOUNT_JSON,
    PLAY_RTDN_AUDIENCE,
)

logger = logging.getLogger(__name__)

_IS_PROD = ENVIRONMENT == "production"


@dataclass
class VerificationResult:
    ok: bool
    reason: str = ""
    # 검증이 mock(미구성 폴백)으로 통과한 경우 True
    mock: bool = False


def _play_configured() -> bool:
    return bool(GOOGLE_PLAY_PACKAGE_NAME and GOOGLE_PLAY_SERVICE_ACCOUNT_JSON)


def verify_subscription_purchase(product_id: str, purchase_token: str) -> VerificationResult:
    """구독 영수증을 Google Play Developer API로 검증한다.

    Returns:
        VerificationResult(ok=True) — 유효한 구매
        VerificationResult(ok=False, reason=...) — 무효 / 검증 불가
    """
    if not purchase_token:
        return VerificationResult(False, "purchase_token이 없습니다")

    if not _play_configured():
        # 검증 인프라 미구성
        if _IS_PROD:
            logger.error(
                "[billing] Google Play 검증 미구성(GOOGLE_PLAY_*) — production에서 프리미엄 부여 거부"
            )
            return VerificationResult(False, "결제 검증이 구성되지 않았습니다")
        if BILLING_ALLOW_MOCK:
            logger.warning(
                "[billing] 개발 환경 mock 검증 통과 (product=%s). 운영 전 Google Play 검증 연동 필요.",
                product_id,
            )
            return VerificationResult(True, "mock(dev)", mock=True)
        return VerificationResult(False, "결제 검증 비활성화(BILLING_ALLOW_MOCK=false)")

    # 실제 Google Play Developer API 검증
    try:
        from google.oauth2 import service_account  # type: ignore
        from googleapiclient.discovery import build  # type: ignore

        creds = service_account.Credentials.from_service_account_file(
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON,
            scopes=["https://www.googleapis.com/auth/androidpublisher"],
        )
        service = build("androidpublisher", "v3", credentials=creds, cache_discovery=False)
        result = (
            service.purchases()
            .subscriptions()
            .get(
                packageName=GOOGLE_PLAY_PACKAGE_NAME,
                subscriptionId=product_id,
                token=purchase_token,
            )
            .execute()
        )
        # paymentState: 0=대기, 1=수신, 2=무료체험, 3=보류된 업그레이드/다운그레이드
        payment_state = result.get("paymentState")
        if payment_state in (1, 2):
            return VerificationResult(True, "verified")
        return VerificationResult(False, f"paymentState={payment_state}")
    except ImportError:
        if _IS_PROD:
            logger.error("[billing] google-api-python-client 미설치 — production 검증 불가")
            return VerificationResult(False, "검증 라이브러리 미설치")
        if BILLING_ALLOW_MOCK:
            logger.warning("[billing] 검증 라이브러리 미설치 — 개발 mock 통과")
            return VerificationResult(True, "mock(no-lib)", mock=True)
        return VerificationResult(False, "검증 라이브러리 미설치")
    except Exception as exc:  # noqa: BLE001
        logger.warning("[billing] Google Play 검증 실패: %s", exc)
        return VerificationResult(False, f"검증 실패: {exc}")


def verify_rtdn_token(authorization: Optional[str]) -> VerificationResult:
    """RTDN Pub/Sub push 요청의 OIDC Bearer 토큰을 검증한다."""
    if not PLAY_RTDN_AUDIENCE:
        if _IS_PROD:
            logger.error("[billing] PLAY_RTDN_AUDIENCE 미설정 — production RTDN webhook 거부")
            return VerificationResult(False, "RTDN 검증 미구성")
        if BILLING_ALLOW_MOCK:
            logger.warning("[billing] RTDN 토큰 검증 미구성 — 개발 mock 통과")
            return VerificationResult(True, "mock(dev)", mock=True)
        return VerificationResult(False, "RTDN 검증 비활성화")

    if not authorization:
        return VerificationResult(False, "Authorization 헤더 없음")

    token = authorization[7:] if authorization.startswith("Bearer ") else authorization
    try:
        from google.auth.transport import requests as g_requests  # type: ignore
        from google.oauth2 import id_token  # type: ignore

        id_token.verify_oauth2_token(
            token, g_requests.Request(), audience=PLAY_RTDN_AUDIENCE
        )
        return VerificationResult(True, "verified")
    except ImportError:
        if _IS_PROD:
            return VerificationResult(False, "google-auth 미설치")
        return VerificationResult(BILLING_ALLOW_MOCK, "mock(no-lib)", mock=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[billing] RTDN 토큰 검증 실패: %s", exc)
        return VerificationResult(False, f"토큰 검증 실패: {exc}")
