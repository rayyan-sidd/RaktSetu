"""Tests for Gnani speech base client and exception mapping."""

import httpx
import pytest

from backend.app.speech.client import GnaniSpeechClient
from backend.app.speech.config import GnaniConfig
from backend.app.speech.exceptions import (
    GnaniApiError,
    GnaniAuthError,
    GnaniConfigurationError,
    GnaniNetworkError,
    GnaniRateLimitError,
    GnaniTimeoutError,
)


@pytest.mark.anyio
async def test_client_unconfigured_raises_on_headers() -> None:
    """Verify that an unconfigured client raises GnaniConfigurationError."""
    client = GnaniSpeechClient(config=GnaniConfig(api_key=""))
    with pytest.raises(GnaniConfigurationError, match="not configured"):
        client._get_headers()


def test_client_headers_populated() -> None:
    """Verify headers include X-API-Key-ID and User-Agent."""
    client = GnaniSpeechClient(config=GnaniConfig(api_key="my-key"))
    headers = client._get_headers(content_type="application/json")
    assert headers["X-API-Key-ID"] == "my-key"
    assert "RaktSetu" in headers["User-Agent"]
    assert headers["Content-Type"] == "application/json"


def test_client_error_mapping() -> None:
    """Verify HTTP and transport exceptions are mapped to domain exceptions."""
    client = GnaniSpeechClient(config=GnaniConfig(api_key="key"))

    # Timeout
    timeout_err = client._map_http_error(httpx.ReadTimeout("timed out"))
    assert isinstance(timeout_err, GnaniTimeoutError)

    # 401 Unauthorized
    dummy_req = httpx.Request("POST", "https://api.vachana.ai/test")
    resp_401 = httpx.Response(401, request=dummy_req, text="Unauthorized")
    auth_err = client._map_http_error(httpx.HTTPStatusError("401", request=dummy_req, response=resp_401))
    assert isinstance(auth_err, GnaniAuthError)
    assert auth_err.status_code == 401

    # 429 Rate limited
    resp_429 = httpx.Response(429, request=dummy_req, text="Too many requests")
    rl_err = client._map_http_error(httpx.HTTPStatusError("429", request=dummy_req, response=resp_429))
    assert isinstance(rl_err, GnaniRateLimitError)
    assert rl_err.status_code == 429

    # 500 Internal error
    resp_500 = httpx.Response(500, request=dummy_req, text="Server Error")
    api_err = client._map_http_error(httpx.HTTPStatusError("500", request=dummy_req, response=resp_500))
    assert isinstance(api_err, GnaniApiError)
    assert api_err.status_code == 500

    # Network connect error
    net_err = client._map_http_error(httpx.ConnectError("Failed to connect"))
    assert isinstance(net_err, GnaniNetworkError)


@pytest.mark.anyio
async def test_client_context_manager() -> None:
    """Verify async context manager creates and closes client."""
    cfg = GnaniConfig(api_key="token")
    async with GnaniSpeechClient(config=cfg) as client:
        assert client.client is not None
        assert not client.client.is_closed
    assert client._client is None
