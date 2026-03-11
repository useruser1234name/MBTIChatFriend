"""관계 히스토리 & 기억 앨범 엔드포인트"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..auth_middleware import verify_firebase_token
from ..models import (
    MemoryMomentRequest,
    RelationshipSummaryResponse,
)
from ..relationship_history import (
    get_relationship_summary,
    save_memory_moment,
    get_memory_album,
)

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api/v1", tags=["relationship"])


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
