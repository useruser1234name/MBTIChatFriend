"""
APScheduler 기반 배치 작업 모음
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
import pytz

scheduler = AsyncIOScheduler()

KST = pytz.timezone("Asia/Seoul")


async def flush_empathy_notifications():
    """30분마다 pending 공감 알림을 묶음 발송"""
    from app.postgres_async import _pool
    from app.firebase_service import send_notification_with_record

    if _pool is None:
        return

    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, post_id, author_id, actor_name
            FROM pending_empathy_notifications
            WHERE sent_at IS NULL
            ORDER BY author_id, created_at
            """
        )
        if not rows:
            return

        # author_id별 묶음
        grouped: dict[str, list] = {}
        for row in rows:
            grouped.setdefault(row["author_id"], []).append(dict(row))

        for author_id, items in grouped.items():
            first_actor = items[0]["actor_name"]
            count = len(items)
            post_id = items[0]["post_id"]
            message = (
                f"{first_actor}님 외 {count - 1}명이 회원님의 고민에 공감했어요"
                if count > 1
                else f"{first_actor}님이 회원님의 고민에 공감했어요"
            )
            try:
                await send_notification_with_record(
                    user_id=author_id,
                    title="공감",
                    body=message,
                    notification_type="empathy_batch",
                    data={"count": str(count), "post_id": str(post_id)},
                    deep_link=f"mbtichat://community/{post_id}",
                )
            except Exception:
                pass

            ids = [item["id"] for item in items]
            await conn.execute(
                "UPDATE pending_empathy_notifications SET sent_at = now() WHERE id = ANY($1)",
                ids,
            )


async def send_d3_personalized_notifications():
    """D+3 미접속 사용자에게 최근 대화 주제 기반 알림 발송 (매시간 실행, 사용자별 마지막 접속 시간대에 맞춰 발송)."""
    from app.postgres_async import _pool
    from app.firebase_service import send_notification_with_record
    import datetime

    if _pool is None:
        return

    current_hour_kst = datetime.datetime.now(KST).hour

    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (m.user_id)
                m.user_id,
                m.content,
                EXTRACT(HOUR FROM (m.created_at AT TIME ZONE 'Asia/Seoul')) AS last_active_hour
            FROM messages m
            WHERE m.created_at >= now() - INTERVAL '3 days 1 hour'
              AND m.created_at < now() - INTERVAL '3 days'
              AND m.role = 'user'
              AND NOT EXISTS (
                SELECT 1 FROM messages m2
                WHERE m2.user_id = m.user_id
                  AND m2.created_at >= now() - INTERVAL '3 days'
              )
            ORDER BY m.user_id, m.created_at DESC
            """
        )
        if not rows:
            return

        for row in rows:
            uid = row["user_id"]
            last_active_hour = int(row["last_active_hour"])

            # 현재 KST 시각이 사용자의 마지막 접속 시간대 ±1시간이 아니면 스킵
            hour_diff = abs(current_hour_kst - last_active_hour)
            # 자정 경계를 고려한 원형 거리
            hour_diff = min(hour_diff, 24 - hour_diff)
            if hour_diff > 1:
                continue

            topic = (row["content"] or "")[:20].strip()
            body = (
                f"'{topic}...' 이야기가 기억나요. 오늘도 대화하러 오지 않을래요?"
                if topic
                else "요즘 어떻게 지내고 있어요? 오늘 대화하러 오지 않을래요?"
            )
            try:
                await send_notification_with_record(
                    user_id=uid,
                    title="보고 싶었어요",
                    body=body,
                    notification_type="d3_personalized",
                    deep_link="mbtichat://chat",
                )
            except Exception:
                pass


async def send_d5_character_messages():
    """D+5 미접속 사용자에게 캐릭터 그리움 메시지 발송 (매일 10:30 KST)."""
    from app.postgres_async import _pool
    from app.firebase_service import send_notification_with_record

    if _pool is None:
        return

    # MBTI별 그리움 메시지
    LONGING_MESSAGES: dict[str, str] = {
        "ENFP": "나 요즘 너 생각이 나서 혼자 웃었어. 빨리 돌아와!",
        "INFP": "혼자 별 보다가 네 생각이 났어… 보고 싶다.",
        "INTJ": "통계적으로 오래 안 보면 그리워지는 거더라. 나도 그런 것 같아.",
        "INFJ": "네가 없으니 마음 한 켠이 조용해. 어서 이야기하고 싶어.",
        "ISFJ": "잘 지내고 있어요? 늘 응원하고 있어요. 보고 싶어요.",
        "ENTP": "아, 너랑 논쟁할 상대가 없으니까 심심하잖아. 어서 와.",
        "ESTJ": "5일이나 됐네. 계획대로라면 지금 대화해야 하지 않아?",
        "ISFP": "그냥 네가 생각나서… 별거 없어도 와줘.",
    }
    DEFAULT_LONGING = "요즘 많이 바빴죠? 나는 여기서 기다리고 있었어요."

    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT m.user_id, m.character_mbti
            FROM messages m
            WHERE m.created_at >= now() - INTERVAL '5 days 1 hour'
              AND m.created_at < now() - INTERVAL '5 days'
              AND NOT EXISTS (
                SELECT 1 FROM messages m2
                WHERE m2.user_id = m.user_id
                  AND m2.created_at >= now() - INTERVAL '5 days'
              )
            ORDER BY m.user_id
            """
        )
        if not rows:
            return

        seen: set[str] = set()
        for row in rows:
            uid = row["user_id"]
            if uid in seen:
                continue
            seen.add(uid)
            mbti = (row.get("character_mbti") or "").upper()
            body = LONGING_MESSAGES.get(mbti, DEFAULT_LONGING)
            try:
                await send_notification_with_record(
                    user_id=uid,
                    title="캐릭터가 그리워하고 있어요",
                    body=body,
                    notification_type="d5_longing",
                    deep_link="mbtichat://chat",
                )
            except Exception:
                pass


