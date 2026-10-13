"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.support import router as support_router
from app.services.redis_store import close_redis_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await close_redis_client()


app = FastAPI(
    title="AI Support API",
    version="1.0.0",
    description="Async AI customer-support agent (FastAPI + Redis + OpenRouter)",
    lifespan=lifespan,
)

app.include_router(support_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
