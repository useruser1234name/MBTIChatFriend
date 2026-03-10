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
