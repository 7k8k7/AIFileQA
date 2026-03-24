from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base
from app.core.observability import configure_logging

configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup: create tables (dev convenience — production uses alembic)
    logger.info(
        "Application starting: app=%s debug=%s database=%s",
        settings.app_name,
        settings.debug,
        settings.database_url.split("://", 1)[0],
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown
    logger.info("Application shutting down: app=%s", settings.app_name)
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ──
@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name}


# ── API routers ──
from app.api.documents import router as documents_router
from app.api.providers import router as providers_router
from app.api.chat import router as chat_router
from app.api.retrieval import router as retrieval_router

app.include_router(documents_router)
app.include_router(providers_router)
app.include_router(chat_router)
app.include_router(retrieval_router)