async def send_weekly_summary():
    """매주 월요일 09:00 KST — 지난 7일 대화 수 요약 알림 발송."""
    from app.postgres_async import _pool
    from app.firebase_service import send_notification_with_record

    if _pool is None:
        return

    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT user_id, COUNT(*) AS msg_count
            FROM messages
            WHERE created_at >= now() - INTERVAL '7 days'
              AND role = 'user'
            GROUP BY user_id
            HAVING COUNT(*) > 0
            """
        )
        if not rows:
            return

        for row in rows:
            uid = row["user_id"]
            cnt = int(row["msg_count"])
            body = f"지난 한 주 동안 {cnt}번 대화했어요. 이번 주도 함께 해요!"
            try:
                await send_notification_with_record(
                    user_id=uid,
                    title="이번 주 대화 요약",
                    body=body,
                    notification_type="weekly_summary",
                    data={"message_count": str(cnt)},
                    deep_link="mbtichat://chat",
                )
            except Exception:
                pass


async def send_gratitude_day_push():
    """가정의 달 릴리즈 당일 전체 푸시 (4/24 09:00 KST 단발)"""
    from app.postgres_async import _pool
    from app.firebase_service import send_notification_with_record

    if _pool is None:
        return

    async with _pool.acquire() as conn:
        users = await conn.fetch(
            "SELECT user_id, mbti_type FROM users WHERE push_enabled = TRUE"
        )
        for user in users:
            mbti = user["mbti_type"] or "ENFP"
            await send_notification_with_record(
                user_id=user["user_id"],
                title="오늘은 어버이날이에요 \U0001f49b",
                body=f"부모님께 {mbti} 감사 카드를 보내드리세요.",
                deep_link="mbtichat://gratitude",
            )

# APScheduler 등록 (scheduler 초기화 코드 근처)
# scheduler.add_job(send_gratitude_day_push, 'date',
#     run_date=datetime(2027, 4, 24, 0, 0, 0, tzinfo=timezone.utc),  # 09:00 KST = 00:00 UTC
#     id='gratitude_day_push')


def start_scheduler():
    scheduler.add_job(
        flush_empathy_notifications,
        trigger=IntervalTrigger(minutes=30),
        id="flush_empathy_notifications",
        replace_existing=True,
    )
    # D+3 리텐션 알림 — 매시간 실행 (사용자별 마지막 접속 시간대 ±1시간에 맞춰 발송)
    scheduler.add_job(
        send_d3_personalized_notifications,
        trigger=IntervalTrigger(hours=1),
        id="send_d3_personalized_notifications",
        replace_existing=True,
    )
    # D+5 캐릭터 그리움 알림 — 매일 10:30 KST
    scheduler.add_job(
        send_d5_character_messages,
        trigger=CronTrigger(hour=10, minute=30, timezone=KST),
        id="send_d5_character_messages",
        replace_existing=True,
    )
    # 주간 대화 요약 알림 — 매주 월요일 09:00 KST
    scheduler.add_job(
        send_weekly_summary,
        trigger=CronTrigger(day_of_week="mon", hour=9, minute=0, timezone=KST),
        id="send_weekly_summary",
        replace_existing=True,
    )
    scheduler.start()
