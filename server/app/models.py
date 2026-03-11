from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Dict, List, Literal, Optional

_VALID_MBTI_TYPES = {
    "INTJ", "INTP", "ENTJ", "ENTP",
    "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ",
    "ISTP", "ISFP", "ESTP", "ESFP",
}


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"] = "user"
    content: str = ""


class MemoryItem(BaseModel):
    key: str
    value: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    mbti: str = Field(..., pattern=r"^[A-Z]{4}$")
    speech_style: Literal["FORMAL", "CASUAL", "TSUNDERE", "SWEET"] = "CASUAL"
    relationship: Literal["FRIEND", "LOVER", "SENIOR_JUNIOR"] = "FRIEND"
    nickname: str = Field(..., min_length=1, max_length=20)

    @field_validator("mbti")
    @classmethod
    def validate_mbti(cls, v: str) -> str:
        if v not in _VALID_MBTI_TYPES:
            raise ValueError(f"유효하지 않은 MBTI 타입: {v}")
        return v
    affinity_level: int = Field(default=1, ge=1, le=5)
    conversation_history: List[HistoryMessage] = Field(default_factory=list)
    user_mbti: Optional[str] = Field(default=None, pattern=r"^[A-Z]{4}$")
    character_name: str = Field(default="")
    character_id: str = Field(default="")
    room_id: str = Field(default="", max_length=120)
    end_of_session: bool = False
    client_local_hour: Optional[int] = Field(default=None, ge=0, le=23)
    memories: List[MemoryItem] = Field(default_factory=list)

    @field_validator("message")
    @classmethod
    def sanitize_message(cls, v: str) -> str:
        v = v.replace("<", "&lt;").replace(">", "&gt;")
        return v.strip()


class ReplyPart(BaseModel):
    text: str
    emotion: str = "NEUTRAL"
    delay: int = 500


class ChatResponse(BaseModel):
    replies: List[ReplyPart]
    affinity_delta: int = 0
    night_diary_generated: bool = False
    next_hook: str = ""
    next_goal: str = ""


class FcmTokenRequest(BaseModel):
    token: str = Field(..., min_length=1)
    user_id: str = ""


class FcmSendRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    title: str = Field(default="MBTI Chat Friend")
    body: str = Field(..., min_length=1)
    character_name: str = ""
    character_id: int = 0


class DiaryRequest(BaseModel):
    character_name: str = ""
    mbti: str = Field(..., pattern=r"^[A-Z]{4}$")
    speech_style: Literal["FORMAL", "CASUAL", "TSUNDERE", "SWEET"] = "CASUAL"
    nickname: str = ""
    affinity_level: int = Field(default=1, ge=1, le=5)
    conversation_history: List[HistoryMessage] = Field(default_factory=list)


class DiaryResponse(BaseModel):
    diary: str
    emotion: str = "NEUTRAL"


class MemoryExtractRequest(BaseModel):
    character_name: str = ""
    character_id: str = ""
    nickname: str = ""
    conversation_history: List[HistoryMessage] = Field(default_factory=list)


class MemoryExtractResponse(BaseModel):
    memories: List[MemoryItem]


class FinetuneRequest(BaseModel):
    character_id: str = ""
    character_name: str = ""
    mbti: str = Field(..., pattern=r"^[A-Z]{4}$")
    speech_style: Literal["FORMAL", "CASUAL", "TSUNDERE", "SWEET"] = "CASUAL"
    relationship: Literal["FRIEND", "LOVER", "SENIOR_JUNIOR"] = "FRIEND"
    nickname: str = ""
    affinity_level: int = Field(default=1, ge=1, le=5)
    conversations: List[dict] = Field(default_factory=list)


class FinetuneResponse(BaseModel):
    job_id: str = ""
    status: str
    training_count: int = 0
    model: str = ""
    error: str = ""


class FinetuneStatusResponse(BaseModel):
    job_id: str
    status: str
    fine_tuned_model: str = ""
    error: str = ""


class FinetuneActivateRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    character_id: str
    model_id: str


class ImageGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    size: str = Field(default="1024x1024")
    quality: str = Field(default="standard")


class ImageGenerateResponse(BaseModel):
    url: str
    revised_prompt: Optional[str] = None


