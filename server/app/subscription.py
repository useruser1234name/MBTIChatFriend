"""구독 플랜 관리 모듈 — CTO-A 박지훈 + ARCH-C 오세진 설계.

설계 원칙:
  - 게이팅은 '위협'이 아닌 '초대' 어조로 안내한다.
  - FREE 유저도 기본 경험은 충분히 즐거워야 한다.
  - 서버사이드에서 플랜 제한을 검증하여 클라이언트 우회를 원천 차단한다.
  - 실제 결제 연동은 다음 스프린트; 이번 스프린트는 게이팅 인프라만 구축한다.
"""

from __future__ import annotations

import logging
from enum import Enum
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)


# ── 플랜 정의 ─────────────────────────────────────────────────────────────────


class Plan(str, Enum):
    FREE = "free"
    PREMIUM = "premium"


# ── 플랜별 제한 설정 ──────────────────────────────────────────────────────────
# -1 은 무제한을 의미한다.
PLAN_LIMITS: dict[Plan, dict] = {
    Plan.FREE: {
        "max_characters": 1,       # 동시에 대화 가능한 캐릭터 수
        "daily_messages": 50,       # 일일 메시지 한도
        "max_memories": 5,          # 저장 가능한 장기 기억 수
        "max_affinity_level": 3,    # 호감도 4-5는 프리미엄 전용
        "expression_set": False,    # 표정 세트 생성 비활성
        # PM 로드맵: 가장 강력한 D7 훅인 밤 일기를 FREE에도 주 3회 제공
        "night_diary": True,        # 야간 일기 활성 (주간 한도 적용)
        "night_diary_weekly_limit": 3,  # FREE: 주 3회 (월/수/금 등)
    },
    Plan.PREMIUM: {
        "max_characters": 5,
        "daily_messages": -1,       # 무제한
        "max_memories": -1,         # 무제한
        "max_affinity_level": 5,
        "expression_set": True,
        "night_diary": True,
        "night_diary_weekly_limit": -1,  # 무제한 (매일)
    },
}

# ── 업그레이드 안내 메시지 (UX 친화적 초대 어조) ───────────────────────────────
# "막힌다"가 아닌 "더 깊은 관계를 원한다면" 식의 어조를 유지할 것.
_UPGRADE_PROMPTS: dict[str, str] = {
    "daily_messages": (
        "오늘 나눌 수 있는 대화가 모두 소진됐어요. "
        "프리미엄으로 업그레이드하면 하루에 얼마든지 이야기를 나눌 수 있답니다 💬"
    ),
    "affinity": (
        "호감도 4단계부터는 더 깊은 감정을 함께 나눌 수 있어요. "
        "프리미엄으로 업그레이드하면 모든 단계에서 특별한 순간들을 경험할 수 있답니다 💌"
    ),
    "expression_set": (
        "표정 세트는 캐릭터의 감정을 더 생생하게 전달해줘요. "
        "프리미엄 플랜에서 15가지 감정 표현을 모두 만나보세요 🎭"
    ),
    "night_diary": (
        "야간 일기는 오늘 하루를 함께한 캐릭터의 솔직한 마음이 담겨있어요. "
        "프리미엄으로 업그레이드하면 매일 밤 캐릭터의 일기를 받아볼 수 있답니다 🌙"
    ),
    "max_characters": (
        "지금은 한 명의 친구와 집중해서 이야기를 나눠보세요. "
        "프리미엄 플랜에서는 최대 5명의 캐릭터와 다양한 관계를 맺을 수 있답니다 👥"
    ),
    "max_memories": (
        "소중한 추억들이 점점 쌓이고 있어요. "
        "프리미엄 플랜에서는 기억 제한 없이 모든 순간을 간직할 수 있답니다 📖"
    ),
    "default": (
        "더 풍부한 경험을 원하신다면 프리미엄 플랜을 고려해보세요. "
        "캐릭터와의 관계가 한층 깊어질 거예요 ✨"
    ),
}


# ── SubscriptionManager ───────────────────────────────────────────────────────


