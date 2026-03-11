from fastapi import APIRouter, Depends
from app.postgres_async import get_async_db

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("/{user_id}")
async def get_notifications(user_id: str, limit: int = 30, db=Depends(get_async_db)):
    """사용자 알림 목록 (최신순, 읽지 않은 것 우선)"""
    rows = await db.fetch(
        """
        SELECT id, type, title, body, is_read, created_at
        FROM notifications
        WHERE user_id = $1
        ORDER BY is_read ASC, created_at DESC
        LIMIT $2
        """,
        user_id, limit,
    )
    return [dict(r) for r in rows]


@router.get("/{user_id}/unread-count")
async def get_unread_count(user_id: str, db=Depends(get_async_db)):
    """읽지 않은 알림 수"""
    row = await db.fetchrow(
        "SELECT COUNT(*) as count FROM notifications WHERE user_id = $1 AND is_read = FALSE",
        user_id,
    )
    return {"count": row["count"]}


@router.post("/{user_id}/mark-read")
async def mark_all_read(user_id: str, db=Depends(get_async_db)):
    """모든 알림 읽음 처리"""
    await db.execute(
        "UPDATE notifications SET is_read = TRUE WHERE user_id = $1 AND is_read = FALSE",
        user_id,
    )
    return {"ok": True}
