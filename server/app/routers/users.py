"""사용자 관련 엔드포인트 (연말 리포트 등)"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional

from ..auth_middleware import verify_firebase_token
from ..postgres_async import get_async_db

router = APIRouter(prefix="/api/v1/users", tags=["users"])


async def get_uid(user: Optional[dict] = Depends(verify_firebase_token)) -> str:
    """Firebase 인증 토큰에서 uid 추출. 인증 실패 시 401."""
    if not user or not user.get("uid"):
        raise HTTPException(status_code=401, detail="인증이 필요합니다.")
    return user["uid"]


@router.get("/year-report")
async def get_year_report(uid: str = Depends(get_uid), db=Depends(get_async_db)):
    """연말 대화 리포트 — 2026년 누적 통계 반환."""
    total_messages = await db.fetchval(
        """
        SELECT COUNT(*) FROM messages
        WHERE user_id = $1 AND created_at >= '2026-01-01'
        """,
        uid,
    )
    top_character = await db.fetchrow(
        """
        SELECT character_mbti, COUNT(*) AS cnt
        FROM messages WHERE user_id = $1 AND created_at >= '2026-01-01'
        GROUP BY character_mbti ORDER BY cnt DESC LIMIT 1
        """,
        uid,
    )
    top_post = await db.fetchrow(
        """
        SELECT p.content, COUNT(e.id) AS empathy_count
        FROM community_posts p
        LEFT JOIN community_empathies e ON e.post_id = p.id
        WHERE p.user_id = $1 AND p.created_at >= '2026-01-01'
        GROUP BY p.id, p.content ORDER BY empathy_count DESC LIMIT 1
        """,
        uid,
    )
    return {
        "total_messages": total_messages or 0,
        "top_character": top_character["character_mbti"] if top_character else None,
        "top_post_summary": top_post["content"][:50] if top_post else None,
        "top_post_empathy": int(top_post["empathy_count"]) if top_post else 0,
    }