class SubscriptionManager:
    """플랜 조회, 제한 검사, 업그레이드 안내를 담당하는 서비스 클래스.

    DB 연동: user_subscriptions 테이블 (postgres.py 스키마 참조).
    DB 미설정 환경에서는 모든 유저를 FREE로 간주한다 (안전 기본값).
    """

    # ── 플랜 조회 ──────────────────────────────────────────────────────────────

    def get_plan(self, user_id: str) -> Plan:
        """user_id 기반 현재 구독 플랜 조회.

        user_subscriptions 테이블에서 만료되지 않은 최신 플랜을 읽는다.
        레코드가 없거나 DB 오류 시 FREE를 기본값으로 반환한다.
        """
        from .postgres import fetchone, postgres_enabled

        if not postgres_enabled():
            return Plan.FREE

        try:
            row = fetchone(
                """
                SELECT plan FROM user_subscriptions
                WHERE user_id = %s
                  AND (expires_at IS NULL OR expires_at > NOW())
                """,
                (user_id,),
            )
            if row and row.get("plan") in Plan._value2member_map_:
                return Plan(row["plan"])
        except Exception as e:
            logger.error(f"[Subscription] 플랜 조회 실패 user_id={user_id}: {e}")

        return Plan.FREE

    def get_limits(self, user_id: str) -> dict:
        """user_id의 현재 플랜에 맞는 제한값 딕셔너리 반환."""
        plan = self.get_plan(user_id)
        return dict(PLAN_LIMITS[plan])

    # ── 일일 메시지 한도 확인 ──────────────────────────────────────────────────

    async def check_message_limit(
        self, user_id: str, room_id: str
    ) -> tuple[bool, str]:
        """오늘 해당 user의 메시지(api_usage 행) 수가 일일 한도를 초과했는지 확인.

        api_usage 테이블의 room_id는 '{uid}:...' 형식으로 저장된다.
        FREE 플랜: 50개 초과 시 거부.
        PREMIUM 플랜 또는 daily_messages=-1: 항상 허용.

        Returns:
            (is_allowed: bool, reason: str)
        """
        from .postgres_async import get_async_db

        limits = self.get_limits(user_id)
        daily_limit: int = limits["daily_messages"]

        # 무제한 플랜
        if daily_limit == -1:
            return True, ""

        db = get_async_db()
        if not db.available:
            # DB 미연결 시 낙관적 허용 (서비스 중단 방지)
            logger.warning(
                f"[Subscription] DB 미연결 — 메시지 한도 검사 스킵 (user={user_id})"
            )
            return True, ""

        try:
            row = await db.fetchone(
                """
                SELECT COUNT(*) AS msg_count
                FROM api_usage
                WHERE room_id LIKE $1
                  AND created_at >= CURRENT_DATE
                """,
                f"{user_id}:%",
            )
            count = int(row["msg_count"]) if row else 0
        except Exception as e:
            logger.error(f"[Subscription] 메시지 한도 조회 실패: {e}")
            return True, ""  # 낙관적 허용

        if count >= daily_limit:
            reason = (
                f"오늘 {daily_limit}개의 메시지를 모두 사용하셨어요. "
                "내일 다시 대화를 이어갈 수 있답니다."
            )
            return False, reason

        return True, ""

    # ── 밤 일기 주간 한도 ──────────────────────────────────────────────────────

    async def check_night_diary_limit(self, user_id: str) -> tuple[bool, str]:
        """이번 주 밤 일기 생성 가능 여부 확인.

        PM 로드맵: FREE는 주 3회, PREMIUM은 무제한.
        diary_entries.room_id는 '{uid}:...' 형식. 이번 주(월요일 기준) 생성 수를 센다.

        Returns:
            (is_allowed: bool, reason: str)
        """
        from .postgres_async import get_async_db

        limits = self.get_limits(user_id)
        if not limits.get("night_diary", False):
            return False, self.get_upgrade_prompt("night_diary")

        weekly_limit: int = limits.get("night_diary_weekly_limit", -1)
        if weekly_limit == -1:
            return True, ""

        db = get_async_db()
        if not db.available:
            return True, ""  # DB 미연결 시 낙관적 허용

        try:
            row = await db.fetchone(
                """
                SELECT COUNT(*) AS cnt
                FROM diary_entries
                WHERE room_id LIKE $1
                  AND created_at >= date_trunc('week', NOW())
                """,
                f"{user_id}:%",
            )
            used = int(row["cnt"]) if row else 0
        except Exception as e:
            logger.error(f"[Subscription] 밤 일기 한도 조회 실패: {e}")
            return True, ""  # 낙관적 허용

        if used >= weekly_limit:
            reason = (
                f"이번 주 밤 일기 {weekly_limit}회를 모두 받았어요. "
                "프리미엄으로 업그레이드하면 매일 밤 일기를 받아볼 수 있답니다 🌙"
            )
            return False, reason
        return True, ""

    # ── 호감도 레벨 게이팅 ────────────────────────────────────────────────────

    def check_affinity_gate(
        self, user_id: str, requested_level: int
    ) -> tuple[bool, str]:
        """요청된 호감도 레벨 접근 허용 여부 확인.

        FREE 플랜은 최대 호감도 3까지만 허용한다.
        4-5단계는 PREMIUM 전용으로, 더 깊은 관계의 대화가 가능하다.

        Returns:
            (is_allowed: bool, reason: str)
        """
        limits = self.get_limits(user_id)
        max_level: int = limits["max_affinity_level"]

        if requested_level <= max_level:
            return True, ""

        reason = self.get_upgrade_prompt("affinity")
        return False, reason

    # ── 업그레이드 안내 메시지 ─────────────────────────────────────────────────

    def get_upgrade_prompt(self, feature: str) -> str:
        """게이팅 시 표시할 업그레이드 안내 메시지.

        어조 원칙:
          - 위협/차단 느낌 금지 ("이 기능은 사용할 수 없습니다" X)
          - 초대/가능성 어조 사용 ("더 깊은 관계를 원한다면" O)
          - 감정적 공감을 담아 자연스럽게 연결
        """
        return _UPGRADE_PROMPTS.get(feature, _UPGRADE_PROMPTS["default"])


# ── 전역 싱글톤 ───────────────────────────────────────────────────────────────

_subscription_manager = SubscriptionManager()


def get_subscription_manager() -> SubscriptionManager:
    """애플리케이션 전역 SubscriptionManager 인스턴스 반환."""
    return _subscription_manager
