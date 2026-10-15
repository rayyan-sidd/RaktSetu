from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health_endpoint_status_code() -> None:
    """Verify GET /api/health returns HTTP 200 OK."""
    response = client.get("/api/health")
    assert response.status_code == 200


def test_health_endpoint_payload() -> None:
    """Verify GET /api/health returns exact expected JSON payload."""
    response = client.get("/api/health")
    assert response.headers["content-type"].startswith("application/json")
    data = response.json()
    assert data == {"status": "ok", "service": "raktsetu-api"}


def test_health_endpoint_in_openapi_schema() -> None:
    """Verify /api/health is registered in the application OpenAPI specification."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "paths" in schema
    assert "/api/health" in schema["paths"]
    assert "get" in schema["paths"]["/api/health"]
    assert schema["info"]["title"] == "RaktSetu API"
    assert schema["info"]["version"] == "0.1.0"
