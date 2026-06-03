"""다이어리 엔드포인트"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..auth_middleware import verify_firebase_token
from ..chat_service import generate_diary
from ..models import DiaryRequest, DiaryResponse
from ..postgres_async import get_async_db

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api/v1", tags=["diary"])


async def get_uid(user: Optional[dict] = Depends(verify_firebase_token)) -> str:
    """Firebase 인증 토큰에서 uid 추출."""
    if not user or not user.get("uid"):
        raise HTTPException(status_code=401, detail="인증이 필요합니다.")
    return user["uid"]


@router.post("/diary/generate", response_model=DiaryResponse)
@limiter.limit("10/minute")
async def generate_diary_entry(
    request: Request,
    req: DiaryRequest,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """캐릭터 시점에서 오늘의 일기 생성"""
    # PM 로드맵: 밤 일기 주간 한도 게이팅 (FREE 주 3회, PREMIUM 무제한).
    if user and user.get("uid"):
        from ..subscription import get_subscription_manager

        allowed, reason = await get_subscription_manager().check_night_diary_limit(
            user["uid"]
        )
        if not allowed:
            raise HTTPException(status_code=402, detail=reason)

    diary_text, emotion = await generate_diary(
        character_name=req.character_name,
        mbti=req.mbti,
        speech_style=req.speech_style,
        nickname=req.nickname,
        affinity_level=req.affinity_level,
        conversation_history=req.conversation_history,
    )
    return DiaryResponse(diary=diary_text, emotion=emotion)


# ── 사용자 감정 일기 CRUD (32차 스프린트) ──────────────────────────────────

@router.post("/diary/entries")
async def create_diary_entry(
    content: str,
    emotion_tags: list[str] = [],
    uid: str = Depends(get_uid),
    conn=Depends(get_async_db),
):
    """사용자 감정 일기 생성"""
    row = await conn.fetchrow(
        "INSERT INTO user_diary_entries(user_id, content, emotion_tags) VALUES($1,$2,$3) RETURNING *",
        uid, content, emotion_tags
    )
    return dict(row)


@router.get("/diary/entries")
async def get_diary_entries(
    uid: str = Depends(get_uid),
    conn=Depends(get_async_db),
):
    """사용자 감정 일기 목록 조회 (최근 30건)"""
    rows = await conn.fetch(
        "SELECT * FROM user_diary_entries WHERE user_id=$1 AND deleted_at IS NULL ORDER BY created_at DESC LIMIT 30",
        uid
    )
    return [dict(r) for r in rows]


@router.get("/diary/weekly-report")
async def get_weekly_report(
    uid: str = Depends(get_uid),
    conn=Depends(get_async_db),
):
    """최근 7일 감정 태그 집계 리포트"""
    rows = await conn.fetch("""
        SELECT emotion_tags, COUNT(*) as count
        FROM user_diary_entries
        WHERE user_id=$1 AND created_at >= NOW() - INTERVAL '7 days' AND deleted_at IS NULL
        GROUP BY emotion_tags
    """, uid)
    return {"weekly_emotions": [dict(r) for r in rows]}
