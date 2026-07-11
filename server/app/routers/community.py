from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import json
import random
from app.auth_middleware import require_auth_always, _assert_owner
from app.config import REDIS_URL, TRENDING_CACHE_TTL
from app.postgres_async import get_async_db

router = APIRouter(prefix="/api/v1/community", tags=["community"])

# 익명 닉네임 생성용 풀
_MBTI_ANIMALS = {
    "ENFP": ["황금여우", "빛나는나비", "호기심고양이"],
    "INFP": ["달빛토끼", "조용한사슴", "은빛고래"],
    "INTJ": ["검은독수리", "고요한올빼미", "전략늑대"],
    "INFJ": ["보랏빛학", "심연고래", "신비로운여우"],
    "ISFJ": ["따뜻한곰", "봄빛사슴", "다정한양"],
    "ENTP": ["번개고양이", "반짝이는까마귀", "날카로운매"],
    "ESTJ": ["황금사자", "든든한코끼리", "의지의황소"],
    "ISFP": ["산들바람새", "조용한고라니", "부드러운수달"],
}
_DEFAULT_ANIMALS = ["용감한다람쥐", "호기심두더지", "빛나는너구리"]

def _generate_anonymous_name(mbti: str) -> str:
    animals = _MBTI_ANIMALS.get(mbti, _DEFAULT_ANIMALS)
    return f"{mbti} {random.choice(animals)}"


class PostCreate(BaseModel):
    user_id: str
    mbti: str = Field(..., min_length=4, max_length=4)
    content: str = Field(..., max_length=300)


class EmpathyToggle(BaseModel):
    user_id: str
    anonymous_name: str = "익명"


class CommentCreate(BaseModel):
    user_id: str
    mbti: str = Field(..., min_length=4, max_length=4)
    content: str = Field(..., max_length=150)


@router.post("/posts", status_code=201)
async def create_post(
    body: PostCreate,
    user: dict = Depends(require_auth_always),
    db=Depends(get_async_db),
):
    """게시글 작성"""
    _assert_owner(user, body.user_id)
    anonymous_name = _generate_anonymous_name(body.mbti.upper())
    row = await db.fetchrow(
        """
        INSERT INTO community_posts (user_id, mbti, content, anonymous_name)
        VALUES ($1, $2, $3, $4)
        RETURNING id, mbti, content, anonymous_name, empathy_count, created_at
        """,
        body.user_id, body.mbti.upper(), body.content, anonymous_name,
    )
    return dict(row)


@router.get("/posts")
async def list_posts(mbti: Optional[str] = None, limit: int = 20, offset: int = 0, db=Depends(get_async_db)):
    """MBTI별 게시글 목록 (최신순)"""
    if mbti:
        rows = await db.fetch(
            """
            SELECT id, mbti, content, anonymous_name, empathy_count, comment_count, created_at
            FROM community_posts
            WHERE deleted_at IS NULL AND is_hidden = FALSE AND mbti = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            mbti.upper(), limit, offset,
        )
    else:
        rows = await db.fetch(
            """
            SELECT id, mbti, content, anonymous_name, empathy_count, comment_count, created_at
            FROM community_posts
            WHERE deleted_at IS NULL AND is_hidden = FALSE
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset,
        )
    return [dict(r) for r in rows]


_REDIS_URL = REDIS_URL
_TRENDING_TTL = TRENDING_CACHE_TTL

# 스키마 정합성: community_posts 컬럼은 mbti(=mbti_type 아님), 공감 테이블은
# community_empathies(복합 PK post_id+user_id, id 컬럼 없음). 클라이언트 TrendingPostUi가
# mbti_type 키를 기대하므로 p.mbti AS mbti_type 으로 매핑한다.
_TRENDING_QUERY = """
        SELECT p.id, p.user_id, p.mbti AS mbti_type, p.content, p.comment_count,
               p.created_at,
               COUNT(DISTINCT e.user_id) AS empathy_count,
               (COUNT(DISTINCT e.user_id) + p.comment_count) AS score
        FROM community_posts p
        LEFT JOIN community_empathies e ON e.post_id = p.id
        WHERE p.deleted_at IS NULL
          AND p.created_at >= now() - INTERVAL '{interval}'
        GROUP BY p.id
        ORDER BY score DESC
        LIMIT $1
        """

