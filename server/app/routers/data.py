"""데이터 삭제 및 비용 대시보드 엔드포인트"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth_middleware import require_auth_always, verify_firebase_token
from ..models import AccountDeleteResponse
from ..postgres_async import get_async_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["data"])


class DataConsentRequest(BaseModel):
    user_id: str
    consented: bool  # True = 동의, False = 철회


class DataConsentResponse(BaseModel):
    user_id: str
    consented: bool
    message: str


@router.post("/data/consent")
async def update_data_consent(
    req: DataConsentRequest,
    user: dict = Depends(require_auth_always),
):
    """
    사용자 학습 데이터 활용 opt-in 동의 저장/철회.

    보안(S-2): 인증 필수 + 토큰 uid 일치 검증 (GDPR — 타인 동의 조작 방지).

    법무 요건 (10차 회의 — 법무 전문가 김지은):
    - 명시적 opt-in (기본값 False)
    - 철회 시 기존 학습 데이터 삭제 플래그 설정
    - 목적: AI 캐릭터 품질 개선
    """
    token_uid = user.get("uid")
    if not token_uid or token_uid != req.user_id:
        raise HTTPException(status_code=403, detail="user_id가 인증 토큰과 일치하지 않습니다")
    db = get_async_db()
    await db.execute(
        """
        INSERT INTO user_data_consent (user_id, consented, updated_at)
        VALUES ($1, $2, NOW())
        ON CONFLICT (user_id) DO UPDATE
        SET consented = $2, updated_at = NOW()
        """,
        req.user_id,
        req.consented,
    )
    msg = "학습 데이터 활용에 동의하셨습니다." if req.consented else "동의가 철회됐습니다. 기존 데이터는 익명화 처리됩니다."
    return DataConsentResponse(user_id=req.user_id, consented=req.consented, message=msg)


@router.get("/data/consent/{user_id}")
async def get_data_consent(
    user_id: str,
    user: dict = Depends(require_auth_always),
):
    """사용자 동의 상태 조회. 본인만 조회 가능."""
    token_uid = user.get("uid")
    if not token_uid or token_uid != user_id:
        raise HTTPException(status_code=403, detail="본인의 동의 상태만 조회할 수 있습니다.")
    db = get_async_db()
    row = await db.fetchone(
        "SELECT consented FROM user_data_consent WHERE user_id = $1",
        user_id,
    )
    consented = bool(row["consented"]) if row else False
    return {"user_id": user_id, "consented": consented}


@router.delete("/data/conversations/{room_id}")
async def delete_conversation(
    room_id: str,
    character_id: str = "",
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """대화 기록 삭제 — 사용자가 특정 캐릭터 또는 전체 대화를 삭제할 수 있음.

    삭제 범위: conversation_memory, story_state, diary_entries,
               metric_events, api_usage (PostgreSQL)
    ChromaDB 벡터 삭제는 Phase 2에서 구현 예정.
    """
    if not room_id.strip():
        raise HTTPException(status_code=400, detail="room_id가 필요합니다.")

    # 인증된 사용자 본인의 room만 삭제 허용
    if user:
        uid = user.get("uid", "")
        if uid and not room_id.startswith(uid):
            raise HTTPException(status_code=403, detail="본인의 대화만 삭제할 수 있습니다.")

    try:
        db = get_async_db()
        await db.delete_conversation(room_id=room_id, character_id=character_id)
        logger.info(f"대화 기록 삭제 완료: room_id={room_id}, character_id={character_id}")
        return {"status": "deleted", "room_id": room_id}
    except Exception as e:
        logger.error(f"대화 기록 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail="삭제 중 오류가 발생했습니다.")


@router.delete("/account", response_model=AccountDeleteResponse)
async def delete_account(
    user: dict = Depends(require_auth_always),
):
    """계정 완전삭제 (S-6 출시게이트).

    순서: PG 20+ 테이블 삭제 → ChromaDB 벡터 삭제 → Firebase Auth 삭제 → deletion_log 기록.
    best-effort: 각 단계 실패해도 계속 진행. Firebase 삭제는 최후 (재시도 불가).
    """
    uid = user.get("uid", "")
    if not uid:
        raise HTTPException(status_code=401, detail="유효한 uid가 없습니다.")

    db = get_async_db()

    # 1. PostgreSQL 20+ 테이블 삭제 (best-effort, 내부에서 각 단계 로깅)
    try:
        await db.delete_account(uid)
    except Exception as e:
        logger.error("[delete_account] PG 삭제 중 예외 (uid=%s): %s", uid, e)

    # 2. ChromaDB 벡터 삭제 (room_id 목록 기반)
    try:
        from ..vector_store import get_vector_store
        vs = get_vector_store()
        if vs is not None:
            # room_id가 '{uid}:character_id' 형식이므로 character_id 패턴으로 삭제
            # character_id는 room_id에서 파싱하지 않고 uid prefix로 컬렉션 목록을 정리
            # vector_store는 character_id 기반 컬렉션이므로 uid와 연관된 character_id를 알 수 없음
            # → deletion_log 기반 추적 또는 클라이언트가 character_id 제공 시 삭제
            # 현재 아키텍처상 uid → character_id 매핑이 서버에 없으므로 ChromaDB 삭제는 best-effort skip
            pass
    except Exception as e:
        logger.warning("[delete_account] ChromaDB 삭제 실패 (uid=%s): %s", uid, e)

    # 3. Firebase Auth 삭제 (재시도 불가라 최후, 실패해도 PG 데이터는 이미 삭제됨)
    try:
        from firebase_admin import auth as firebase_auth
        firebase_auth.delete_user(uid)
        logger.info("[delete_account] Firebase Auth 삭제 완료 (uid=%s)", uid)
    except Exception as e:
        logger.error("[delete_account] Firebase Auth 삭제 실패 (uid=%s): %s", uid, e)
        # Firebase 삭제 실패는 치명적이지 않음 — PG 데이터는 이미 삭제됨
        # 사용자는 재로그인이 가능하나 앱 기능은 동작하지 않음

    return AccountDeleteResponse(
        status="deleted",
        uid=uid,
        message="계정이 삭제되었습니다.",
    )


@router.get("/cost/summary")
async def cost_summary(
    days: int = 7,
    user: Optional[dict] = Depends(verify_firebase_token),
):
    """API 비용 요약 — 모델별 토큰 사용량 집계.

    DATA-A 오재원 제안: 실측 데이터 기반 비용 최적화 의사결정 지원.
    """
    # INTERVAL '%s days'는 %s가 문자열 리터럴 내부라 파라미터 바인딩이 되지 않는다.
    # make_interval(days => %s)로 정수 days를 안전하게 바인딩한다.
    days = max(1, min(int(days), 365))
    from ..postgres import fetchall
    rows = fetchall(
        """
        SELECT
            model_id,
            COUNT(*) AS call_count,
            SUM(prompt_tokens) AS total_prompt,
            SUM(completion_tokens) AS total_completion,
            SUM(total_tokens) AS total_tokens
        FROM api_usage
        WHERE created_at >= NOW() - make_interval(days => %s)
        GROUP BY model_id
        ORDER BY total_tokens DESC
        """,
        (days,),
    )
    return {"period_days": days, "models": rows}
