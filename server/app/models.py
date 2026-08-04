from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Dict, List, Literal, Optional

from .config import MAX_CONVERSATION_HISTORY, MAX_MESSAGE_LENGTH

_VALID_MBTI_TYPES = {
    "INTJ", "INTP", "ENTJ", "ENTP",
    "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ",
    "ISTP", "ISFP", "ESTP", "ESFP",
}


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"] = "user"
    content: str = Field(default="", max_length=MAX_MESSAGE_LENGTH)


class MemoryItem(BaseModel):
    key: str
    value: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LENGTH)
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
    conversation_history: List[HistoryMessage] = Field(default_factory=list, max_length=MAX_CONVERSATION_HISTORY)
    user_mbti: Optional[str] = Field(default=None, pattern=r"^[A-Z]{4}$")
    character_name: str = Field(default="")
    character_id: str = Field(default="")
    persona_raw: str = Field(default="", max_length=2000)
    persona_summary: str = Field(default="", max_length=2000)
    dialogue_prompt: str = Field(default="", max_length=4000)
    visual_prompt: str = Field(default="", max_length=4000)
    room_id: str = Field(default="", max_length=120)
    end_of_session: bool = False
    client_local_hour: Optional[int] = Field(default=None, ge=0, le=23)
    memories: List[MemoryItem] = Field(default_factory=list)
    mood: Optional[str] = Field(default=None, description="사용자 오늘 기분 (좋아/슬퍼/화남/고민/피곤/설렘)")
    # M2(2026-08-03 회의): 웹 MVP에서 검증된 [Scene] 이식. JSON 키 이름은
    # Android 계약이므로 정확히 user_role / situation 을 유지해야 한다.
    user_role: str = Field(
        default="", max_length=200,
        description="캐릭터 입장에서 본 사용자의 역할 (예: 어릴 적부터 함께 자란 소꿉친구)",
    )
    situation: str = Field(
        default="", max_length=200,
        description="현재 장면/배경 (예: 눈 내리는 겨울 저녁, 대공의 서재에서 단둘이)",
    )

    @field_validator("user_role", "situation")
    @classmethod
    def sanitize_scene(cls, v: str) -> str:
        """장면 입력 새니타이즈 — message와 동일한 태그 이스케이프 + 개행 제거.

        개행을 남기면 프롬프트 안에 가짜 섹션 헤더를 심을 수 있으므로
        모든 공백 런을 단일 공백으로 접는다(prompts._sanitize_scene_value와 동일).
        max_length는 이 검증보다 먼저 평가되므로 200자 초과는 그대로 422다.
        """
        if not v:
            return ""
        v = v.replace("<", "&lt;").replace(">", "&gt;")
        return " ".join(v.split())

    @field_validator("message")
    @classmethod
    def sanitize_message(cls, v: str) -> str:
        v = v.replace("<", "&lt;").replace(">", "&gt;")
        return v.strip()


