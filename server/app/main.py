"""FastAPI 메인 서버"""

import logging
from contextlib import asynccontextmanager

import uvicorn

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .config import CORS_ORIGINS, ENVIRONMENT, HOST, PORT, REQUIRE_AUTH
from .firebase_service import init_firebase
from .image_service import init_storage
from .postgres import init_postgres_schema
from .postgres_async import get_async_db, initialize_read_pool
from .scheduler import start_scheduler

from .routers import (
    chat,
    health,
    quality,
    session,
    subscription,
    relationship,
    ab_test,
    data,
    billing,
    letter,
    fcm,
    diary,
    image,
    finetune,
    referral,
    community,
    compatibility,
    notifications,
    users,
    events,
    web_chat,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)


async def init_async_pool() -> None:
    await get_async_db().initialize()


async def close_async_pool() -> None:
    await get_async_db().close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("MBTI Chat Friend 서버 시작")
    # BD-NEW: production에서 REQUIRE_AUTH 강제 검증 — 비활성 시 기동 중단
    if ENVIRONMENT == "production" and not REQUIRE_AUTH:
        logger.critical(
            "[보안 차단] ENVIRONMENT=production이지만 REQUIRE_AUTH가 비활성화되어 있습니다. "
            "인증 우회 위험으로 서버 기동을 중단합니다. REQUIRE_AUTH=true로 설정하세요."
        )
        raise RuntimeError("production 환경에서는 REQUIRE_AUTH=false로 기동할 수 없습니다.")
    elif ENVIRONMENT == "production":
        logger.info("Production 환경: 인증 강제 활성화 확인됨")
    init_firebase()
    init_storage()
    init_postgres_schema()
    # W1-2: 비동기 PostgreSQL 풀 초기화
    await init_async_pool()
    # A5: 읽기 복제본 풀 초기화 (DATABASE_REPLICA_URL 없으면 내부적으로 스킵)
    await initialize_read_pool()
    start_scheduler()
    yield
    await close_async_pool()
    logger.info("서버 종료")


_is_production = ENVIRONMENT == "production"
app = FastAPI(
    title="MBTI Chat Friend API",
    version="0.5.0",
    lifespan=lifespan,
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    openapi_url=None if _is_production else "/openapi.json",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS: 와일드카드(*) origin과 allow_credentials=True 조합은 브라우저 표준 위반이며
# 보안상 위험하다. 명시적 origin이 설정된 경우에만 credentials를 허용한다.
_allow_credentials = bool(CORS_ORIGINS) and "*" not in CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=_allow_credentials,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# 라우터 등록
app.include_router(health.router)
app.include_router(chat.router)
app.include_router(fcm.router)
app.include_router(diary.router)
app.include_router(image.router)
app.include_router(finetune.router)
app.include_router(quality.router)
app.include_router(data.router)
app.include_router(session.router)
app.include_router(ab_test.router)
app.include_router(relationship.router)
app.include_router(subscription.router)
app.include_router(billing.router)
app.include_router(letter.router)
app.include_router(referral.router)
app.include_router(community.router)
app.include_router(compatibility.router)
app.include_router(notifications.router)
app.include_router(users.router)
app.include_router(events.router)
app.include_router(web_chat.router)

# /health (루트 레벨, 하위 호환)
@app.get("/health")
async def health_check_root():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=PORT,
        reload=(ENVIRONMENT != "production"),
    )
