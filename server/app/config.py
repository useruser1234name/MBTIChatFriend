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
# 프로젝트 컨벤션: gpt-4.1 / gpt-4.1-mini만 사용 (gpt-4o 금지 — CLAUDE.md)
LLM_MODEL_COMPLEX = os.getenv("LLM_MODEL_COMPLEX", "gpt-4.1")
LLM_MODEL_SIMPLE = os.getenv("LLM_MODEL_SIMPLE", "gpt-4.1-mini")
LLM_MODEL_BASE = os.getenv("LLM_MODEL_BASE", "gpt-4.1")

# W2-6: 사용자당 일일 토큰 상한 (PM-B 손민준 + ARCH-B 황인호 설계)
# 기본값 50,000 토큰 = GPT-4o-mini 기준 약 1만 단어 교환
DAILY_TOKEN_LIMIT = int(os.getenv("DAILY_TOKEN_LIMIT", "50000"))

# Self-regulation 임계값 — RemoteConfig 동적화 (6차 스프린트 — CTO-B 김태우)
# Firebase RemoteConfig 또는 환경변수로 런타임 제어 가능
SESSION_LIMIT_ADULT_MINUTES = int(os.getenv("SESSION_LIMIT_ADULT_MINUTES", "90"))
SESSION_LIMIT_MINOR_MINUTES = int(os.getenv("SESSION_LIMIT_MINOR_MINUTES", "60"))
SESSION_CONSECUTIVE_DAYS_THRESHOLD = int(os.getenv("SESSION_CONSECUTIVE_DAYS_THRESHOLD", "7"))

MAX_TOKENS = int(os.getenv("MAX_TOKENS", "768"))

# ── Google Play 결제 검증 (billing) ──────────────────────────────
# 서버측 영수증 검증 설정. 미구성 시 production에서는 프리미엄 부여를 거부한다.
GOOGLE_PLAY_PACKAGE_NAME = os.getenv("GOOGLE_PLAY_PACKAGE_NAME", "")
# 서비스 계정 JSON 파일 경로 (Google Play Developer API 호출용)
GOOGLE_PLAY_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON", "")
# RTDN(Pub/Sub push) OIDC 토큰 검증용 audience. 미설정 시 production에서 webhook 거부.
PLAY_RTDN_AUDIENCE = os.getenv("PLAY_RTDN_AUDIENCE", "")
# 결제 검증 미구성 상태에서 개발 편의를 위해 mock 허용 여부 (production 무시)
BILLING_ALLOW_MOCK = os.getenv("BILLING_ALLOW_MOCK", "true").lower() == "true"

# 내부/배치/관리자 엔드포인트 보호용 토큰 (스케줄러·크론이 호출 시 헤더로 전달)
INTERNAL_API_TOKEN = os.getenv("INTERNAL_API_TOKEN", "")

# 읽기 복제본 DB (postgres_async.py의 replica 전용 풀). 미설정 시 replica 없음.
DATABASE_REPLICA_URL = os.getenv("DATABASE_REPLICA_URL", "")

# 커뮤니티 트렌딩 캐시 (routers/community.py)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
TRENDING_CACHE_TTL = 600  # 10분