class ProactiveChatRequest(BaseModel):
    """선톡(캐릭터 선발화) 전용 요청 — 유저 발화가 없는 턴.

    ChatRequest와 필드 구성은 거의 같지만 `message` 대신 `hook`(다음 대화
    흐름 힌트)만 받는다. 유도 문구 자체는 서버가 합성한다
    (routers/chat.build_proactive_message) — 클라이언트가 "[선톡 유도] ..."
    문구를 message로 보내던 기존 방식은 그 문구가 유저 발화로 messages
    테이블/chat_turn 이벤트에 적재돼 세션·리텐션 지표를 오염시켰다.

    ChatRequest를 상속하지 않는 이유: ChatRequest는 message가 필수
    (min_length=1)이고 기존 계약을 그대로 유지해야 하므로, 필요한 필드만
    독립적으로 선언하고 `to_chat_request()`로 내부 변환한다. 제약(패턴,
    길이, MBTI 검증)은 ChatRequest와 동일하게 맞춰 잘못된 입력이 핸들러
    안이 아니라 422로 걸러지게 한다.

    end_of_session/persona_* 계열은 선톡 경로에서 쓰지 않으므로 노출하지
    않는다(내부 ChatRequest에서는 기본값 사용 — 야간 일기 미발동).
    """

    hook: str = Field(default="", max_length=300)
    mbti: str = Field(..., pattern=r"^[A-Z]{4}$")
    speech_style: Literal["FORMAL", "CASUAL", "TSUNDERE", "SWEET"] = "CASUAL"
    relationship: Literal["FRIEND", "LOVER", "SENIOR_JUNIOR"] = "FRIEND"
    nickname: str = Field(..., min_length=1, max_length=20)
    affinity_level: int = Field(default=1, ge=1, le=5)
    conversation_history: List[HistoryMessage] = Field(
        default_factory=list, max_length=MAX_CONVERSATION_HISTORY
    )
    user_mbti: Optional[str] = Field(default=None, pattern=r"^[A-Z]{4}$")
    character_name: str = Field(default="")
    character_id: str = Field(default="")
    room_id: str = Field(default="", max_length=120)
    client_local_hour: Optional[int] = Field(default=None, ge=0, le=23)
    memories: List[MemoryItem] = Field(default_factory=list)
    mood: Optional[str] = Field(default=None, description="사용자 오늘 기분")
    user_role: str = Field(default="", max_length=200)
    situation: str = Field(default="", max_length=200)

    @field_validator("mbti")
    @classmethod
    def validate_mbti(cls, v: str) -> str:
        if v not in _VALID_MBTI_TYPES:
            raise ValueError(f"유효하지 않은 MBTI 타입: {v}")
        return v

    @field_validator("hook", "user_role", "situation")
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        """ChatRequest.sanitize_scene과 동일 규칙 — 태그 이스케이프 + 공백 접기.

        hook은 서버 합성 프롬프트에 그대로 삽입되므로 개행을 남기면 가짜
        섹션 헤더를 심을 수 있다.
        """
        if not v:
            return ""
        v = v.replace("<", "&lt;").replace(">", "&gt;")
        return " ".join(v.split())

    def to_chat_request(self, message: str) -> "ChatRequest":
        """합성된 유도 문구를 message로 갖는 내부 ChatRequest를 만든다.

        기존 스트림 파이프라인(_prepare_chat_turn / stream_reply /
        _finalize_chat_turn)은 전부 ChatRequest를 받으므로, 분기를 늘리는
        대신 경계에서 한 번만 변환해 파이프라인을 그대로 재사용한다.
        """
        return ChatRequest(
            message=message,
            mbti=self.mbti,
            speech_style=self.speech_style,
            relationship=self.relationship,
            nickname=self.nickname,
            affinity_level=self.affinity_level,
            conversation_history=self.conversation_history,
            user_mbti=self.user_mbti,
            character_name=self.character_name,
            character_id=self.character_id,
            room_id=self.room_id,
            client_local_hour=self.client_local_hour,
            memories=self.memories,
            mood=self.mood,
            user_role=self.user_role,
            situation=self.situation,
        )


VALID_EMOTIONS: frozenset = frozenset({
    "NEUTRAL", "HAPPY", "SHY", "SAD", "ANGRY",
    "SURPRISED", "LOVE", "PLAYFUL", "WORRIED", "TOUCHED",
})


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
    conversations: List[Dict[str, str]] = Field(default_factory=list)


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
    size: Literal["256x256", "512x512", "1024x1024", "1792x1024", "1024x1792"] = "1024x1024"
    quality: Literal["standard", "hd"] = "standard"


class ImageGenerateResponse(BaseModel):
    url: str
    revised_prompt: Optional[str] = None


class ImageSetRequest(BaseModel):
    base_prompt: str = Field(..., min_length=1, max_length=4000)
    character_id: str = Field(..., min_length=1)
    size: Literal["256x256", "512x512", "1024x1024"] = "1024x1024"


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
    night_diary_weekly_limit: int = 0    # -1 이면 무제한 (PREMIUM)
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


