"""FastAPI 메인 서버"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager

import uvicorn
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sse_starlette.sse import EventSourceResponse

from openai import AsyncOpenAI

from .auth_middleware import verify_firebase_token
from .chat_service import generate_reply, generate_diary, extract_memories
from .finetune_service import (
    prepare_and_start_finetune,
    check_finetune_status,
    activate_model,
)
from .config import CORS_ORIGINS, HOST, PORT, OPENAI_API_KEY
from .content_filter import check_content
from .firebase_service import (
    init_firebase,
    register_token,
    get_token,
    send_push_notification,
)
from .models import (
    ChatRequest, ChatResponse,
    FcmTokenRequest, FcmSendRequest,
    DiaryRequest, DiaryResponse,
    MemoryExtractRequest, MemoryExtractResponse,
    FinetuneRequest, FinetuneResponse,
    FinetuneStatusResponse, FinetuneActivateRequest,
    ImageGenerateRequest, ImageGenerateResponse,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("MBTI Chat Friend 서버 시작")
    init_firebase()
    yield
    logger.info("서버 종료")


app = FastAPI(
    title="MBTI Chat Friend API",
    version="0.5.0",
    lifespan=lifespan
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/api/v1/chat/send", response_model=ChatResponse)
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

    replies, affinity_delta = await generate_reply(
        message=req.message,
        mbti=req.mbti,
        speech_style=req.speech_style,
        relationship=req.relationship,
        nickname=req.nickname,
        affinity_level=req.affinity_level,
        conversation_history=req.conversation_history,
        user_mbti=req.user_mbti,
        character_name=req.character_name,
        character_id=req.character_id,
        memories=req.memories or []
    )

    return ChatResponse(replies=replies, affinity_delta=affinity_delta)


@app.post("/api/v1/chat/stream")
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

    replies, affinity_delta = await generate_reply(
        message=req.message,
        mbti=req.mbti,
        speech_style=req.speech_style,
        relationship=req.relationship,
        nickname=req.nickname,
        affinity_level=req.affinity_level,
        conversation_history=req.conversation_history,
        user_mbti=req.user_mbti,
        character_name=req.character_name,
        character_id=req.character_id,
        memories=req.memories or []
    )

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
            # 딜레이를 서버에서 적용하여 실시간 타이핑 효과
            await asyncio.sleep(reply.delay / 1000.0)

        # 완료 이벤트 (호감도 변화 포함)
        done_data = json.dumps({
            "affinity_delta": affinity_delta
        }, ensure_ascii=False)
        yield {
            "event": "done",
            "data": done_data
        }

    return EventSourceResponse(event_generator())


# === 메모리 엔드포인트 ===


@app.post("/api/v1/memory/extract", response_model=MemoryExtractResponse)
@limiter.limit("10/minute")
async def extract_memory(
    request: Request,
    req: MemoryExtractRequest,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """대화에서 장기 기억 추출"""
    memories = await extract_memories(
        character_name=req.character_name,
        nickname=req.nickname,
        conversation_history=req.conversation_history,
        character_id=req.character_id,
    )
    return MemoryExtractResponse(memories=memories)


# === FCM 엔드포인트 ===


@app.post("/api/v1/fcm/register")
async def register_fcm_token(
    req: FcmTokenRequest,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """FCM 토큰 등록"""
    user_id = req.user_id or "anonymous"
    register_token(user_id, req.token)
    return {"status": "ok"}


@app.post("/api/v1/fcm/send")
async def send_fcm_notification(
    req: FcmSendRequest,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """FCM 푸시 알림 발송"""
    token = get_token(req.user_id)
    if not token:
        raise HTTPException(status_code=404, detail="FCM token not found for user")

    data = {}
    if req.character_name:
        data["character_name"] = req.character_name
    if req.character_id:
        data["character_id"] = str(req.character_id)
    data["message"] = req.body

    success = send_push_notification(
        token=token,
        title=req.title,
        body=req.body,
        data=data,
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to send notification")

    return {"status": "sent"}


# === 다이어리 엔드포인트 ===


@app.post("/api/v1/diary/generate", response_model=DiaryResponse)
@limiter.limit("10/minute")
async def generate_diary_entry(
    request: Request,
    req: DiaryRequest,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """캐릭터 시점에서 오늘의 일기 생성"""
    diary_text, emotion = await generate_diary(
        character_name=req.character_name,
        mbti=req.mbti,
        speech_style=req.speech_style,
        nickname=req.nickname,
        affinity_level=req.affinity_level,
        conversation_history=req.conversation_history,
    )
    return DiaryResponse(diary=diary_text, emotion=emotion)


# === 이미지 생성 엔드포인트 ===


@app.post("/api/v1/image/generate", response_model=ImageGenerateResponse)
@limiter.limit("10/minute")
async def generate_image(
    request: Request,
    req: ImageGenerateRequest,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """DALL-E 3 이미지 생성 프록시"""
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")

    try:
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        response = await client.images.generate(
            model="dall-e-3",
            prompt=req.prompt,
            n=1,
            size=req.size,
            quality=req.quality,
        )
        image_data = response.data[0]
        return ImageGenerateResponse(
            url=image_data.url,
            revised_prompt=image_data.revised_prompt,
        )
    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# === Fine-tuning 엔드포인트 ===


@app.post("/api/v1/finetune/start", response_model=FinetuneResponse)
@limiter.limit("5/minute")
async def start_finetune(
    request: Request,
    req: FinetuneRequest,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """대화 데이터 수집 → OpenAI Fine-tuning 잡 시작"""
    result = await prepare_and_start_finetune(
        character_id=req.character_id,
        character_name=req.character_name,
        mbti=req.mbti,
        speech_style=req.speech_style,
        relationship=req.relationship,
        nickname=req.nickname,
        affinity_level=req.affinity_level,
        conversations=req.conversations,
    )
    return FinetuneResponse(**result)


@app.get("/api/v1/finetune/status/{job_id}", response_model=FinetuneStatusResponse)
async def get_finetune_status(
    job_id: str,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """Fine-tuning 잡 진행 상태 조회"""
    result = await check_finetune_status(job_id)
    return FinetuneStatusResponse(**result)


@app.post("/api/v1/finetune/activate")
async def activate_finetune(
    req: FinetuneActivateRequest,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """완료된 파인튜닝 모델을 캐릭터에 활성화"""
    activate_model(req.character_id, req.model_id)
    return {"status": "ok", "character_id": req.character_id, "model_id": req.model_id}


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=PORT,
        reload=True
    )
