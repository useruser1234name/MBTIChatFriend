"""FastAPI 메인 서버"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime

import uvicorn
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sse_starlette.sse import EventSourceResponse

from openai import AsyncOpenAI

from .auth_middleware import verify_firebase_token
from .chat_service import generate_reply, generate_diary, extract_memories, generate_night_diary
from .finetune_service import (
    prepare_and_start_finetune,
    check_finetune_status,
    activate_model,
)
from .config import CORS_ORIGINS, HOST, PORT, OPENAI_API_KEY, FIREBASE_STORAGE_BUCKET
from .diary_store import has_night_diary, night_bucket_date, save_night_diary
from .metrics_service import record_event
from .postgres import init_postgres_schema
from .story_state_store import (
    apply_diary_outcome,
    build_story_memory_items,
    bump_turn_and_get_state,
    get_story_state,
    mark_callback_used,
    maybe_build_callback_hint,
)
from .content_filter import check_content
from .firebase_service import (
    init_firebase,
    register_token,
    get_token,
    send_push_notification,
)
from .image_service import (
    init_storage,
    generate_and_upload_base,
    start_expression_set_task,
    get_task_status,
)
from .models import (
    ChatRequest, ChatResponse,
    FcmTokenRequest, FcmSendRequest,
    DiaryRequest, DiaryResponse,
    MemoryExtractRequest, MemoryExtractResponse,
    FinetuneRequest, FinetuneResponse,
    FinetuneStatusResponse, FinetuneActivateRequest,
    ImageGenerateRequest, ImageGenerateResponse,
    ImageSetRequest, ImageSetResponse, ImageSetStatusResponse,
    MemoryItem,
    FeedbackRequest, QualityDashboardResponse,
)
from .quality_service import (
    get_diversity_report,
    get_quality_dashboard,
)
from .postgres import execute as pg_execute, to_jsonb

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("MBTI Chat Friend 서버 시작")
    init_firebase()
    init_storage()
    init_postgres_schema()
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


def _resolve_room_id(req: ChatRequest, user: Optional[dict]) -> str:
    if req.room_id and req.room_id.strip():
        return req.room_id.strip()

    uid = (user or {}).get("uid", "anonymous")
    character = req.character_id or req.mbti or "unknown"
    nickname = req.nickname or "user"
    return f"{uid}:{character}:{nickname}"


def _is_night_window(client_local_hour: Optional[int]) -> bool:
    if client_local_hour is None:
        return False
    return (22 <= client_local_hour <= 23) or (0 <= client_local_hour <= 4)


def _merge_memories(base: list[MemoryItem], extra: list[MemoryItem]) -> list[MemoryItem]:
    merged: list[MemoryItem] = []
    seen_keys: set[str] = set()

    for item in (base or []) + (extra or []):
        key = item.key.strip()
        value = item.value.strip()
        if not key or not value:
            continue
        if key in seen_keys:
            continue
        seen_keys.add(key)
        merged.append(MemoryItem(key=key, value=value))

    return merged


async def _run_chat_pipeline(req: ChatRequest, user: Optional[dict]) -> dict:
    room_id = _resolve_room_id(req, user)
    character_id = req.character_id or ""

    state = bump_turn_and_get_state(room_id, character_id)
    effective_character_id = character_id or state.character_id
    callback_key, callback_hint = maybe_build_callback_hint(state)
    story_memories = build_story_memory_items(state, callback_hint or "")
    merged_memories = _merge_memories(req.memories or [], story_memories)

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
        character_id=effective_character_id,
        memories=merged_memories,
    )

    if callback_key:
        mark_callback_used(room_id, callback_key, state.turn_count)

    night_diary_generated = False
    next_hook = state.next_hook
    next_goal = state.next_goal

    if req.end_of_session and _is_night_window(req.client_local_hour):
        diary_date = night_bucket_date(req.client_local_hour)
        if not has_night_diary(room_id, effective_character_id, diary_date):
            diary_text, diary_emotion, diary_next_hook, diary_next_goal = await generate_night_diary(
                character_name=req.character_name,
                mbti=req.mbti,
                speech_style=req.speech_style,
                nickname=req.nickname,
                affinity_level=req.affinity_level,
                conversation_history=req.conversation_history,
            )
            saved = save_night_diary(
                room_id=room_id,
                character_id=effective_character_id,
                diary_date=diary_date,
                diary_text=diary_text,
                emotion=diary_emotion,
                next_hook=diary_next_hook,
                next_goal=diary_next_goal,
            )
            if saved:
                night_diary_generated = True
                apply_diary_outcome(room_id, effective_character_id, diary_next_hook, diary_next_goal)
                next_hook = diary_next_hook
                next_goal = diary_next_goal
                record_event(
                    event_type="night_diary_generated",
                    room_id=room_id,
                    character_id=effective_character_id,
                    payload={
                        "diary_date": diary_date.isoformat(),
                        "emotion": diary_emotion,
                        "next_hook": diary_next_hook,
                        "next_goal": diary_next_goal,
                    },
                )

    if not next_hook or not next_goal:
        latest = get_story_state(room_id, effective_character_id)
        next_hook = next_hook or latest.next_hook
        next_goal = next_goal or latest.next_goal

    record_event(
        event_type="chat_turn",
        room_id=room_id,
        character_id=effective_character_id,
        payload={
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "turn_count": state.turn_count,
            "affinity_delta": affinity_delta,
            "callback_used": bool(callback_key),
            "end_of_session": req.end_of_session,
            "night_diary_generated": night_diary_generated,
            "client_local_hour": req.client_local_hour,
        },
    )

    return {
        "room_id": room_id,
        "replies": replies,
        "affinity_delta": affinity_delta,
        "night_diary_generated": night_diary_generated,
        "next_hook": next_hook or "",
        "next_goal": next_goal or "",
    }


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

    result = await _run_chat_pipeline(req, user)
    return ChatResponse(
        replies=result["replies"],
        affinity_delta=result["affinity_delta"],
        night_diary_generated=result["night_diary_generated"],
        next_hook=result["next_hook"],
        next_goal=result["next_goal"],
    )


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

    result = await _run_chat_pipeline(req, user)
    replies = result["replies"]
    affinity_delta = result["affinity_delta"]

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
    """gpt-image-1 이미지 생성 → Firebase Storage 업로드"""
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")

    try:
        import uuid
        character_id = str(uuid.uuid4())
        url, revised = await generate_and_upload_base(
            prompt=req.prompt,
            character_id=character_id,
            size=req.size,
            quality=req.quality,
        )
        return ImageGenerateResponse(url=url, revised_prompt=revised)
    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/image/generate-set", response_model=ImageSetResponse)
@limiter.limit("5/minute")
async def generate_image_set(
    request: Request,
    req: ImageSetRequest,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """표정 세트 15장 백그라운드 생성 시작"""
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")

    try:
        task_id = start_expression_set_task(
            base_prompt=req.base_prompt,
            character_id=req.character_id,
            size=req.size,
        )
        return ImageSetResponse(status="processing", task_id=task_id)
    except Exception as e:
        logger.error(f"Expression set generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/image/set-status/{task_id}", response_model=ImageSetStatusResponse)
async def get_image_set_status(
    task_id: str,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """표정 세트 생성 진행 상황 조회"""
    status = get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")

    return ImageSetStatusResponse(
        status=status["status"],
        completed=status["completed"],
        total=status["total"],
        urls=status["urls"],
    )


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


# === 피드백 & 품질 엔드포인트 ===


@app.post("/api/v1/feedback/submit")
@limiter.limit("30/minute")
async def submit_feedback(
    request: Request,
    req: FeedbackRequest,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """사용자 피드백 제출 (thumbs_up / thumbs_down)"""
    try:
        pg_execute(
            """
            INSERT INTO response_feedback
                (room_id, character_id, message_id, feedback_type, feedback_detail)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                req.room_id,
                req.character_id,
                req.message_id,
                req.feedback_type,
                req.feedback_detail,
            ),
        )
    except Exception as e:
        logger.error(f"피드백 저장 실패: {e}")
        raise HTTPException(status_code=500, detail="피드백 저장에 실패했습니다.")

    return {"status": "ok"}


@app.get("/api/v1/quality/dashboard", response_model=QualityDashboardResponse)
async def quality_dashboard(
    character_id: str = "",
    days: int = 30,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """품질 대시보드 조회"""
    data = get_quality_dashboard(character_id, days)
    return QualityDashboardResponse(**data)


@app.get("/api/v1/quality/diversity/{character_id}")
async def diversity_report(
    character_id: str,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """다양성 리포트 조회"""
    return get_diversity_report(character_id)


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=PORT,
        reload=True
    )
