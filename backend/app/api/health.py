from fastapi import APIRouter, status

from backend.app.schemas.health import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="API Health Check",
    description="Returns the operational status of the RaktSetu backend process.",
)
async def get_health() -> HealthResponse:
    """Return operational process health for the RaktSetu API."""
    return HealthResponse(status="ok", service="raktsetu-api")
