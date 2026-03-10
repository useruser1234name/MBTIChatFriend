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

# 인증 강제 여부 - production에서는 기본 활성화
REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "true" if ENVIRONMENT == "production" else "false").lower() == "true"
