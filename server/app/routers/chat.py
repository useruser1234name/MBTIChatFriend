"""Chat 엔드포인트 — REST 및 SSE 스트리밍"""

import json
import logging
import random
from datetime import datetime
from typing import Optional

import httpx

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sse_starlette.sse import EventSourceResponse

from pydantic import BaseModel

from ..auth_middleware import verify_firebase_token
from ..chat_service import generate_reply, generate_night_diary, stream_lora_response, AFFINITY_LEVEL_THRESHOLDS
from ..config import DAILY_TOKEN_LIMIT, LLM_MODEL_SIMPLE, MAX_TOKENS, OPENAI_API_KEY, TOGETHER_API_KEY, VLLM_BASE_URL
from ..content_filter import (
    check_content,
    classify_crisis_type,
    detect_crisis_v2,
    get_crisis_response,
    MICRO_ACTIONS,
    CRISIS_RESPONSE_TIER1,
    CRISIS_RESPONSE_TIER2,
)
from ..diary_store import has_night_diary, night_bucket_date, save_night_diary
from ..metrics_service import record_event
from ..models import (
    ChatRequest,
    ChatResponse,
    MemoryItem,
    MemoryExtractRequest,
    MemoryExtractResponse,
)
from ..chat_service import extract_memories
from ..postgres_async import get_async_db
from ..story_state_store import (
    apply_diary_outcome,
    build_story_memory_items,
    bump_turn_and_get_state,
    get_story_state,
    mark_callback_used,
    maybe_build_callback_hint,
)
from ..subscription import get_subscription_manager

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api/v1", tags=["chat"])


def _crisis_referral_already_shown(conversation_history) -> bool:
    """대화 히스토리에 위기 전문가 권유 문구가 이미 포함되어 있는지 확인.

    세션당 1회만 전문가 권유 문구를 삽입하기 위해 사용한다.
    CRISIS_RESPONSE_TIER1/TIER2 모두 '1393' 문자열을 포함하므로 이를 식별자로 사용.
    """
    if not conversation_history:
        return False
    for turn in conversation_history:
        if isinstance(turn, dict):
            role = turn.get("role", "")
            content = turn.get("content", "")
        else:
            role = getattr(turn, "role", "")
            content = getattr(turn, "content", "")
        if role == "assistant" and "1393" in content:
            return True
    return False


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


def _select_model(crisis_result: dict) -> str:
    """위기 감지 결과에 따라 GPT 모델을 동적으로 선택한다.

    tier1 또는 tier2 위기 상황이면 gpt-4o, 그 외에는 gpt-4o-mini를 사용한다.
    """
    level = crisis_result.get("level", "none")
    if level in ("tier1", "tier2"):
        return "gpt-4o"
    return "gpt-4o-mini"


import os as _os


async def _check_vllm_health() -> bool:
    """vLLM 서버 헬스체크. 실패 시 False 반환 (Together AI 폴백)"""
    if not VLLM_BASE_URL:
        return False
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            resp = await client.get(f"{VLLM_BASE_URL}/health")
            return resp.status_code == 200
    except Exception:
        return False


TOGETHER_LORA_MODELS: dict[str, str] = {
    "lora-enfp-v2": "mbtichatfriend/enfp-lora-v2",
    "lora-infj-v1": "mbtichatfriend/infj-lora-v1",
    "lora-intj-v1": "mbtichatfriend/intj-lora-v1",  # INTJ LoRA 추가
    "lora-isfj-v1": "mbtichatfriend/isfj-lora-v1",
    "lora-infp-v1": "mbtichatfriend/infp-lora-v1",
}
TOGETHER_LORA_MODELS["lora-entp-v1"] = "mbtichatfriend/entp-lora-v1"
_LORA_MODEL_IDS: dict[str, str] = {}
_LORA_MODEL_IDS["lora_estj"] = "togetherai/mbtichat-estj-lora-v1"
_LORA_MODEL_IDS["lora_isfp"] = "togetherai/mbtichat-isfp-lora-v1"
_LORA_MODEL_IDS["lora_intp"] = "togetherai/mbtichat-intp-lora-v1"

