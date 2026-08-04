"""Chat 엔드포인트 — REST 및 SSE 스트리밍"""

import asyncio
import json
import logging
import random
import time
import openai
from datetime import datetime, timezone
from typing import Optional, Tuple

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sse_starlette.sse import EventSourceResponse

from pydantic import BaseModel

from ..auth_middleware import verify_firebase_token
from ..chat_service import (
    generate_reply,
    generate_night_diary,
    stream_lora_response,
    stream_reply,
    StreamDone,
    AFFINITY_LEVEL_THRESHOLDS,
)
from ..mbti import get_greeting_emotion
from ..config import DAILY_TOKEN_LIMIT, LLM_MODEL_SIMPLE, MAX_TOKENS, OPENAI_API_KEY, TOGETHER_API_KEY
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
from ..metrics_service import record_event_async
from ..background_tasks import create_tracked_task
from ..model_routing import resolve_model_endpoint, select_model_for_crisis
from ..models import (
    ChatRequest,
    ChatResponse,
    MemoryItem,
    MemoryExtractRequest,
    MemoryExtractResponse,
    ReplyPart,
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


# C4: 시간대 인지 프롬프트 — hour(0-23) → 4구간 라벨.
# 05-10 아침 / 11-16 낮 / 17-21 저녁 / 22-04 밤(자정 넘어가는 구간 포함).
_TIME_OF_DAY_LABELS: tuple[tuple[range, str], ...] = (
    (range(5, 11), "아침"),
    (range(11, 17), "낮"),
    (range(17, 22), "저녁"),
)
_TIME_OF_DAY_DEFAULT_LABEL = "밤"  # 22-23시, 0-4시


def _time_of_day_label(client_local_hour: int) -> str:
    """0-23시를 아침/낮/저녁/밤 중 하나로 분류한다 (C4, 재사용 가능)."""
    for hour_range, label in _TIME_OF_DAY_LABELS:
        if client_local_hour in hour_range:
            return label
    return _TIME_OF_DAY_DEFAULT_LABEL


def build_time_context(client_local_hour: Optional[int]) -> str:
    """client_local_hour를 시간대 인지 프롬프트 문구로 변환한다 (C4).

    build_system_prompt의 동적 꼬리 파라미터(time_context)로 그대로
    전달하도록 설계됨 — 정적 프리픽스에는 영향 없음. hour가 None이면
    빈 문자열을 반환해 기존 동작과 동일하게 시간 블록 자체가 프롬프트에
    삽입되지 않는다.
    """
    if client_local_hour is None:
        return ""
    label = _time_of_day_label(client_local_hour)
    return f"[현재 시간대: {label}이다. 자연스럽게 반영하되 매번 언급하지는 마라.]"


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


async def _prepare_chat_turn(req: ChatRequest, user: Optional[dict]) -> dict:
    """턴 시작 준비: room_id 해석, 스토리 상태 bump, 콜백/스토리 기억 병합.

    generate_reply(논스트림)와 stream_reply(스트림)가 공유하는 전처리.
    P2: bump_turn_and_get_state는 동기 psycopg 호출(story_state_store.py)이라
    핫패스(매 턴)에서 이벤트 루프를 블로킹한다 — asyncio.to_thread로 감싼다
    (함수 자체는 시그니처 변경 없이 유지, 호출부만 감쌈).
    """
    room_id = _resolve_room_id(req, user)
    character_id = req.character_id or ""

    state = await asyncio.to_thread(bump_turn_and_get_state, room_id, character_id)
    effective_character_id = character_id or state.character_id
    callback_key, callback_hint = maybe_build_callback_hint(state)
    story_memories = build_story_memory_items(state, callback_hint or "")
    merged_memories = _merge_memories(req.memories or [], story_memories)
    return {
        "room_id": room_id,
        "state": state,
        "effective_character_id": effective_character_id,
        "callback_key": callback_key,
        "merged_memories": merged_memories,
    }


async def _record_affinity_level_up(
    *,
    event_type: str,
    room_id: str,
    from_level: int,
    to_level: int,
    turn_count: int,
    character_id: str,
    user_id: str,
) -> None:
    """affinity_level_up 이벤트를 fire-and-forget으로 기록한다.

    _finalize_chat_turn 전용(잔여 본문 분할, S15). 원래 중첩 함수였으며
    room_id/event_type(AFFINITY_LEVEL_UP)은 클로저로 캡처하던 값을
    명시적 파라미터로 전환했다. record_event_async는 반드시 모듈 전역
    이름으로 호출해야 tests/test_chat_turn_events_user_id.py의 monkeypatch가
    적용된다(P2: record_event → record_event_async로 전환).
    """
    try:
        await record_event_async(
            event_type=event_type,
            room_id=room_id,
            character_id=character_id,
            user_id=user_id,
            payload={
                "from_level": from_level,
                "to_level": to_level,
                "turn_count": turn_count,
                "character_id": character_id,
            },
        )
    except Exception as _e:
        logger.warning("affinity_level_up 이벤트 기록 실패: %s", _e)


async def _persist_chat_data(
    uid: str,
    character_mbti: str,
    user_message: str,
    assistant_text: str,
) -> None:
    """scheduler D+3/D+5 리텐션 알림을 위해 users/messages 테이블에 데이터 적재.

    _finalize_chat_turn 전용(잔여 본문 분할, S15). 원래도 필요한 값을 모두
    파라미터로 받고 있어 클로저 캡처가 없었다(그대로 모듈 레벨로 승격).
    fire-and-forget: DB 미연결 환경에서도 메인 응답을 블로킹하지 않는다.

    P8: users upsert + 메시지 INSERT(최대 2건)를 각각 별도로 풀에서 커넥션을
    획득하던 것(왕복 최대 3회)을 AsyncDatabase.execute_sequence로 교체해
    커넥션 1회 획득으로 순차 실행한다. 트랜잭션으로 묶지 않으므로(문장별
    개별 commit/rollback) 기존과 동일하게 한 문장이 실패해도 나머지 문장은
    독립적으로 실행되고, 실패 로그도 문장별로 그대로 남는다.
    """
    if not uid:
        return
    db = get_async_db()
    if not db.available:
        return

    # 문장과 로그 라벨을 같은 순서로 구성 — user_message/assistant_text가
    # 비어있으면 기존과 동일하게 해당 문장 자체를 실행하지 않는다(로그도 없음).
    statements: list[tuple[str, tuple]] = [
        (
            # users upsert: 최초 가입 시 created_at 기록, 이후엔 last_active_at만 갱신
            """
            INSERT INTO users (user_id, created_at, last_active_at)
            VALUES ($1, NOW(), NOW())
            ON CONFLICT (user_id)
            DO UPDATE SET last_active_at = NOW()
            """,
            (uid,),
        ),
    ]
    labels = ["users upsert"]

    if user_message:
        statements.append((
            """
            INSERT INTO messages (user_id, character_mbti, role, content)
            VALUES ($1, $2, 'user', $3)
            """,
            (uid, character_mbti, user_message[:2000]),
        ))
        labels.append("messages(user) INSERT")

    if assistant_text:
        statements.append((
            """
            INSERT INTO messages (user_id, character_mbti, role, content)
            VALUES ($1, $2, 'assistant', $3)
            """,
            (uid, character_mbti, assistant_text[:2000]),
        ))
        labels.append("messages(assistant) INSERT")

    results = await db.execute_sequence(statements)
    for label, result in zip(labels, results):
        if result is not None:
            logger.warning("%s 실패 (uid=%s): %s", label, uid, result)


async def _maybe_generate_night_diary(
    req: ChatRequest,
    room_id: str,
    effective_character_id: str,
    next_hook: str,
    next_goal: str,
    uid: str,
) -> Tuple[bool, str, str]:
    """세션 종료 + 야간 시간대(22-23시/0-4시)면 야간 일기를 생성·저장한다.

    _finalize_chat_turn 전용(잔여 본문 분할, S15). 조건 미충족이거나 이미
    생성돼 있거나 저장에 실패하면 (False, next_hook, next_goal)을 입력값
    그대로 반환한다. 저장에 성공하면 next_hook/next_goal을 일기가 제안한
    값으로 갱신하고 night_diary_generated 이벤트를 기록한다.
    Returns (night_diary_generated, next_hook, next_goal).
    """
    night_diary_generated = False
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
                await record_event_async(
                    event_type="night_diary_generated",
                    room_id=room_id,
                    character_id=effective_character_id,
                    user_id=uid,
                    payload={
                        "diary_date": diary_date.isoformat(),
                        "emotion": diary_emotion,
                        "next_hook": diary_next_hook,
                        "next_goal": diary_next_goal,
                    },
                )
    return night_diary_generated, next_hook, next_goal


def _infer_affinity_level_change(affinity_delta: int, old_level: int) -> int:
    """affinity_delta 부호/크기로 새 호감도 레벨을 추정한다.

    _finalize_chat_turn 전용(잔여 본문 분할, S15). 클라이언트가 실제 score를
    갖고 있어 서버는 delta 기반으로만 추정한다(단순 근사, 정밀 계산 아님).
    변동이 없다고 판단되면 old_level을 그대로 반환한다.
    """
    new_level = old_level
    if affinity_delta > 0 and old_level < 5:
        # 다음 레벨 임계값을 넘을 가능성이 있으면 레벨 +1로 간주
        # (정확한 score는 클라이언트 관리이므로 delta 양수 = 가능성 있음)
        next_threshold = AFFINITY_LEVEL_THRESHOLDS.get(old_level + 1, 101)
        # delta가 충분히 크면(임계값 gap의 50% 이상) 레벨 업 추정
        cur_threshold = AFFINITY_LEVEL_THRESHOLDS.get(old_level, 0)
        gap = next_threshold - cur_threshold
        if affinity_delta >= max(1, gap // 2):
            new_level = old_level + 1
    elif affinity_delta < 0 and old_level > 1:
        prev_threshold = AFFINITY_LEVEL_THRESHOLDS.get(old_level, 0)
        if abs(affinity_delta) >= max(1, prev_threshold // 4):
            new_level = old_level - 1
    return new_level


async def _finalize_chat_turn(
    req: ChatRequest,
    user: Optional[dict],
    *,
    room_id: str,
    state,
    effective_character_id: str,
    callback_key,
    replies: list,
    affinity_delta: int,
) -> dict:
    """응답 생성 이후 후처리: 콜백 마킹, 야간 일기, hook/goal, 이벤트, 영속화.

    논스트림/스트림 두 경로가 동일하게 호출한다.
    """
    # P0-1: 이 턴에서 기록하는 모든 metric_events에 user_id를 채운다.
    # (라이브 chat_turn 이벤트에 user_id가 비어 있던 결함 수정 — 검증관 실측 기반)
    _uid = (user or {}).get("uid", "") if user else ""

    # P2: story_state_store의 동기 psycopg 호출을 asyncio.to_thread로 감싼다
    # (함수 시그니처/모듈 바인딩은 그대로 유지 — monkeypatch 호환).
    if callback_key:
        await asyncio.to_thread(mark_callback_used, room_id, callback_key, state.turn_count)

    next_hook = state.next_hook
    next_goal = state.next_goal

    night_diary_generated, next_hook, next_goal = await _maybe_generate_night_diary(
        req, room_id, effective_character_id, next_hook, next_goal, _uid,
    )

    if not next_hook or not next_goal:
        latest = await asyncio.to_thread(get_story_state, room_id, effective_character_id)
        next_hook = next_hook or latest.next_hook
        next_goal = next_goal or latest.next_goal

    # A2: affinity_level_up 이벤트 기록 — 레벨이 변동된 경우에만 fire-and-forget
    if affinity_delta != 0:
        _old_level = req.affinity_level
        # affinity_delta > 0 이면 현재 레벨보다 높아질 수 있고,
        # affinity_delta < 0 이면 낮아질 수 있다 — delta 부호/크기로 추정.
        _new_level = _infer_affinity_level_change(affinity_delta, _old_level)

        if _new_level != _old_level:
            try:
                from ..analytics_events import AFFINITY_LEVEL_UP

                create_tracked_task(
                    _record_affinity_level_up(
                        event_type=AFFINITY_LEVEL_UP,
                        room_id=room_id,
                        from_level=_old_level,
                        to_level=_new_level,
                        turn_count=state.turn_count,
                        character_id=effective_character_id,
                        user_id=_uid,
                    ),
                    name="record-affinity-level-up",
                )
            except Exception as _e:
                logger.warning("affinity_level_up 이벤트 태스크 생성 실패: %s", _e)

    await record_event_async(
        event_type="chat_turn",
        room_id=room_id,
        character_id=effective_character_id,
        user_id=_uid,
        payload={
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z",
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
    # _uid는 함수 상단에서 이미 계산됨 (chat_turn 등 이벤트와 동일 값 재사용)
    _character_mbti = (req.mbti or "").upper()
    _user_message = req.message or ""
    _assistant_text = replies[0].text if replies else ""

    try:
        create_tracked_task(
            _persist_chat_data(_uid, _character_mbti, _user_message, _assistant_text),
            name="persist-chat-data",
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


async def _run_chat_pipeline(
    req: ChatRequest,
    user: Optional[dict],
    crisis_tier: int = 0,
    crisis_hint: str = "",
    request_start_ts: Optional[float] = None,
    gate_ms: float = 0.0,
) -> dict:
    """논스트림 경로: 준비 → 전체 응답 생성 → 후처리.

    crisis_tier/crisis_hint(2026-08-03 P0-S3): 위기 감지 결과를 생성 경로까지
    전달한다. 이전에는 select_model_for_crisis 결과가 로그·이벤트 payload에만
    쓰이고 generate_reply에 넘어가지 않아 Tier1 턴도 mini로 처리될 수 있었고,
    위기 대응 지침은 도달 불가한 LoRA 경로에만 붙어 사실상 미적용이었다.

    request_start_ts/gate_ms(2026-08-03 P1, 회의 항목1): 호출부(send_message/
    stream_message)가 요청 진입 시각(time.monotonic())과 _gate_user 소요를
    측정해 넘겨주면 generate_reply가 turn_latency에 t_e2e_total_ms/t_gate_ms를
    함께 남긴다. 기본값(None/0.0)이면 기존 동작과 동일.
    """
    prep = await _prepare_chat_turn(req, user)
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
        character_id=prep["effective_character_id"],
        memories=prep["merged_memories"],
        time_context=build_time_context(req.client_local_hour),
        crisis_tier=crisis_tier,
        crisis_hint=crisis_hint,
        request_start_ts=request_start_ts,
        gate_ms=gate_ms,
        user_role=req.user_role,
        situation=req.situation,
    )
    return await _finalize_chat_turn(
        req,
        user,
        room_id=prep["room_id"],
        state=prep["state"],
        effective_character_id=prep["effective_character_id"],
        callback_key=prep["callback_key"],
        replies=replies,
        affinity_delta=affinity_delta,
    )


async def _gate_user(req: ChatRequest, user: Optional[dict], request: Request):
    """일일 토큰 예산 및 구독 한도 게이팅 공통 처리.

    P3: check_daily_budget/check_message_limit 두 DB 조회를 asyncio.gather로
    동시 실행해 직렬 대기 시간을 없앤다. 기존 코드는 순차 실행이라 daily_budget이
    실패하면 message_limit은 아예 평가되지 않아 429가 항상 402보다 우선했다 —
    그 우선순위를 유지하기 위해 gather로 두 결과를 모두 받은 뒤에도 반드시
    budget(429)을 먼저 검사하고, budget이 통과했을 때만 message_limit(402)을
    검사한다(두 검사 모두 실패해도 429만 raise). room_id_for_check는 부수효과
    없는 순수 계산이라 미리 구해도 안전하다.
    """
    if not user:
        return
    uid = user.get("uid", "")
    if not uid:
        return

    sub_mgr = get_subscription_manager()
    room_id_for_check = _resolve_room_id(req, user)

    (is_within, _used), (is_allowed, _limit_reason) = await asyncio.gather(
        get_async_db().check_daily_budget(uid, DAILY_TOKEN_LIMIT),
        sub_mgr.check_message_limit(uid, room_id_for_check),
    )

    if not is_within:
        raise HTTPException(
            status_code=429,
            detail=f"일일 사용량 한도({DAILY_TOKEN_LIMIT:,} 토큰)에 도달했습니다. 내일 다시 이용해주세요.",
        )

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
    # P1(2026-08-03, 회의 항목1): 요청 진입 시각 — turn_latency의 t_e2e_total_ms/
    # t_gate_ms 계측 기준점. 콘텐츠 필터보다도 먼저 캡처해야 진짜 "요청 진입"이 된다.
    _req_t0 = time.monotonic()

    # H-1: 콘텐츠 필터
    is_safe, reason = check_content(req.message)
    if not is_safe:
        raise HTTPException(status_code=400, detail=reason)

    await _gate_user(req, user, request)
    _t_gate_ms = (time.monotonic() - _req_t0) * 1000

    # W1-1: 위기 개입 키워드 감지 v2 — 맥락 인식, 관용 표현 필터 강화
    is_crisis, crisis_tier = detect_crisis_v2(
        req.message,
        [m.model_dump() for m in req.conversation_history] if req.conversation_history else None,
    )

    # 하이브리드 GPT 라우팅: 위기 수준에 따라 모델 동적 선택
    crisis_result = {"level": crisis_tier if is_crisis else "none"}
    selected_model = select_model_for_crisis(crisis_result)
    logger.info(f"[ModelRouting] crisis_level={crisis_result['level']}, model={selected_model}")

    # 위기 유형 분류 → 시스템 프롬프트 추가 지침 (P0-S3: 논스트림 경로에도 생성·전달)
    crisis_type_hint = _build_crisis_hint(req.message, req.mbti, is_crisis, crisis_tier)
    _effective_tier = crisis_tier if is_crisis else 0

    result = await _run_chat_pipeline(
        req, user, crisis_tier=_effective_tier, crisis_hint=crisis_type_hint,
        request_start_ts=_req_t0, gate_ms=_t_gate_ms,
    )

    replies = result["replies"]
    if is_crisis:
        # 세션당 1회 제한: 히스토리에 이미 전문가 권유 문구가 있으면 삽입 생략
        if not _crisis_referral_already_shown(req.conversation_history):
            crisis_msg = get_crisis_response(crisis_tier)
            crisis_reply = ReplyPart(text=crisis_msg, emotion="SAD", delay=0)
            replies = [crisis_reply] + list(replies)
        await record_event_async(
            event_type="crisis_detected",
            room_id=result["room_id"],
            character_id=req.character_id,
            user_id=(user or {}).get("uid", "") if user else "",
            payload={"tier": crisis_tier, "model": selected_model},
        )

    return ChatResponse(
        replies=replies,
        affinity_delta=result["affinity_delta"],
        night_diary_generated=result["night_diary_generated"],
        next_hook=result["next_hook"],
        next_goal=result["next_goal"],
    )


def _build_crisis_hint(message: str, mbti: str, is_crisis: bool, crisis_tier: int) -> str:
    """위기 유형을 분류해 시스템 프롬프트에 덧붙일 추가 지침 문자열을 만든다.

    stream_message 전용(잔여 본문 분할, S16). is_crisis가 False이거나
    crisis_tier<=0이면 빈 문자열을 반환한다(기존 동작과 동일).
    """
    crisis_type_hint: str = ""
    if is_crisis and crisis_tier > 0:
        crisis_type = classify_crisis_type(message)
        logger.info(f"[CrisisType] tier={crisis_tier}, type={crisis_type}")
        if crisis_type == "self_criticism":
            _mbti_key = (mbti or "").upper()
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
    return crisis_type_hint


async def _lora_event_generator(
    req: ChatRequest,
    crisis_type_hint: str,
    lora_model_id: str,
    lora_base_url: str,
    replies: list,
    result: dict,
    message_event,
    done_event,
):
    """LoRA 서빙 경로 SSE 제너레이터: 전체 파이프라인으로 확보한 replies/메타를
    바탕으로 토큰 단위 스트리밍하고, 실패 시 기존 replies로 폴백한다.

    stream_message 전용(잔여 본문 분할, S16). 원래 중첩 함수였으며
    req/crisis_type_hint/lora_model_id(_lora_model_id)/lora_base_url(_lora_base_url)/
    replies/result/message_event(_message_event)/done_event(_done_event)는
    전부 클로저로 캡처하던 값을 명시적 파라미터로 전환했다. SSE 이벤트
    이름("token"/"message"/"done")·data JSON 구조·yield 순서는 원본과 동일.
    """
    from ..prompts import build_system_prompt as _build_sys
    sys_prompt = _build_sys(
        mbti=req.mbti or "",
        speech_style=req.speech_style or "",
        relationship=req.relationship or "",
        nickname=req.nickname or "",
        affinity_level=req.affinity_level or 0,
        user_mbti=req.user_mbti or "",
        character_name=req.character_name or "",
        user_role=req.user_role,
        situation=req.situation,
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
        async for token in stream_lora_response(lora_messages, lora_model_id, lora_base_url):
            yield {
                "event": "token",
                "data": json.dumps({"content": token}, ensure_ascii=False),
            }
    except Exception as _lora_err:
        logger.warning(f"[LoRA] 스트리밍 실패, 기존 replies 사용: {_lora_err}")
        for reply in replies:
            yield message_event(reply)
    yield done_event(result)


async def _openai_event_generator(
    req: ChatRequest,
    user: Optional[dict],
    crisis_reply,
    record_crisis,
    message_event,
    done_event,
    crisis_tier: int = 0,
    crisis_hint: str = "",
    request_start_ts: Optional[float] = None,
    gate_ms: float = 0.0,
):
    """OpenAI 경로 SSE 제너레이터: 말풍선이 완결되는 즉시 전송해 TTFB를 단축한다.

    stream_message 전용(잔여 본문 분할, S16). req/user/crisis_reply(_crisis_reply)/
    record_crisis(_record_crisis)/message_event(_message_event)/
    done_event(_done_event)는 클로저로 캡처하던 값을 명시적 파라미터로
    전환했다. SSE 이벤트 이름("message"/"done")·data JSON 구조·예외 시
    폴백 이벤트·yield 순서는 원본과 동일.

    crisis_tier/crisis_hint(2026-08-03 P0-S3): 위기 감지 결과를 stream_reply로
    전달해 모델 승격 + 위기 지침 주입이 실제로 적용되게 한다.

    request_start_ts/gate_ms(2026-08-03 P1, 회의 항목1): stream_message가
    측정한 요청 진입 시각/게이트 소요를 stream_reply까지 전달해
    turn_latency에 t_e2e_first_bubble_ms/t_gate_ms를 남긴다.
    """
    prep = await _prepare_chat_turn(req, user)
    room_id = prep["room_id"]
    await record_crisis(room_id)

    # 위기 문구를 가장 먼저 전송 (persistence/finalize 대상에는 미포함 — 기존 동작 유지)
    if crisis_reply is not None:
        yield message_event(crisis_reply)

    collected = []
    affinity_delta = 0
    try:
        async for item in stream_reply(
            message=req.message,
            mbti=req.mbti,
            speech_style=req.speech_style,
            relationship=req.relationship,
            nickname=req.nickname,
            affinity_level=req.affinity_level,
            conversation_history=req.conversation_history,
            user_mbti=req.user_mbti,
            character_name=req.character_name,
            character_id=prep["effective_character_id"],
            memories=prep["merged_memories"],
            room_id=room_id,
            time_context=build_time_context(req.client_local_hour),
            crisis_tier=crisis_tier,
            crisis_hint=crisis_hint,
            request_start_ts=request_start_ts,
            gate_ms=gate_ms,
            user_role=req.user_role,
            situation=req.situation,
        ):
            if isinstance(item, StreamDone):
                affinity_delta = item.affinity_delta
            else:
                collected.append(item)
                yield message_event(item)
    except Exception as _stream_err:
        logger.error(f"[stream] OpenAI 스트리밍 실패: {_stream_err}")
        if not collected:
            _fb = ReplyPart(text="앗, 잠깐 멍해졌어요... 다시 말해줄래요?", emotion="SURPRISED", delay=2000)
            collected.append(_fb)
            yield message_event(_fb)

    meta = await _finalize_chat_turn(
        req,
        user,
        room_id=room_id,
        state=prep["state"],
        effective_character_id=prep["effective_character_id"],
        callback_key=prep["callback_key"],
        replies=collected,
        affinity_delta=affinity_delta,
    )
    yield done_event(meta)


@router.post("/chat/stream")
@limiter.limit("30/minute")
async def stream_message(
    request: Request,
    req: ChatRequest,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """SSE 스트리밍 방식 - 메시지를 실시간으로 분할 전송"""
    # P1(2026-08-03, 회의 항목1): 요청 진입 시각 — turn_latency의
    # t_e2e_first_bubble_ms/t_gate_ms 계측 기준점.
    _req_t0 = time.monotonic()

    # H-1: 콘텐츠 필터
    is_safe, reason = check_content(req.message)
    if not is_safe:
        raise HTTPException(status_code=400, detail=reason)

    await _gate_user(req, user, request)
    _t_gate_ms = (time.monotonic() - _req_t0) * 1000

    # W1-1: 위기 개입 감지 v2 — 맥락 인식, 관용 표현 필터 강화
    is_crisis, crisis_tier = detect_crisis_v2(
        req.message,
        [m.model_dump() for m in req.conversation_history] if req.conversation_history else None,
    )

    # 하이브리드 GPT 라우팅: 위기 수준에 따라 모델 동적 선택
    crisis_result = {"level": crisis_tier if is_crisis else "none"}
    selected_model = select_model_for_crisis(crisis_result)
    logger.info(f"[ModelRouting] crisis_level={crisis_result['level']}, model={selected_model}")

    # 위기 유형 분류 및 시스템 프롬프트 추가 지침 생성 (공유 헬퍼, S16)
    crisis_type_hint = _build_crisis_hint(req.message, req.mbti, is_crisis, crisis_tier)
    _effective_tier = crisis_tier if is_crisis else 0

    # 위기 개입 문구: 세션당 1회 (히스토리에 이미 권유 문구 있으면 생략)
    _insert_crisis = is_crisis and not _crisis_referral_already_shown(req.conversation_history)
    _crisis_reply = None
    if _insert_crisis:
        _crisis_reply = ReplyPart(text=get_crisis_response(crisis_tier), emotion="SAD", delay=0)

    def _message_event(part) -> dict:
        return {
            "event": "message",
            "data": json.dumps(
                {"text": part.text, "emotion": part.emotion, "delay": part.delay},
                ensure_ascii=False,
            ),
        }

    def _done_event(meta: dict) -> dict:
        return {
            "event": "done",
            "data": json.dumps(
                {
                    "affinity_delta": meta["affinity_delta"],
                    "night_diary_generated": meta["night_diary_generated"],
                    "next_hook": meta["next_hook"],
                    "next_goal": meta["next_goal"],
                    "room_id": meta["room_id"],
                },
                ensure_ascii=False,
            ),
        }

    async def _record_crisis(room_id: str) -> None:
        if is_crisis:
            await record_event_async(
                event_type="crisis_detected",
                room_id=room_id,
                character_id=req.character_id,
                user_id=(user or {}).get("uid", "") if user else "",
                payload={
                    "tier": crisis_tier,
                    "model": selected_model,
                    "crisis_type_hint": crisis_type_hint[:50] if crisis_type_hint else "",
                },
            )

    # LoRA 스트리밍 분기: base_url이 있으면 vLLM/Together AI LoRA 토큰 스트리밍 사용
    _ab_variant = getattr(req, "ab_variant", "") or ""
    _lora_model_id, _lora_base_url = await resolve_model_endpoint(selected_model, _ab_variant)
    _use_lora_stream = bool(_lora_base_url and TOGETHER_API_KEY)

    if _use_lora_stream:
        # LoRA 경로: 전체 파이프라인으로 replies/메타 확보 후 토큰 스트리밍 (기존 동작 유지)
        # 폴백 replies도 위기 인지 상태로 생성되도록 crisis 정보를 함께 전달한다.
        result = await _run_chat_pipeline(
            req, user, crisis_tier=_effective_tier, crisis_hint=crisis_type_hint,
            request_start_ts=_req_t0, gate_ms=_t_gate_ms,
        )
        replies = list(result["replies"])
        if _crisis_reply is not None:
            replies = [_crisis_reply] + replies
        await _record_crisis(result["room_id"])

        return EventSourceResponse(_lora_event_generator(
            req, crisis_type_hint, _lora_model_id, _lora_base_url, replies, result,
            _message_event, _done_event,
        ))

    # OpenAI 경로: 말풍선 점진 스트리밍 (완결되는 즉시 전송해 TTFB 단축)
    return EventSourceResponse(_openai_event_generator(
        req, user, _crisis_reply, _record_crisis, _message_event, _done_event,
        crisis_tier=_effective_tier, crisis_hint=crisis_type_hint,
        request_start_ts=_req_t0, gate_ms=_t_gate_ms,
    ))


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
            timeout=20,
        )
        content = resp.choices[0].message.content.strip()
        starters = json.loads(content)
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
    await db.execute(
        """
        INSERT INTO metric_events (event_type, room_id, character_id, payload)
        VALUES ('conversation_starter_used', $1, $2, $3::jsonb)
        """,
        req.room_id,
        req.character_id,
        json.dumps({"starter_text": req.starter_text[:100]}),
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
    mbti_upper = character_mbti.upper()
    prompt = _MBTI_GREETING_PROMPTS.get(
        mbti_upper,
        f"{mbti_upper} 성격의 AI 친구로서 따뜻한 첫 인사를 해주세요. 50자 이내.",
    )
    # C2: 첫인사에 감정 부여 — MBTI 고정 매핑(get_greeting_emotion, app/mbti.py).
    # additive 필드: 기존 greeting/character_mbti 필드는 그대로 유지한다.
    greeting_emotion = get_greeting_emotion(mbti_upper)

    if not OPENAI_API_KEY:
        # API 키 없으면 기본 인사 반환
        return {
            "greeting": f"안녕! 나는 {mbti_upper} 성격의 AI야. 잘 부탁해!",
            "character_mbti": mbti_upper,
            "emotion": greeting_emotion,
        }

    try:
        _client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
        resp = await _client.chat.completions.create(
            model=LLM_MODEL_SIMPLE,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.9,
            timeout=20,
        )
        greeting_text = resp.choices[0].message.content.strip()
    except Exception as exc:
        logger.warning("[Greeting] LLM 호출 실패, 기본 인사 사용: %s", exc)
        greeting_text = f"안녕! 나는 {mbti_upper} 성격의 AI야. 잘 부탁해!"

    return {"greeting": greeting_text, "character_mbti": mbti_upper, "emotion": greeting_emotion}
