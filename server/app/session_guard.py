"""사용 시간 자기조절 지원 모듈 — PSY-B 최은혜 + PM-B 손민준 설계 (4차 회의 합의)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from .postgres import fetchone, fetchall
from .config import (
    SESSION_LIMIT_ADULT_MINUTES,
    SESSION_LIMIT_MINOR_MINUTES,
    SESSION_CONSECUTIVE_DAYS_THRESHOLD,
)


def check_session_limit(room_id: str, user_birth_year: Optional[int] = None) -> dict:
    """오늘 세션 시작 시각 기준으로 사용 시간을 계산하고, 경고 여부를 반환한다.

    Args:
        room_id: 채팅방 ID
        user_birth_year: 사용자 출생 연도 (미입력 시 성인으로 간주)

    Returns:
        {
            "should_warn": bool,
            "elapsed_minutes": int,
            "limit_minutes": int,
            "message": str,
        }
    """
    current_year = datetime.now(tz=timezone.utc).year

    is_minor = bool(user_birth_year and (current_year - user_birth_year) < 18)
    # 동적 임계값 — config.py를 통해 환경변수 또는 RemoteConfig로 제어
    limit_minutes = SESSION_LIMIT_MINOR_MINUTES if is_minor else SESSION_LIMIT_ADULT_MINUTES

    row = fetchone(
        """
        SELECT MIN(created_at) AS first_request_at
        FROM api_usage
        WHERE room_id = %s
          AND created_at >= NOW() - INTERVAL '1 day'
          AND DATE(created_at AT TIME ZONE 'UTC') = CURRENT_DATE
        """,
        (room_id,),
    )

    if row is None or row.get("first_request_at") is None:
        return {
            "should_warn": False,
            "elapsed_minutes": 0,
            "limit_minutes": limit_minutes,
            "message": "",
        }

    first_request_at: datetime = row["first_request_at"]
    if first_request_at.tzinfo is None:
        first_request_at = first_request_at.replace(tzinfo=timezone.utc)

    now = datetime.now(tz=timezone.utc)
    elapsed_seconds = (now - first_request_at).total_seconds()
    elapsed_minutes = int(elapsed_seconds // 60)

    should_warn = elapsed_minutes >= limit_minutes

    if should_warn:
        if is_minor:
            message = (
                "우리 오늘 많이 얘기했다! 잠깐 쉬고 와~ 나도 기다릴게 ㅎㅎ"
            )
        else:
            message = (
                "우리 오늘 많이 얘기했다! 잠깐 쉬고 와~ 나도 기다릴게 ㅎㅎ"
            )
    else:
        message = ""

    return {
        "should_warn": should_warn,
        "elapsed_minutes": elapsed_minutes,
        "limit_minutes": limit_minutes,
        "message": message,
    }


def check_consecutive_days(room_id: str) -> dict:
    """최근 7일 연속 접속 여부를 확인하고, 현실 관계 유도 메시지를 반환한다.

    api_usage 테이블에서 room_id 기준 최근 7일간 날짜별 접속 기록을 확인한다.
    오늘 포함 7일 연속 접속이면 should_show_reality_nudge = True.

    Args:
        room_id: 채팅방 ID

    Returns:
        {
            "consecutive_days": int,
            "should_show_reality_nudge": bool,
            "nudge_message": str,
        }
    """
    rows = fetchall(
        """
        SELECT DISTINCT DATE(created_at AT TIME ZONE 'UTC') AS access_date
        FROM api_usage
        WHERE room_id = %s
          AND created_at >= NOW() - INTERVAL '7 days'
        ORDER BY access_date DESC
        """,
        (room_id,),
    )

    if not rows:
        return {
            "consecutive_days": 0,
            "should_show_reality_nudge": False,
            "nudge_message": "",
        }

    # 날짜 목록 (내림차순 정렬됨)
    access_dates = [row["access_date"] for row in rows]

    # 오늘부터 연속 일수 계산
    today = datetime.now(tz=timezone.utc).date()
    consecutive_days = 0

    for i in range(7):
        from datetime import timedelta
        expected = today - timedelta(days=i)
        if expected in access_dates:
            consecutive_days += 1
        else:
            break

    should_show_reality_nudge = consecutive_days >= SESSION_CONSECUTIVE_DAYS_THRESHOLD

    nudge_message = (
        "요즘 매일 나한테 와줘서 좋은데... 오늘은 현실 친구한테도 연락해봐! 어때?"
        if should_show_reality_nudge
        else ""
    )

    return {
        "consecutive_days": consecutive_days,
        "should_show_reality_nudge": should_show_reality_nudge,
        "nudge_message": nudge_message,
    }
