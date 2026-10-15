from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Schema representing API process health status."""

    status: str = Field(
        default="ok",
        description="Operational health status of the API service process",
        examples=["ok"],
    )
    service: str = Field(
        default="raktsetu-api",
        description="Name identifier of the backend service",
        examples=["raktsetu-api"],
    )