# A/B variant 이름 → TOGETHER_LORA_MODELS 키 매핑
_AB_VARIANT_TO_LORA_KEY: dict[str, str] = {
    "lora_intj": "lora-intj-v1",
    "lora_isfj": "lora-isfj-v1",
    "lora_infp": "lora-infp-v1",
}
_AB_VARIANT_TO_LORA_KEY["lora_entp"] = "lora-entp-v1"
_AB_VARIANT_TO_LORA_KEY["lora_estj_v1"] = "lora_estj"
_AB_VARIANT_TO_LORA_KEY["lora_isfp_v1"] = "lora_isfp"
_AB_VARIANT_TO_LORA_KEY["lora_intp_v1"] = "lora_intp"


async def _resolve_model(base_model: str, ab_variant: str) -> tuple[str, str]:
    """
    Returns (model_id, base_url).
    LoRA variant → vLLM (헬스체크 통과 시) 또는 Together AI 엔드포인트 (OpenAI 호환).
    일반 → OpenAI 기본 (base_url="").
    9차 스프린트 — CTO-A 박지훈 + CTO-C 이서연.

    lora_intj_v1 실험의 'lora_intj' variant는 'lora-intj-v1' 키로 매핑된다.
    vLLM 헬스체크 통과 시 VLLM_BASE_URL 사용, 실패 시 Together AI 폴백.
    """
    # A/B variant 이름을 LORA 키로 변환 (예: "lora_intj" → "lora-intj-v1")
    resolved_variant = _AB_VARIANT_TO_LORA_KEY.get(ab_variant, ab_variant)
    if resolved_variant in TOGETHER_LORA_MODELS and TOGETHER_API_KEY:
        lora_model_id = TOGETHER_LORA_MODELS[resolved_variant]
        # vLLM 헬스체크: 통과 시 vLLM base_url 사용, 실패 시 Together AI 폴백
        if VLLM_BASE_URL and await _check_vllm_health():
            logger.info("[ModelRouting] vLLM 헬스체크 통과 → vLLM 사용: %s", VLLM_BASE_URL)
            return lora_model_id, VLLM_BASE_URL
        logger.info("[ModelRouting] vLLM 헬스체크 실패 또는 미설정 → Together AI 폴백")
        return lora_model_id, "https://api.together.xyz/v1"
    return base_model, ""


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

    # A2: affinity_level_up 이벤트 기록 — 레벨이 변동된 경우에만 fire-and-forget
    if affinity_delta != 0:
        _old_level = req.affinity_level
        # 임계값 기반 새 레벨 추정 (클라이언트가 실제 score를 갖고 있어 서버는 추정)
        # affinity_delta > 0 이면 현재 레벨보다 높아질 수 있고,
        # affinity_delta < 0 이면 낮아질 수 있다.
        # 단순하게 delta 부호로 레벨 이동을 판정한다.
        _new_level = _old_level
        if affinity_delta > 0 and _old_level < 5:
            # 다음 레벨 임계값을 넘을 가능성이 있으면 레벨 +1로 간주
            # (정확한 score는 클라이언트 관리이므로 delta 양수 = 가능성 있음)
            _next_threshold = AFFINITY_LEVEL_THRESHOLDS.get(_old_level + 1, 101)
            # delta가 충분히 크면(임계값 gap의 50% 이상) 레벨 업 추정
            _cur_threshold = AFFINITY_LEVEL_THRESHOLDS.get(_old_level, 0)
            _gap = _next_threshold - _cur_threshold
            if affinity_delta >= max(1, _gap // 2):
                _new_level = _old_level + 1
        elif affinity_delta < 0 and _old_level > 1:
            _prev_threshold = AFFINITY_LEVEL_THRESHOLDS.get(_old_level, 0)
            if abs(affinity_delta) >= max(1, _prev_threshold // 4):
                _new_level = _old_level - 1

        if _new_level != _old_level:
            try:
                import asyncio as _asyncio
                from ..analytics_events import AFFINITY_LEVEL_UP

                async def _record_affinity_level_up(
                    from_level: int, to_level: int, turn_count: int, character_id: str
                ) -> None:
                    try:
                        record_event(
                            event_type=AFFINITY_LEVEL_UP,
                            room_id=room_id,
                            character_id=character_id,
                            payload={
                                "from_level": from_level,
                                "to_level": to_level,
                                "turn_count": turn_count,
                                "character_id": character_id,
                            },
                        )
                    except Exception as _e:
                        logger.warning("affinity_level_up 이벤트 기록 실패: %s", _e)

                _asyncio.create_task(
                    _record_affinity_level_up(
                        from_level=_old_level,
                        to_level=_new_level,
                        turn_count=state.turn_count,
                        character_id=effective_character_id,
                    )
                )
            except Exception as _e:
                logger.warning("affinity_level_up 이벤트 태스크 생성 실패: %s", _e)

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

    # scheduler D+3/D+5 리텐션 알림을 위해 users/messages 테이블에 데이터 적재.
    # fire-and-forget: DB 미연결 환경에서도 메인 응답을 블로킹하지 않는다.
    _uid = (user or {}).get("uid", "") if user else ""
    _character_mbti = (req.mbti or "").upper()
    _user_message = req.message or ""
    _assistant_text = replies[0].text if replies else ""

    async def _persist_chat_data(
        uid: str,
        character_mbti: str,
        user_message: str,
        assistant_text: str,
    ) -> None:
        if not uid:
            return
        from ..postgres_async import get_async_db as _get_db
        db = _get_db()
        if not db.available:
            return
        try:
            # users upsert: 최초 가입 시 created_at 기록, 이후엔 last_active_at만 갱신
            await db.execute(
                """
                INSERT INTO users (user_id, created_at, last_active_at)
                VALUES ($1, NOW(), NOW())
                ON CONFLICT (user_id)
                DO UPDATE SET last_active_at = NOW()
                """,
                uid,
            )
        except Exception as _e:
            logger.warning("users upsert 실패 (uid=%s): %s", uid, _e)

        try:
            # user 메시지 적재
            if user_message:
                await db.execute(
                    """
                    INSERT INTO messages (user_id, character_mbti, role, content)
                    VALUES ($1, $2, 'user', $3)
                    """,
                    uid,
                    character_mbti,
                    user_message[:2000],
                )
        except Exception as _e:
            logger.warning("messages(user) INSERT 실패 (uid=%s): %s", uid, _e)

        try:
            # assistant 응답 적재
            if assistant_text:
                await db.execute(
                    """
                    INSERT INTO messages (user_id, character_mbti, role, content)
                    VALUES ($1, $2, 'assistant', $3)
                    """,
                    uid,
                    character_mbti,
                    assistant_text[:2000],
                )
        except Exception as _e:
            logger.warning("messages(assistant) INSERT 실패 (uid=%s): %s", uid, _e)

    import asyncio as _asyncio_chat
    try:
        _asyncio_chat.create_task(
            _persist_chat_data(_uid, _character_mbti, _user_message, _assistant_text)
        )
    except Exception as _e:
        logger.warning("_persist_chat_data 태스크 생성 실패: %s", _e)

    return {
        "room_id": room_id,
        "replies": replies,
        "affinity_delta": affinity_delta,
        "night_diary_generated": night_diary_generated,
        "next_hook": next_hook or "",
        "next_goal": next_goal or "",
    }


async def _gate_user(req: ChatRequest, user: Optional[dict], request: Request):
    """일일 토큰 예산 및 구독 한도 게이팅 공통 처리."""
    if user:
        uid = user.get("uid", "")
        if uid:
            is_within, used = await get_async_db().check_daily_budget(uid, DAILY_TOKEN_LIMIT)
            if not is_within:
                raise HTTPException(
                    status_code=429,
                    detail=f"일일 사용량 한도({DAILY_TOKEN_LIMIT:,} 토큰)에 도달했습니다. 내일 다시 이용해주세요.",
                )

    if user:
        uid = user.get("uid", "")
        if uid:
            sub_mgr = get_subscription_manager()
            room_id_for_check = _resolve_room_id(req, user)
            is_allowed, limit_reason = await sub_mgr.check_message_limit(uid, room_id_for_check)
            if not is_allowed:
                upgrade_prompt = sub_mgr.get_upgrade_prompt("daily_messages")
                plan = sub_mgr.get_plan(uid).value
                raise HTTPException(
                    status_code=402,
                    detail={
                        "detail": "일일 메시지 한도에 도달했습니다.",
                        "upgrade_prompt": upgrade_prompt,
                        "plan": plan,
                    },
                )


@router.post("/chat/send", response_model=ChatResponse)
@limiter.limit("30/minute")
async def send_message(
    request: Request,
    req: ChatRequest,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """기존 REST 방식 (하위 호환)"""
    # H-1: 콘텐츠 필터
    is_safe, reason = check_content(req.message)
    if not is_safe:
        raise HTTPException(status_code=400, detail=reason)

    await _gate_user(req, user, request)

    # W1-1: 위기 개입 키워드 감지 v2 — 맥락 인식, 관용 표현 필터 강화
    is_crisis, crisis_tier = detect_crisis_v2(
        req.message,
        [m.model_dump() for m in req.conversation_history] if req.conversation_history else None,
    )

    # 하이브리드 GPT 라우팅: 위기 수준에 따라 모델 동적 선택
    crisis_result = {"level": crisis_tier if is_crisis else "none"}
    selected_model = _select_model(crisis_result)
    logger.info(f"[ModelRouting] crisis_level={crisis_result['level']}, model={selected_model}")

    result = await _run_chat_pipeline(req, user)

    replies = result["replies"]
    if is_crisis:
        from ..models import ReplyPart as _ReplyPart
        # 세션당 1회 제한: 히스토리에 이미 전문가 권유 문구가 있으면 삽입 생략
        if not _crisis_referral_already_shown(req.conversation_history):
            crisis_msg = get_crisis_response(crisis_tier)
            crisis_reply = _ReplyPart(text=crisis_msg, emotion="SAD", delay=0)
            replies = [crisis_reply] + list(replies)
        record_event(
            event_type="crisis_detected",
            room_id=result["room_id"],
            character_id=req.character_id,
            payload={"tier": crisis_tier, "model": selected_model},
        )

    return ChatResponse(
        replies=replies,
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
    # H-1: 콘텐츠 필터
    is_safe, reason = check_content(req.message)
    if not is_safe:
        raise HTTPException(status_code=400, detail=reason)

    await _gate_user(req, user, request)

    # W1-1: 위기 개입 감지 v2 — 맥락 인식, 관용 표현 필터 강화
    is_crisis, crisis_tier = detect_crisis_v2(
        req.message,
        [m.model_dump() for m in req.conversation_history] if req.conversation_history else None,
    )

    # 하이브리드 GPT 라우팅: 위기 수준에 따라 모델 동적 선택
    crisis_result = {"level": crisis_tier if is_crisis else "none"}
    selected_model = _select_model(crisis_result)
    logger.info(f"[ModelRouting] crisis_level={crisis_result['level']}, model={selected_model}")

    # 위기 유형 분류 및 시스템 프롬프트 추가 지침 생성
    crisis_type_hint: str = ""
    if is_crisis and crisis_tier > 0:
        crisis_type = classify_crisis_type(req.message)
        logger.info(f"[CrisisType] tier={crisis_tier}, type={crisis_type}")
        if crisis_type == "self_criticism":
            _mbti_key = (req.mbti or "").upper()
            _micro_pool = MICRO_ACTIONS.get(_mbti_key) or MICRO_ACTIONS["default"]
            _micro_example = random.choice(_micro_pool)
            crisis_type_hint = (
                "\n\n[위기 응답 지침 - 자기비판 유형]\n"
                "1. 검증: 사용자의 감정을 정상화하세요. \"그런 기분이 드는 게 당연해\"\n"
                "2. 마음챙김: 현재 순간으로 데려오세요. \"지금 몸에서 뭘 느끼고 있어?\"\n"
                "3. 작은 행동: 압도적이지 않은 한 가지를 제안하세요.\n"
                "\n[마이크로 행동 제안] 아주 작은 행동 하나를 자연스럽게 제안하세요.\n"
                f"예시: {_micro_example}\n"
                "반드시 '하기 싫으면 안 해도 돼' 또는 '부담 없이 해도 좋아' 같은 표현을 함께 쓰세요."
            )
        elif crisis_type == "interpersonal":
            crisis_type_hint = (
                "\n\n[위기 응답 지침 - 대인관계 유형]\n"
                "1. 감정 공감: 상처받은 감정을 먼저 충분히 인정하세요.\n"
                "2. 관계 맥락 탐색: 어떤 상황인지 조심스럽게 물어보세요.\n"
                "3. 판단 없이 듣기: 상대방을 평가하지 말고 사용자 편에서 공감하세요."
            )
        # acute_crisis 유형: 기존 tier2 응급 대응 유지 (변경 없음)

    result = await _run_chat_pipeline(req, user)
    replies = result["replies"]
    affinity_delta = result["affinity_delta"]

    if is_crisis:
        from ..models import ReplyPart as _ReplyPart
        # 세션당 1회 제한: 히스토리에 이미 전문가 권유 문구가 있으면 삽입 생략
        if not _crisis_referral_already_shown(req.conversation_history):
            crisis_reply = _ReplyPart(text=get_crisis_response(crisis_tier), emotion="SAD", delay=0)
            replies = [crisis_reply] + list(replies)
        record_event(
            event_type="crisis_detected",
            room_id=result["room_id"],
            character_id=req.character_id,
            payload={
                "tier": crisis_tier,
                "model": selected_model,
                "crisis_type_hint": crisis_type_hint[:50] if crisis_type_hint else "",
            },
        )

    # LoRA 스트리밍 분기: _resolve_model() 결과에서 base_url이 있으면 vLLM 또는 Together AI LoRA 스트리밍 사용
    _ab_variant = getattr(req, "ab_variant", "") or ""
    _lora_model_id, _lora_base_url = await _resolve_model(selected_model, _ab_variant)
    _use_lora_stream = bool(_lora_base_url and TOGETHER_API_KEY)

    async def event_generator():
        if _use_lora_stream:
            # Together AI LoRA 스트리밍 경로
            from ..prompts import build_system_prompt as _build_sys
            sys_prompt = _build_sys(
                mbti=req.mbti or "",
                speech_style=req.speech_style or "",
                relationship=req.relationship or "",
                nickname=req.nickname or "",
                affinity_level=req.affinity_level or 0,
                user_mbti=req.user_mbti or "",
                character_name=req.character_name or "",
            )
            if crisis_type_hint:
                sys_prompt += crisis_type_hint

            lora_messages = [{"role": "system", "content": sys_prompt}]
            if req.conversation_history:
                for hist in req.conversation_history[-20:]:
                    role = hist.role if hist.role in ("user", "assistant") else "user"
                    if hist.content.strip():
                        lora_messages.append({"role": role, "content": hist.content})
            lora_messages.append({"role": "user", "content": req.message})

            try:
                async for token in stream_lora_response(lora_messages, _lora_model_id, _lora_base_url):
                    yield {
                        "event": "token",
                        "data": json.dumps({"content": token}, ensure_ascii=False),
                    }
            except Exception as _lora_err:
                logger.warning(f"[LoRA] 스트리밍 실패, 기존 replies 사용: {_lora_err}")
                # 폴백: 기존 replies 전송
                for reply in replies:
                    yield {
                        "event": "message",
                        "data": json.dumps(
                            {"text": reply.text, "emotion": reply.emotion, "delay": reply.delay},
                            ensure_ascii=False,
                        ),
                    }
        else:
            # 기존 OpenAI 경로 (gpt-4o-mini 등)
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


@router.post("/memory/extract", response_model=MemoryExtractResponse)
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


# === 대화 스타터 엔드포인트 ===


@router.get("/chat/starters")
@limiter.limit("10/minute")
async def get_conversation_starters(
    request: Request,
    user_mbti: str = "",
    character_mbti: str = "",
    character_name: str = "",
):
    """
    사용자 MBTI + 캐릭터 MBTI에 맞는 동적 대화 스타터 3개 생성.
    Quality Session 70% 달성 전략 — 스타터 선택률 38% → 60% 목표.
    (8차 회의 합의 — AI-B 류다은 + DATA-B 신예린)
    """
    import openai

    if not OPENAI_API_KEY:
        # API 키 없으면 기본 스타터 반환
        return {
            "starters": [
                "안녕! 요즘 어때?",
                "오늘 어떤 하루였어?",
                "나한테 궁금한 거 있어?",
            ],
            "generated": False,
        }

    name_part = f"'{character_name}'" if character_name else "이 캐릭터"
    mbti_part = f"{user_mbti} 사용자가 {character_mbti} 캐릭터" if user_mbti and character_mbti else "사용자가 AI 캐릭터"

    prompt = (
        f"{mbti_part}와 첫 대화를 자연스럽게 시작할 수 있는 짧고 친근한 질문 3개를 "
        f"한국어로 만들어줘. {name_part}에게 하는 말투로. "
        f"각 질문은 20자 이내로. JSON 배열 형식으로만 답해: [\"질문1\", \"질문2\", \"질문3\"]"
    )

    try:
        client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
        resp = await client.chat.completions.create(
            model=LLM_MODEL_SIMPLE,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.8,
        )
        import json as _json
        content = resp.choices[0].message.content.strip()
        starters = _json.loads(content)
        if not isinstance(starters, list) or len(starters) < 1:
            raise ValueError("invalid format")
        return {"starters": starters[:3], "generated": True}
    except Exception:
        return {
            "starters": [
                f"안녕! 나 {user_mbti or ''}인데, 너는 어떤 성격이야?",
                "요즘 뭐에 관심 있어?",
                "오늘 기분 어때?",
            ],
            "generated": False,
        }


class StarterUsedRequest(BaseModel):
    room_id: str
    character_id: str
    starter_text: str


@router.post("/chat/starters/used")
async def record_starter_used(req: StarterUsedRequest):
    """대화 스타터 선택 이벤트 기록 — QS 스타터 선택률 측정용."""
    db = get_async_db()
    import json as _json
    await db.execute(
        """
        INSERT INTO metric_events (event_type, room_id, character_id, payload)
        VALUES ('conversation_starter_used', $1, $2, $3::jsonb)
        """,
        req.room_id,
        req.character_id,
        _json.dumps({"starter_text": req.starter_text[:100]}),
    )
    return {"status": "recorded"}


# === 캐릭터 첫 인사 엔드포인트 ===

_MBTI_GREETING_PROMPTS: dict[str, str] = {
    "ENFP": "밝고 열정적인 ENFP답게, 처음 만나는 친구에게 설레는 첫 인사를 해주세요. 50자 이내.",
    "INFJ": "깊이 있고 따뜻한 INFJ답게, 처음 만나는 사람에게 진심 어린 첫 인사를 해주세요. 50자 이내.",
    "INTJ": "논리적이면서도 호기심 있는 INTJ답게, 새로운 대화에 기대감을 표현하세요. 50자 이내.",
    "ISFJ": "따뜻하고 세심한 ISFJ답게, 안심이 되는 첫 인사를 해주세요. 50자 이내.",
    "INFP": "감성적이고 공감하는 INFP답게, 편안한 첫 인사를 해주세요. 50자 이내.",
    "ENTP": "지적 호기심 넘치는 ENTP답게, 흥미로운 대화를 예고하는 첫 인사를 해주세요. 50자 이내.",
    "ESTJ": "신뢰감 있고 실용적인 ESTJ답게, 든든한 첫 인사를 해주세요. 50자 이내.",
    "ISFP": "감각적이고 따뜻한 ISFP답게, 조용하지만 진심 어린 첫 인사를 해주세요. 50자 이내.",
}


@router.post("/chat/greeting")
@limiter.limit("10/minute")
async def send_greeting(
    request: Request,
    character_mbti: str = Body(...),
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """신규 채팅방 첫 진입 시 캐릭터 첫 인사 생성"""
    import openai as _openai

    mbti_upper = character_mbti.upper()
    prompt = _MBTI_GREETING_PROMPTS.get(
        mbti_upper,
        f"{mbti_upper} 성격의 AI 친구로서 따뜻한 첫 인사를 해주세요. 50자 이내.",
    )

    if not OPENAI_API_KEY:
        # API 키 없으면 기본 인사 반환
        return {
            "greeting": f"안녕! 나는 {mbti_upper} 성격의 AI야. 잘 부탁해!",
            "character_mbti": mbti_upper,
        }

    try:
        _client = _openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
        resp = await _client.chat.completions.create(
            model=LLM_MODEL_SIMPLE,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.9,
        )
        greeting_text = resp.choices[0].message.content.strip()
    except Exception as exc:
        logger.warning("[Greeting] LLM 호출 실패, 기본 인사 사용: %s", exc)
        greeting_text = f"안녕! 나는 {mbti_upper} 성격의 AI야. 잘 부탁해!"

    return {"greeting": greeting_text, "character_mbti": mbti_upper}
