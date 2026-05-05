import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY", "")
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "")
FIREBASE_STORAGE_BUCKET = os.getenv("FIREBASE_STORAGE_BUCKET", "")
# pgBouncer 전환 시 이 값을 postgresql://user:pass@pgbouncer-host:6432/dbname 으로 교체
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost/mbtichatfriend")

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# CORS 설정 - production에서는 명시적 origin 필요
_cors_raw = os.getenv("CORS_ORIGINS", "")
if _cors_raw:
    CORS_ORIGINS = [o.strip() for o in _cors_raw.split(",") if o.strip()]
elif ENVIRONMENT == "production":
    CORS_ORIGINS = []  # production에서는 반드시 CORS_ORIGINS 설정 필요
else:
    CORS_ORIGINS = ["*"]

# 인증 강제 여부 - 기본값 true (개발 환경에서 비활성화하려면 .env에 REQUIRE_AUTH=false 명시)
REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "true").lower() == "true"

# Input limits
MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", "2000"))
MAX_CONVERSATION_HISTORY = int(os.getenv("MAX_CONVERSATION_HISTORY", "50"))

# DB connection pool
DB_POOL_MIN_SIZE = int(os.getenv("DB_POOL_MIN_SIZE", "5"))
DB_POOL_MAX_SIZE = int(os.getenv("DB_POOL_MAX_SIZE", "20"))

# LLM model settings
LLM_MODEL_COMPLEX = os.getenv("LLM_MODEL_COMPLEX", "gpt-4o")
LLM_MODEL_SIMPLE = os.getenv("LLM_MODEL_SIMPLE", "gpt-4o-mini")
LLM_MODEL_BASE = os.getenv("LLM_MODEL_BASE", "gpt-4o")

# W2-6: 사용자당 일일 토큰 상한 (PM-B 손민준 + ARCH-B 황인호 설계)
# 기본값 50,000 토큰 = GPT-4o-mini 기준 약 1만 단어 교환
DAILY_TOKEN_LIMIT = int(os.getenv("DAILY_TOKEN_LIMIT", "50000"))

# Self-regulation 임계값 — RemoteConfig 동적화 (6차 스프린트 — CTO-B 김태우)
# Firebase RemoteConfig 또는 환경변수로 런타임 제어 가능
SESSION_LIMIT_ADULT_MINUTES = int(os.getenv("SESSION_LIMIT_ADULT_MINUTES", "90"))
SESSION_LIMIT_MINOR_MINUTES = int(os.getenv("SESSION_LIMIT_MINOR_MINUTES", "60"))
SESSION_CONSECUTIVE_DAYS_THRESHOLD = int(os.getenv("SESSION_CONSECUTIVE_DAYS_THRESHOLD", "7"))

MAX_TOKENS = int(os.getenv("MAX_TOKENS", "768"))
