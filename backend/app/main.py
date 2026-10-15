from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from backend.app.api.blood_banks import router as blood_banks_router
from backend.app.api.health import router as health_router
from backend.app.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup and shutdown tasks."""
    init_db()
    yield


app = FastAPI(
    title="RaktSetu API",
    description="Backend API powering the RaktSetu blood discovery and voluntary donor coordination prototype.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(blood_banks_router)
