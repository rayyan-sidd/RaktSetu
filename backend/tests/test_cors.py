import os
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from backend.app.main import app, get_cors_origins


def test_get_cors_origins_defaults_to_localhost_and_no_wildcard() -> None:
    """Verify that default CORS origins contain localhost development hosts and no wildcards."""
    with patch.dict(os.environ, {"RAKTSETU_CORS_ORIGINS": ""}, clear=False):
        origins = get_cors_origins()
        assert "http://localhost:5173" in origins
        assert "http://127.0.0.1:5173" in origins
        assert "http://localhost:3000" in origins
        assert "*" not in origins


def test_get_cors_origins_parses_comma_separated_env_var() -> None:
    """Verify comma-separated origins with whitespace are cleanly parsed and deduplicated."""
    custom_origins = " https://raktsetu.onrender.com , https://raktsetu-web.onrender.com , http://localhost:5173 "
    with patch.dict(os.environ, {"RAKTSETU_CORS_ORIGINS": custom_origins}, clear=False):
        origins = get_cors_origins()
        assert "https://raktsetu.onrender.com" in origins
        assert "https://raktsetu-web.onrender.com" in origins
        assert "http://localhost:5173" in origins
        # Ensure no duplicates and no wildcards
        assert origins.count("http://localhost:5173") == 1
        assert "*" not in origins


def test_cors_preflight_allowed_origin() -> None:
    """Verify preflight OPTIONS request from an allowed localhost origin receives CORS headers."""
    client = TestClient(app)
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "GET" in response.headers.get("access-control-allow-methods", "")


def test_cors_preflight_disallowed_origin() -> None:
    """Verify preflight OPTIONS request from an unrecognized origin does not receive CORS approval."""
    client = TestClient(app)
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://unauthorized-domain.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") != "http://unauthorized-domain.com"


def test_cors_with_configured_render_origin() -> None:
    """Verify that adding an origin to RAKTSETU_CORS_ORIGINS allows that specific origin."""
    test_app = FastAPI()
    with patch.dict(
        os.environ,
        {"RAKTSETU_CORS_ORIGINS": "https://custom-raktsetu.onrender.com"},
        clear=False,
    ):
        test_app.add_middleware(
            CORSMiddleware,
            allow_origins=get_cors_origins(),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @test_app.get("/test")
        def sample_endpoint():
            return {"status": "ok"}

        test_client = TestClient(test_app)
        response = test_client.options(
            "/test",
            headers={
                "Origin": "https://custom-raktsetu.onrender.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert (
            response.headers.get("access-control-allow-origin")
            == "https://custom-raktsetu.onrender.com"
        )