class ImageSetRequest(BaseModel):
    base_prompt: str = Field(..., min_length=1, max_length=4000)
    character_id: str = Field(..., min_length=1)
    size: str = Field(default="1024x1024")


class ImageSetResponse(BaseModel):
    status: str  # "processing"
    task_id: str


class ImageSetStatusResponse(BaseModel):
    status: str  # "processing" | "completed" | "failed"
    completed: int = 0
    total: int = 15
    urls: dict = {}


class FeedbackRequest(BaseModel):
    room_id: str = ""
    character_id: str = ""
    message_id: str = Field(..., min_length=1)
    feedback_type: Literal["thumbs_up", "thumbs_down"]
    feedback_detail: str = Field(default="", max_length=200)


class QualityDashboardResponse(BaseModel):
    avg_quality_score: float = 0.0
    avg_mbti_consistency: float = 0.0
    avg_contextual_relevance: float = 0.0
    avg_emotional_naturalness: float = 0.0
    avg_engagement_quality: float = 0.0
    avg_diversity_score: float = 0.0
    total_turns: int = 0
    thumbs_up_count: int = 0
    thumbs_down_count: int = 0
    thumbs_up_rate: float = 0.0
    quality_trend: List[dict] = []


# ── Self-Regulation 모델 (PSY-B 최은혜 + PM-B 손민준, 4차 회의 합의) ──────────


class SessionCheckRequest(BaseModel):
    """세션 사용 시간 및 연속 접속 점검 요청."""

    room_id: str = Field(..., min_length=1, max_length=120)
    user_birth_year: Optional[int] = Field(
        default=None,
        ge=1900,
        le=2100,
        description="사용자 출생 연도 (미성년자 판별용). 미입력 시 성인으로 간주.",
    )


class SessionCheckResponse(BaseModel):
    """세션 사용 시간 + 연속 접속 점검 통합 응답."""

    # 세션 사용 시간
    should_warn: bool = False
    elapsed_minutes: int = 0
    limit_minutes: int = 90
    message: str = ""

    # 연속 접속
    consecutive_days: int = 0
    should_show_reality_nudge: bool = False
    nudge_message: str = ""


# ── 구독 플랜 모델 (CTO-A 박지훈 + ARCH-C 오세진, 5차 스프린트) ────────────────


class SubscriptionStatusResponse(BaseModel):
    """현재 구독 플랜 상태 응답."""

    plan: str = "free"
    daily_messages_used: int = 0
    daily_messages_limit: int = 50       # -1 이면 무제한
    max_characters: int = 1
    max_memories: int = 5
    max_affinity_level: int = 3
    expression_set: bool = False
    night_diary: bool = False
    expires_at: Optional[str] = None     # ISO 8601 문자열 또는 None (영구)


class SubscriptionUpgradeRequest(BaseModel):
    """구독 플랜 업그레이드 요청 (결제 연동 전 mock).

    다음 스프린트에서 실제 결제 payload로 교체 예정.
    """

    user_id: str = Field(..., min_length=1)
    plan: Literal["free", "premium"] = "premium"


# ── 관계 히스토리 & 기억 앨범 모델 (UX-B 안현우 + UI-C 정수아, 5차 회의 합의) ──


class MemoryMomentRequest(BaseModel):
    """기억 앨범 저장 요청."""

    character_id: str = Field(..., min_length=1, max_length=120)
    message_text: str = Field(..., min_length=1, max_length=2000)
    moment_type: Literal["special", "funny", "touching"] = "special"
    user_note: str = Field(default="", max_length=500)


class RelationshipSummaryResponse(BaseModel):
    """관계 히스토리 요약 응답."""

    total_messages: int = 0
    total_sessions: int = 0
    days_together: int = 0
    affinity_journey: List[tuple] = []
    top_topics: List[str] = []
    first_chat_date: str = ""


class MemoryMomentItem(BaseModel):
    """기억 앨범 단일 항목."""

    id: Optional[int] = None
    room_id: str = ""
    character_id: str = ""
    user_id: str = ""
    message_text: str = ""
    moment_type: str = "special"
    user_note: str = ""
    created_at: str = ""
