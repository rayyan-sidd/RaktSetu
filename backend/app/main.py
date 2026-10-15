from fastapi import FastAPI

from backend.app.api.health import router as health_router

app = FastAPI(
    title="RaktSetu API",
    description="Backend API powering the RaktSetu blood discovery and voluntary donor coordination prototype.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(health_router)
