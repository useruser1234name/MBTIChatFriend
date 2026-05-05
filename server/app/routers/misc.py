"""기타 라우터: health, mood_checkin, compatibility, diary"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth_middleware import verify_firebase_token
from ..chat_service import generate_diary, client as _openai_client
from ..config import LLM_MODEL_SIMPLE, MAX_CONVERSATION_HISTORY, MAX_MESSAGE_LENGTH
from ..compatibility import calculate_compatibility
from ..models import (
    ClientConfigResponse,
    CompatibilityRequest,
    CompatibilityResponse,
    DiaryRequest,
    DiaryResponse,
    MoodCheckinRequest,
    MoodCheckinResponse,
)
from ..shared import limiter

logger = logging.getLogger(__name__)
router = APIRouter()

_MOOD_EMOTION_MAP = {
    "좋아": "HAPPY",
    "슬퍼": "SAD",
    "화남": "ANGRY",
    "고민": "WORRIED",
    "피곤": "NEUTRAL",
    "설렘": "SHY",
}


@router.get("/config/client", response_model=ClientConfigResponse)
async def get_client_config():
    """Client-visible server constraints for local validation upper bounds."""
    return ClientConfigResponse(
        max_message_length=MAX_MESSAGE_LENGTH,
        max_conversation_history=MAX_CONVERSATION_HISTORY,
    )


@router.post("/diary/generate", response_model=DiaryResponse)
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


@router.post("/mood/checkin", response_model=MoodCheckinResponse)
@limiter.limit("10/minute")
async def mood_checkin(
    request: Request,
    req: MoodCheckinRequest,
    user=Depends(verify_firebase_token),
):
    """사용자 무드에 캐릭터가 반응하는 짧은 메시지 생성"""
    if not _openai_client:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")

    mbti = req.mbti or "ENFP"
    character_name = req.character_name or "캐릭터"
    nickname = req.nickname or "사용자"
    mood = req.mood or "좋아"

    system_prompt = (
        f"너는 MBTI {mbti} 성격의 '{character_name}'이야. "
        f"'{nickname}'이(가) 지금 기분이 '{mood}'이라고 했어. "
        f"{mbti} 성격답게 짧고 자연스럽게 반응해줘. "
        f"1~2문장, 반말, 이모지 없이. 한국어로 답해."
    )

    try:
        response = await _openai_client.chat.completions.create(
            model=LLM_MODEL_SIMPLE,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"내 기분: {mood}"},
            ],
            temperature=0.8,
            max_tokens=100,
        )
        message = response.choices[0].message.content or "응, 알겠어!"
        emotion = _MOOD_EMOTION_MAP.get(mood, "NEUTRAL")
        return MoodCheckinResponse(message=message.strip(), emotion=emotion)
    except Exception as e:
        logger.error(f"무드 체크인 실패: {e}")
        raise HTTPException(status_code=500, detail="무드 반응 생성에 실패했습니다.")


@router.post("/compatibility/check", response_model=CompatibilityResponse)
@limiter.limit("30/minute")
async def check_compatibility(
    request: Request,
    req: CompatibilityRequest,
    user=Depends(verify_firebase_token),
):
    """MBTI 궁합 조회 (하드코딩 매트릭스 기반, LLM 호출 없음)"""
    user_mbti = req.user_mbti.upper().strip()
    char_mbti = req.character_mbti.upper().strip()

    valid_types = {
        "INTJ", "INTP", "ENTJ", "ENTP",
        "INFJ", "INFP", "ENFJ", "ENFP",
        "ISTJ", "ISFJ", "ESTJ", "ESFJ",
        "ISTP", "ISFP", "ESTP", "ESFP",
    }
    if user_mbti not in valid_types:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 사용자 MBTI: {user_mbti}")
    if char_mbti not in valid_types:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 캐릭터 MBTI: {char_mbti}")

    result = calculate_compatibility(user_mbti, char_mbti)
    return CompatibilityResponse(**result)
