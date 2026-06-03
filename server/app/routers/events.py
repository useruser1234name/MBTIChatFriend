"""클라이언트 분석 이벤트 수집 엔드포인트 (PM 로드맵 — 최소 계측).

배치 수집으로 네트워크 오버헤드를 줄인다. user_id는 인증 토큰에서 채워
metric_events에 기록하므로 클라이언트가 타인 명의로 이벤트를 남길 수 없다.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..analytics_events import is_allowed
from ..auth_middleware import require_auth_always
from ..metrics_service import record_event

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api/v1/events", tags=["analytics"])


class ClientEvent(BaseModel):
    event_type: str = Field(..., min_length=1, max_length=64)
    room_id: str = ""
    character_id: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class EventBatch(BaseModel):
    events: list[ClientEvent] = Field(..., max_length=100)


@router.post("/batch")
@limiter.limit("60/minute")
async def ingest_events(
    request: Request,
    batch: EventBatch,
    user: dict = Depends(require_auth_always),
):
    """클라이언트 분석 이벤트 배치 적재.

    - 인증 필수: user_id는 토큰에서 채운다(클라이언트 값 무시).
    - 허용 목록(analytics_events.ALLOWED_CLIENT_EVENTS)에 없는 event_type은 건너뛴다.
    """
    uid = user.get("uid", "")
    accepted = 0
    skipped: list[str] = []
    for ev in batch.events:
        if not is_allowed(ev.event_type):
            skipped.append(ev.event_type)
            continue
        record_event(
            event_type=ev.event_type,
            room_id=ev.room_id,
            character_id=ev.character_id,
            user_id=uid,
            payload=ev.payload,
        )
        accepted += 1
    return {"accepted": accepted, "skipped": skipped}
