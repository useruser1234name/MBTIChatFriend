"""관계 히스토리 & 기억 앨범 & 호감도 미러링 엔드포인트"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..auth_middleware import verify_firebase_token
from ..models import (
    MemoryMomentRequest,
    RelationshipSummaryResponse,
)
from ..postgres_async import get_async_db
from ..relationship_history import (
    get_relationship_summary,
    save_memory_moment,
    get_memory_album,
)

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api/v1", tags=["relationship"])


# ── 호감도 미러링 스키마 ──────────────────────────────────────────────

class AffinitySyncRequest(BaseModel):
    """클라이언트 → 서버 호감도 동기화 요청."""
    room_id: str = Field(..., min_length=1)
    character_id: str = Field(..., min_length=1)
    score: int = Field(..., ge=0, le=100)
    level: int = Field(..., ge=1, le=5)


class AffinityResponse(BaseModel):
    room_id: str
    character_id: str
    score: int
    level: int


@router.get(
    "/relationship/{room_id}/summary",
    response_model=RelationshipSummaryResponse,
)
async def relationship_summary(
    room_id: str,
    character_id: str = "",
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """관계 히스토리 요약 조회.

    총 메시지 수·세션 수·함께한 일수·호감도 변화 이력·관심 토픽 top-5·
    첫 대화 날짜를 반환한다. 캐릭터 투자감 강화의 핵심 지표.

    UX-B 안현우 + UI-C 정수아 설계 (5차 회의 합의).
    """
    if not room_id.strip():
        raise HTTPException(status_code=400, detail="room_id가 필요합니다.")

    data = await get_relationship_summary(room_id=room_id, character_id=character_id)
    return RelationshipSummaryResponse(**data)


@router.post("/relationship/{room_id}/memory")
@limiter.limit("60/minute")
async def save_relationship_memory(
    request: Request,
    room_id: str,
    req: MemoryMomentRequest,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """특별한 순간을 기억 앨범에 저장.

    moment_type: "special" | "funny" | "touching"
    사용자가 직접 하이라이트 메시지를 앨범에 담는다.

    UX-B 안현우 + UI-C 정수아 설계 (5차 회의 합의).
    """
    if not room_id.strip():
        raise HTTPException(status_code=400, detail="room_id가 필요합니다.")

    user_id = (user or {}).get("uid", "")
    result = await save_memory_moment(
        room_id=room_id,
        character_id=req.character_id,
        user_id=user_id,
        message_text=req.message_text,
        moment_type=req.moment_type,
        user_note=req.user_note,
    )
    return result


@router.post("/affinity/sync", response_model=AffinityResponse)
@limiter.limit("60/minute")
async def sync_affinity(
    request: Request,
    req: AffinitySyncRequest,
    user: Optional[dict] = Depends(verify_firebase_token),
    db=Depends(get_async_db),
):
    """클라이언트 호감도 점수를 서버에 동기화 (미러링).

    room_id 소유자 검증: room_id는 '{uid}:...' 형식이어야 한다.
    재설치 후 복구 및 서버 권위 데이터 확보용.
    """
    if user:
        uid = user.get("uid", "")
        if uid and not req.room_id.startswith(uid):
            raise HTTPException(status_code=403, detail="본인의 room_id만 동기화할 수 있습니다.")

    await db.execute(
        """
        INSERT INTO affinity_scores (room_id, character_id, score, level, updated_at)
        VALUES ($1, $2, $3, $4, NOW())
        ON CONFLICT (room_id) DO UPDATE
        SET character_id = $2, score = $3, level = $4, updated_at = NOW()
        """,
        req.room_id,
        req.character_id,
        req.score,
        req.level,
    )
    return AffinityResponse(
        room_id=req.room_id,
        character_id=req.character_id,
        score=req.score,
        level=req.level,
    )


@router.get("/affinity/{room_id}", response_model=AffinityResponse)
async def get_affinity(
    room_id: str,
    user: Optional[dict] = Depends(verify_firebase_token),
    db=Depends(get_async_db),
):
    """서버에 저장된 호감도 점수 조회 (재설치 복구용).

    room_id 소유자 검증 적용.
    """
    if user:
        uid = user.get("uid", "")
        if uid and not room_id.startswith(uid):
            raise HTTPException(status_code=403, detail="본인의 room_id만 조회할 수 있습니다.")

    row = await db.fetchrow(
        "SELECT room_id, character_id, score, level FROM affinity_scores WHERE room_id = $1",
        room_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="호감도 데이터가 없습니다.")
    return AffinityResponse(**row)


@router.get("/relationship/{room_id}/album")
async def get_relationship_album(
    room_id: str,
    character_id: str = "",
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """저장된 기억 앨범 조회.

    최신순 정렬로 최대 200개의 기억 앨범 항목을 반환한다.

    UX-B 안현우 + UI-C 정수아 설계 (5차 회의 합의).
    """
    if not room_id.strip():
        raise HTTPException(status_code=400, detail="room_id가 필요합니다.")

    items = await get_memory_album(room_id=room_id, character_id=character_id)
    return {"album": items}