_TRENDING_QUERY_MBTI = """
        SELECT p.id, p.user_id, p.mbti AS mbti_type, p.content, p.comment_count,
               p.created_at,
               COUNT(DISTINCT e.user_id) AS empathy_count,
               (COUNT(DISTINCT e.user_id) + p.comment_count) AS score
        FROM community_posts p
        LEFT JOIN community_empathies e ON e.post_id = p.id
        WHERE p.deleted_at IS NULL
          AND p.created_at >= now() - INTERVAL '{interval}'
          AND p.mbti = $2
        GROUP BY p.id
        ORDER BY score DESC
        LIMIT $1
        """


@router.get("/posts/pinned")
async def get_pinned_posts(db=Depends(get_async_db)):
    """고정 공지 게시글 — 인증 불필요"""
    rows = await db.fetch("""
        SELECT p.id, p.mbti, p.content, p.anonymous_name, p.comment_count,
               p.created_at, p.is_pinned,
               COUNT(DISTINCT e.user_id) AS empathy_count
        FROM community_posts p
        LEFT JOIN community_empathies e ON e.post_id = p.id
        WHERE p.is_pinned = TRUE AND p.deleted_at IS NULL AND p.is_hidden = FALSE
        GROUP BY p.id
        ORDER BY p.created_at DESC
    """)
    return [dict(r) for r in rows]


@router.get("/posts/public-ids")
async def get_public_post_ids(db=Depends(get_async_db)):
    """공개 게시글 ID 목록 조회 — 인증 불필요. 삭제·숨김 제외."""
    rows = await db.fetch("""
        SELECT id, created_at FROM community_posts
        WHERE deleted_at IS NULL AND is_hidden = FALSE
        ORDER BY id DESC
    """)
    return [{"id": r["id"], "updated_at": str(r["created_at"])} for r in rows]


@router.get("/posts/trending")
async def get_trending_posts(limit: int = 3, mbti: Optional[str] = None, db=Depends(get_async_db)):
    """인기 게시글 조회 (최근 24시간, 결과 부족 시 72시간 폴백, Redis TTL 600초 캐싱).
    mbti 파라미터가 있으면 해당 MBTI 유형의 게시글만 조회."""
    import aioredis

    mbti_upper = mbti.upper() if mbti else None
    cache_key = f"trending:posts:{limit}:{mbti_upper or 'all'}"

    # Redis 캐시 확인
    redis = None
    try:
        redis = await aioredis.from_url(_REDIS_URL, decode_responses=True)
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass  # Redis 연결 실패 시 캐시 없이 진행

    if mbti_upper:
        # MBTI 필터 적용 쿼리
        rows = await db.fetch(
            _TRENDING_QUERY_MBTI.format(interval="24 hours"),
            limit, mbti_upper,
        )
        if len(rows) < limit:
            rows = await db.fetch(
                _TRENDING_QUERY_MBTI.format(interval="72 hours"),
                limit, mbti_upper,
            )
    else:
        # 전체 조회 쿼리
        rows = await db.fetch(
            _TRENDING_QUERY.format(interval="24 hours"),
            limit,
        )
        # 결과가 limit 미만이면 72시간으로 폴백
        if len(rows) < limit:
            rows = await db.fetch(
                _TRENDING_QUERY.format(interval="72 hours"),
                limit,
            )

    result = [dict(r) for r in rows]

    # Redis 캐시 저장
    try:
        if redis is not None:
            await redis.set(cache_key, json.dumps(result, default=str), ex=_TRENDING_TTL)
    except Exception:
        pass
    finally:
        if redis is not None:
            try:
                await redis.close()
            except Exception:
                pass

    return result


