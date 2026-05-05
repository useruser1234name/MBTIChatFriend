"""FastAPI 메인 서버"""

import logging
from contextlib import asynccontextmanager

import uvicorn

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from .background_tasks import drain_background_tasks, snapshot_background_tasks
from .config import CORS_ORIGINS, HOST, PORT, ENVIRONMENT, LOG_LEVEL, REQUIRE_AUTH
from .firebase_service import init_firebase
from .image_service import get_storage_health, init_storage
from .postgres import init_postgres_schema, init_async_pool, close_async_pool, get_postgres_health
from .shared import limiter
from .routers import chat, fcm, memory, finetune, quality, data, image, misc
from .vector_store import close_store, get_vector_store_health

logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger(__name__)


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
    await init_async_pool(min_size=5, max_size=20)
    yield
    drain_result = await drain_background_tasks(timeout=10.0)
    logger.info("Background tasks drained: %s", drain_result)
    close_store()
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

def _readiness_payload() -> dict:
    dependencies = {
        "postgres": get_postgres_health(),
        "vector_store": get_vector_store_health(),
        "storage": get_storage_health(),
        "background_tasks": snapshot_background_tasks(),
    }
    ready = dependencies["postgres"]["status"] != "error"
    return {
        "status": "ready" if ready else "degraded",
        "dependencies": dependencies,
    }


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok", "kind": "live"}


@app.get("/health/live", tags=["health"])
async def health_live():
    return {"status": "ok", "kind": "live"}


@app.get("/health/ready", tags=["health"])
async def health_ready():
    payload = _readiness_payload()
    status_code = 200 if payload["status"] == "ready" else 503
    return JSONResponse(status_code=status_code, content=payload)


_PREFIX = "/api/v1"
app.include_router(misc.router, prefix=_PREFIX, tags=["misc"])
app.include_router(chat.router, prefix=_PREFIX, tags=["chat"])
app.include_router(fcm.router, prefix=_PREFIX, tags=["fcm"])
app.include_router(memory.router, prefix=_PREFIX, tags=["memory"])
app.include_router(finetune.router, prefix=_PREFIX, tags=["finetune"])
app.include_router(quality.router, prefix=_PREFIX, tags=["quality"])
app.include_router(data.router, prefix=_PREFIX, tags=["data"])
app.include_router(image.router, prefix=_PREFIX, tags=["image"])


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=PORT,
        reload=(ENVIRONMENT != "production"),
    )
