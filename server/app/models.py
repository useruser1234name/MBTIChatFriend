from pydantic import BaseModel, Field, field_validator
from typing import List, Optional


class HistoryMessage(BaseModel):
    role: str = "user"
    content: str = ""


class MemoryItem(BaseModel):
    key: str
    value: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    mbti: str = Field(..., pattern=r"^[A-Z]{4}$")
    speech_style: str
    relationship: str
    nickname: str = Field(..., min_length=1, max_length=20)
    affinity_level: int = Field(default=1, ge=1, le=5)
    conversation_history: List[HistoryMessage] = Field(default_factory=list)
    user_mbti: Optional[str] = Field(default=None, pattern=r"^[A-Z]{4}$")
    character_name: str = Field(default="")
    character_id: str = Field(default="")
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
    speech_style: str = "CASUAL"
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
    speech_style: str = "CASUAL"
    relationship: str = "FRIEND"
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
    character_id: str
    model_id: str


class ImageGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    size: str = Field(default="1024x1024")
    quality: str = Field(default="standard")


class ImageGenerateResponse(BaseModel):
    url: str
    revised_prompt: Optional[str] = None
