"""채팅 라우터: send_message, stream_message"""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from ..auth_middleware import verify_firebase_token
from ..content_filter import check_content, check_crisis
from ..models import ChatRequest, ChatResponse, ReplyPart
from ..shared import limiter, _handle_crisis_response, _run_chat_pipeline

router = APIRouter()


@router.post("/chat/send", response_model=ChatResponse)
@limiter.limit("30/minute")
async def send_message(
    request: Request,
    req: ChatRequest,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """기존 REST 방식 (하위 호환)"""
    is_safe, reason = check_content(req.message)
    if not is_safe:
        raise HTTPException(status_code=400, detail=reason)

    # 위기 키워드 감지 → 개입 응답 반환
    is_crisis, tier, intervention = check_crisis(req.message)
    if is_crisis and tier == 1:
        return ChatResponse(
            replies=[ReplyPart(text=intervention, emotion="WORRIED", delay=0)],
            affinity_delta=0,
        )

    result = await _run_chat_pipeline(req, user)

    # Tier 2 위기: 일반 응답 + 상담 안내 추가
    _handle_crisis_response(is_crisis, tier, intervention, result["replies"])

    return ChatResponse(
        replies=result["replies"],
        affinity_delta=result["affinity_delta"],
        night_diary_generated=result["night_diary_generated"],
        next_hook=result["next_hook"],
        next_goal=result["next_goal"],
    )


@router.post("/chat/stream")
@limiter.limit("30/minute")
async def stream_message(
    request: Request,
    req: ChatRequest,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """SSE 스트리밍 방식 - 메시지를 실시간으로 분할 전송"""
    is_safe, reason = check_content(req.message)
    if not is_safe:
        raise HTTPException(status_code=400, detail=reason)

    # 위기 키워드 감지
    is_crisis, tier, intervention = check_crisis(req.message)
    if is_crisis and tier == 1:
        crisis_reply = ReplyPart(text=intervention, emotion="WORRIED", delay=0)

        async def crisis_generator():
            data = json.dumps({"text": crisis_reply.text, "emotion": crisis_reply.emotion, "delay": 0}, ensure_ascii=False)
            yield {"event": "message", "data": data}
            yield {"event": "done", "data": json.dumps({"affinity_delta": 0, "night_diary_generated": False, "next_hook": "", "next_goal": "", "room_id": ""}, ensure_ascii=False)}

        return EventSourceResponse(crisis_generator())

    result = await _run_chat_pipeline(req, user)
    replies = result["replies"]
    affinity_delta = result["affinity_delta"]

    # Tier 2 위기: 일반 응답 뒤에 상담 안내 추가
    _handle_crisis_response(is_crisis, tier, intervention, replies)

    async def event_generator():
        for reply in replies:
            data = json.dumps({
                "text": reply.text,
                "emotion": reply.emotion,
                "delay": reply.delay
            }, ensure_ascii=False)
            yield {
                "event": "message",
                "data": data
            }

        # 완료 이벤트 (호감도 변화 포함)
        done_data = json.dumps({
            "affinity_delta": affinity_delta,
            "night_diary_generated": result["night_diary_generated"],
            "next_hook": result["next_hook"],
            "next_goal": result["next_goal"],
            "room_id": result["room_id"],
        }, ensure_ascii=False)
        yield {
            "event": "done",
            "data": done_data
        }

    return EventSourceResponse(event_generator())
