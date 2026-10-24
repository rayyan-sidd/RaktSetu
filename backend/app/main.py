from contextlib import asynccontextmanager
import os
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.blood_banks import router as blood_banks_router
from backend.app.api.health import router as health_router
from backend.app.core.database import SessionLocal, init_db
from backend.app.services.seeder import seed_deployment_snapshot

DEFAULT_DEV_CORS_ORIGINS: list[str] = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]


def get_cors_origins() -> list[str]:
    """Retrieve allowed CORS origins combining localhost development defaults and RAKTSETU_CORS_ORIGINS."""
    origins = list(DEFAULT_DEV_CORS_ORIGINS)
    custom_origins = os.getenv("RAKTSETU_CORS_ORIGINS", "")
    if custom_origins:
        for origin in custom_origins.split(","):
            cleaned = origin.strip()
            if cleaned and cleaned not in origins:
                origins.append(cleaned)
    return origins


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup and shutdown tasks.

    Performs database schema migrations first, then safely initializes
    the deployment snapshot fixture if the database is completely empty.
    """
    init_db()
    with SessionLocal() as db:
        seed_deployment_snapshot(db)
    yield


app = FastAPI(
    title="RaktSetu API",
    description="Backend API powering the RaktSetu blood discovery and voluntary donor coordination prototype.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(blood_banks_router)

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=port, reload=False)