@router.get("/posts/event-trending")
async def get_event_trending_posts(db=Depends(get_async_db)):
    """이벤트 트렌딩 — 최근 31일 공감 상위 5건.

    (이전 버전은 '2027-04-10~05-01' 하드코딩이라 항상 빈 결과였음 — 연도 무관 윈도우로 수정.)
    스키마: community_posts.mbti / community_empathies(post_id,user_id) 기준.
    """
    rows = await db.fetch("""
        SELECT p.id, p.content, p.mbti, p.anonymous_name, p.comment_count, p.created_at,
               COUNT(DISTINCT e.user_id) AS empathy_count
        FROM community_posts p
        LEFT JOIN community_empathies e ON e.post_id = p.id
        WHERE p.is_pinned = FALSE
          AND p.deleted_at IS NULL
          AND p.is_hidden = FALSE
          AND p.created_at >= now() - INTERVAL '31 days'
        GROUP BY p.id
        ORDER BY empathy_count DESC
        LIMIT 5
    """)
    return [dict(r) for r in rows]


@router.get("/posts/{post_id}")
async def get_post(post_id: int, db=Depends(get_async_db)):
    """게시글 상세"""
    row = await db.fetchrow(
        """
        SELECT id, mbti, content, anonymous_name, empathy_count, created_at
        FROM community_posts
        WHERE id = $1 AND deleted_at IS NULL AND is_hidden = FALSE
        """,
        post_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Post not found")
    return dict(row)


@router.get("/posts/{post_id}/public")
async def get_public_post(post_id: int, db=Depends(get_async_db)):
    """게시글 공개 조회 — 인증 불필요"""
    row = await db.fetchrow("""
        SELECT p.id, p.mbti AS mbti_type, p.content, p.anonymous_name, p.comment_count,
               p.created_at,
               COUNT(DISTINCT e.user_id) AS empathy_count
        FROM community_posts p
        LEFT JOIN community_empathies e ON e.post_id = p.id
        WHERE p.id = $1 AND p.deleted_at IS NULL
        GROUP BY p.id
    """, post_id)
    if not row:
        raise HTTPException(status_code=404, detail="Post not found")
    return dict(row)


@router.delete("/posts/{post_id}", status_code=204)
async def delete_post(
    post_id: int,
    user_id: str,
    user: dict = Depends(require_auth_always),
    db=Depends(get_async_db),
):
    """게시글 소프트 삭제 (본인만)"""
    _assert_owner(user, user_id)
    result = await db.execute(
        """
        UPDATE community_posts
        SET deleted_at = now()
        WHERE id = $1 AND user_id = $2 AND deleted_at IS NULL
        """,
        post_id, user_id,
    )
    if result == "UPDATE 0":
        raise HTTPException(status_code=403, detail="Not authorized or already deleted")


@router.post("/posts/{post_id}/empathy")
async def toggle_empathy(
    post_id: int,
    body: EmpathyToggle,
    user: dict = Depends(require_auth_always),
    db=Depends(get_async_db),
):
    """공감 토글 (추가 또는 취소)"""
    _assert_owner(user, body.user_id)
    existing = await db.fetchrow(
        "SELECT 1 FROM community_empathies WHERE post_id = $1 AND user_id = $2",
        post_id, body.user_id,
    )
    if existing:
        # 공감 취소
        await db.execute(
            "DELETE FROM community_empathies WHERE post_id = $1 AND user_id = $2",
            post_id, body.user_id,
        )
        await db.execute(
            "UPDATE community_posts SET empathy_count = empathy_count - 1 WHERE id = $1",
            post_id,
        )
        return {"empathized": False}
    else:
        # 공감 추가
        await db.execute(
            "INSERT INTO community_empathies (post_id, user_id) VALUES ($1, $2)",
            post_id, body.user_id,
        )
        await db.execute(
            "UPDATE community_posts SET empathy_count = empathy_count + 1 WHERE id = $1",
            post_id,
        )
        # 게시글 작성자 조회 후 pending 큐에 추가 (자기 공감 제외)
        post_row = await db.fetchrow(
            "SELECT user_id FROM community_posts WHERE id = $1 AND deleted_at IS NULL",
            post_id,
        )
        if post_row and post_row["user_id"] != body.user_id:
            await db.execute(
                """
                INSERT INTO pending_empathy_notifications (post_id, author_id, actor_name)
                VALUES ($1, $2, $3)
                """,
                post_id, post_row["user_id"], body.anonymous_name,
            )
        return {"empathized": True}


@router.post("/posts/{post_id}/report")
async def report_post(
    post_id: int,
    body: dict,
    user: dict = Depends(require_auth_always),
    db=Depends(get_async_db),
):
    """게시글 신고. 동일 사용자의 중복 신고는 무시. 신고 3회 이상 시 자동 숨김(트리거)."""
    user_id = body.get("user_id", "")
    reason = body.get("reason", "")
    if not user_id or not reason:
        raise HTTPException(status_code=422, detail="user_id와 reason이 필요합니다")
    _assert_owner(user, user_id)
    await db.execute("""
        INSERT INTO post_reports(reporter_id, post_id, reason)
        VALUES ($1, $2, $3)
        ON CONFLICT(reporter_id, post_id) DO NOTHING
    """, user_id, post_id, reason)
    return {"ok": True}


@router.post("/posts/{post_id}/comments", status_code=201)
async def create_comment(
    post_id: int,
    body: CommentCreate,
    user: dict = Depends(require_auth_always),
    db=Depends(get_async_db),
):
    """댓글 작성. 게시글 작성자에게 FCM 알림."""
    _assert_owner(user, body.user_id)
    anonymous_name = _generate_anonymous_name(body.mbti.upper())
    row = await db.fetchrow(
        """
        INSERT INTO community_comments (post_id, user_id, mbti, content, anonymous_name)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, post_id, mbti, content, anonymous_name, created_at
        """,
        post_id, body.user_id, body.mbti.upper(), body.content, anonymous_name,
    )
    # 게시글 작성자 FCM 알림 (자기 댓글 제외)
    post_row = await db.fetchrow(
        "SELECT user_id FROM community_posts WHERE id = $1 AND deleted_at IS NULL",
        post_id,
    )
    if post_row and post_row["user_id"] != body.user_id:
        try:
            from ..firebase_service import send_notification_with_record
            await send_notification_with_record(
                user_id=post_row["user_id"],
                title="새 댓글",
                body=f"{anonymous_name}님이 회원님의 게시글에 댓글을 남겼어요",
                notification_type="community_comment",
                data={"post_id": str(post_id)},
                deep_link=f"mbtichat://community/{post_id}",
            )
        except Exception:
            pass
    return dict(row)


@router.get("/posts/{post_id}/comments")
async def list_comments(post_id: int, db=Depends(get_async_db)):
    """게시글 댓글 목록 (오래된 순)"""
    rows = await db.fetch(
        """
        SELECT id, mbti, content, anonymous_name, created_at
        FROM community_comments
        WHERE post_id = $1 AND deleted_at IS NULL
        ORDER BY created_at ASC
        """,
        post_id,
    )
    return [dict(r) for r in rows]


@router.delete("/posts/{post_id}/comments/{comment_id}", status_code=204)
async def delete_comment(
    post_id: int,
    comment_id: int,
    user_id: str,
    user: dict = Depends(require_auth_always),
    db=Depends(get_async_db),
):
    """댓글 소프트 삭제 (본인만)"""
    _assert_owner(user, user_id)
    result = await db.execute(
        """
        UPDATE community_comments
        SET deleted_at = now()
        WHERE id = $1 AND post_id = $2 AND user_id = $3 AND deleted_at IS NULL
        """,
        comment_id, post_id, user_id,
    )
    if result == "UPDATE 0":
        raise HTTPException(status_code=403, detail="Not authorized or already deleted")
