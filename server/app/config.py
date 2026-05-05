import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "")
FIREBASE_STORAGE_BUCKET = os.getenv("FIREBASE_STORAGE_BUCKET", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# CORS 설정 - production에서는 명시적 origin 필요
_cors_raw = os.getenv("CORS_ORIGINS", "")
if _cors_raw:
    CORS_ORIGINS = [o.strip() for o in _cors_raw.split(",") if o.strip()]
elif ENVIRONMENT == "production":
    CORS_ORIGINS = []  # production에서는 반드시 CORS_ORIGINS 설정 필요
else:
    CORS_ORIGINS = ["*"]

# 인증 강제 여부 - 프로덕션에서는 무조건 활성화
_require_auth_env = os.getenv("REQUIRE_AUTH", "true").lower() == "true"
REQUIRE_AUTH = True if ENVIRONMENT == "production" else _require_auth_env

# 입력 크기 제한
MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", "2000"))
MAX_CONVERSATION_HISTORY = int(os.getenv("MAX_CONVERSATION_HISTORY", "50"))

# DB 커넥션 풀
DB_POOL_MIN_SIZE = int(os.getenv("DB_POOL_MIN_SIZE", "5"))
DB_POOL_MAX_SIZE = int(os.getenv("DB_POOL_MAX_SIZE", "20"))

# 로그 레벨
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# LLM 모델 설정 (계정에 따라 gpt-4.1 / gpt-4o 선택)
LLM_MODEL_COMPLEX = os.getenv("LLM_MODEL_COMPLEX", "gpt-4o")
LLM_MODEL_SIMPLE = os.getenv("LLM_MODEL_SIMPLE", "gpt-4o-mini")
LLM_MODEL_BASE = os.getenv("LLM_MODEL_BASE", "gpt-4o")
