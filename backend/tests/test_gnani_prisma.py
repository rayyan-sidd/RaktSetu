"""Tests for Prisma Speech-to-Text (STT) integration and blood query extraction."""

import httpx
import pytest

from backend.app.speech.client import GnaniSpeechClient
from backend.app.speech.config import GnaniConfig
from backend.app.speech.exceptions import (
    GnaniAuthError,
    GnaniRateLimitError,
    GnaniTimeoutError,
    PrismaTranscriptionError,
)
from backend.app.speech.query_parser import extract_blood_query


@pytest.mark.anyio
async def test_transcribe_audio_success_v3() -> None:
    """Verify Prisma v3.0 transcription sends expected request and parses response."""
    captured_request: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_request["url"] = str(request.url)
        captured_request["headers"] = dict(request.headers)
        captured_request["content"] = request.content
        return httpx.Response(
            200,
            json={
                "success": True,
                "request_id": "req-123",
                "transcript": "Need O+ blood in Delhi urgently",
                "model": "prisma-v3.0",
                "detected_language_code": "en-IN",
                "processing_time": 0.42,
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(base_url="https://api.vachana.ai", transport=transport) as http_client:
        client = GnaniSpeechClient(
            config=GnaniConfig(api_key="test-prisma-key"),
            http_client=http_client,
        )
        result = await client.transcribe_audio(b"fake-ogg-bytes", filename="note.ogg")

    assert captured_request["url"] == "https://api.vachana.ai/stt/v3"
    assert captured_request["headers"]["x-api-key-id"] == "test-prisma-key"
    assert b"prisma-v3.0" in captured_request["content"]
    assert b"indic-auto" in captured_request["content"]
    assert b"fake-ogg-bytes" in captured_request["content"]

    assert result.transcript == "Need O+ blood in Delhi urgently"
    assert result.detected_language_code == "en-IN"
    assert result.request_id == "req-123"
    assert result.processing_time == 0.42
    assert result.is_empty is False


@pytest.mark.anyio
async def test_transcribe_audio_v25_minimal_payload() -> None:
    """Verify Prisma handles minimal v2.5 response shape cleanly."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": True,
                "transcript": "  लखनऊ में बी पॉजिटिव ब्लड  ",
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(base_url="https://api.vachana.ai", transport=transport) as http_client:
        client = GnaniSpeechClient(
            config=GnaniConfig(api_key="test-key"),
            http_client=http_client,
        )
        result = await client.transcribe_audio(b"wav-data", model="prisma-v2.5")

    assert result.transcript == "लखनऊ में बी पॉजिटिव ब्लड"
    assert result.detected_language_code is None
    assert result.is_empty is False


@pytest.mark.anyio
async def test_transcribe_audio_empty_bytes_raises() -> None:
    """Verify empty audio payload fails fast without network call."""
    client = GnaniSpeechClient(config=GnaniConfig(api_key="test-key"))
    with pytest.raises(PrismaTranscriptionError, match="empty audio"):
        await client.transcribe_audio(b"")


@pytest.mark.anyio
async def test_transcribe_audio_error_handling() -> None:
    """Verify HTTP and API error responses map to appropriate exceptions."""
    # 401 Auth Error
    t_401 = httpx.MockTransport(lambda req: httpx.Response(401, text="Invalid key"))
    async with httpx.AsyncClient(base_url="https://api.vachana.ai", transport=t_401) as hc:
        c = GnaniSpeechClient(config=GnaniConfig(api_key="bad"), http_client=hc)
        with pytest.raises(GnaniAuthError):
            await c.transcribe_audio(b"audio")

    # 429 Rate Limit
    t_429 = httpx.MockTransport(lambda req: httpx.Response(429, text="Rate limited"))
    async with httpx.AsyncClient(base_url="https://api.vachana.ai", transport=t_429) as hc:
        c = GnaniSpeechClient(config=GnaniConfig(api_key="k"), http_client=hc)
        with pytest.raises(GnaniRateLimitError):
            await c.transcribe_audio(b"audio")

    # 500 Server Error -> PrismaTranscriptionError
    t_500 = httpx.MockTransport(lambda req: httpx.Response(500, text="Server failed"))
    async with httpx.AsyncClient(base_url="https://api.vachana.ai", transport=t_500) as hc:
        c = GnaniSpeechClient(config=GnaniConfig(api_key="k"), http_client=hc)
        with pytest.raises(PrismaTranscriptionError):
            await c.transcribe_audio(b"audio")

    # 200 with success: false
    t_fail = httpx.MockTransport(lambda req: httpx.Response(200, json={"success": False, "message": "Corrupt audio"}))
    async with httpx.AsyncClient(base_url="https://api.vachana.ai", transport=t_fail) as hc:
        c = GnaniSpeechClient(config=GnaniConfig(api_key="k"), http_client=hc)
        with pytest.raises(PrismaTranscriptionError, match="Corrupt audio"):
            await c.transcribe_audio(b"audio")

    # Timeout
    def timeout_handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Timed out", request=req)

    t_timeout = httpx.MockTransport(timeout_handler)
    async with httpx.AsyncClient(base_url="https://api.vachana.ai", transport=t_timeout) as hc:
        c = GnaniSpeechClient(config=GnaniConfig(api_key="k"), http_client=hc)
        with pytest.raises(GnaniTimeoutError):
            await c.transcribe_audio(b"audio")


@pytest.mark.parametrize(
    "transcript, expected_group, expected_city",
    [
        ("Find O+ blood in Delhi", "O+", "Delhi"),
        ("Need A negative blood in Lucknow immediately", "A-", "Lucknow"),
        ("Can I get AB positive in New Delhi?", "AB+", "Delhi"),
        ("AB- blood bank in Lucknow please", "AB-", "Lucknow"),
        ("Looking for B +ve in Dilli", "B+", "Delhi"),
        ("oh negative blood needed in lko", "O-", "Lucknow"),
        ("0+ blood Delhi", "O+", "Delhi"),
        ("a b negative in both cities", "AB-", "All"),
        ("Delhi and Lucknow O positive", "O+", "All"),
        ("दिल्ली में ओ पॉजिटिव ब्लड बैंक चाहिए", "O+", "Delhi"),
        ("लखनऊ में बी नेगेटिव रक्त", "B-", "Lucknow"),
        ("नई दिल्ली में एबी पॉजिटिव", "AB+", "Delhi"),
        ("लखनऊ में ए+ ब्लड", "A+", "Lucknow"),
        ("All blood groups in Delhi", "All", "Delhi"),
        ("सभी ब्लड ग्रुप दिल्ली में", "All", "Delhi"),
        ("Only O+ mentioned here", "O+", None),
        ("Only Lucknow mentioned here", None, "Lucknow"),
        ("Hello how are you doing", None, None),
        ("", None, None),
    ],
)
def test_extract_blood_query_variants(
    transcript: str,
    expected_group: str | None,
    expected_city: str | None,
) -> None:
    """Verify query extraction across English, Hinglish, Hindi, and ASR variants."""
    parsed = extract_blood_query(transcript)
    assert parsed.blood_group == expected_group
    assert parsed.city == expected_city
