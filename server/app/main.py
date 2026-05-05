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
from .postgres_async import get_async_db
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
    # BD-NEW: production에서 REQUIRE_AUTH 강제 검증
    if ENVIRONMENT == "production" and not REQUIRE_AUTH:
        logger.critical(
            "[보안 경고] ENVIRONMENT=production이지만 REQUIRE_AUTH가 비활성화되어 있습니다. "
            "모든 인증이 우회될 수 있습니다. 즉시 설정을 확인하세요."
        )
    elif ENVIRONMENT == "production":
        logger.info("Production 환경: 인증 강제 활성화 확인됨")
    init_firebase()
    init_storage()
    init_postgres_schema()
    # W1-2: 비동기 PostgreSQL 풀 초기화
    await init_async_pool()
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
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
