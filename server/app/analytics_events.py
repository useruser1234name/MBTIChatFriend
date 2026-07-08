"""분석 이벤트 타입 정의 (PM 로드맵 — 최소 계측 12종).

리텐션/퍼널/수익화 측정을 위한 표준 이벤트 집합. 클라이언트가 임의 문자열을
보내 metric_events를 오염시키지 않도록 허용 목록으로 검증한다.

저장: metric_events 테이블 (event_type, room_id, character_id, user_id, payload).
user_id는 서버가 인증 토큰에서 채워 넣는다(클라이언트 위조 방지).
"""

from __future__ import annotations

# ── 앱 수명주기 ──────────────────────────────────────────────
APP_OPEN = "app_open"
APP_BACKGROUND = "app_background"

# ── 온보딩 퍼널 ──────────────────────────────────────────────
ONBOARDING_STEP = "onboarding_step"
ONBOARDING_COMPLETE = "onboarding_complete"

# ── 핵심 루프 ────────────────────────────────────────────────
CHAT_MESSAGE_SENT = "chat_message_sent"
AFFINITY_LEVEL_UP = "affinity_level_up"
DIARY_OPENED = "diary_opened"

# ── 수익화 퍼널 ──────────────────────────────────────────────
PAYWALL_SHOWN = "paywall_shown"
PREMIUM_SCREEN_OPEN = "premium_screen_open"
PURCHASE_INITIATED = "purchase_initiated"
PURCHASE_COMPLETE = "purchase_complete"

# 커뮤니티/기타 보조 이벤트
COMMUNITY_POST_VIEWED = "community_post_viewed"

# 클라이언트가 전송 가능한 이벤트 허용 목록
ALLOWED_CLIENT_EVENTS: frozenset[str] = frozenset(
    {
        APP_OPEN,
        APP_BACKGROUND,
        ONBOARDING_STEP,
        ONBOARDING_COMPLETE,
        CHAT_MESSAGE_SENT,
        AFFINITY_LEVEL_UP,
        DIARY_OPENED,
        PAYWALL_SHOWN,
        PREMIUM_SCREEN_OPEN,
        PURCHASE_INITIATED,
        PURCHASE_COMPLETE,
        COMMUNITY_POST_VIEWED,
    }
)


def is_allowed(event_type: str) -> bool:
    return event_type in ALLOWED_CLIENT_EVENTS
