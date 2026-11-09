"""Tests for Timbre Text-to-Speech (TTS) synthesis and spoken summary formatter."""

import base64
import json

import httpx
import pytest

from backend.app.speech.client import GnaniSpeechClient
from backend.app.speech.config import GnaniConfig
from backend.app.speech.exceptions import (
    GnaniAuthError,
    GnaniRateLimitError,
    TimbreSynthesisError,
)
from backend.app.speech.timbre import (
    TimbreAudioConfig,
    format_spoken_discovery_summary,
)


def test_timbre_audio_config_serialization() -> None:
    """Verify TimbreAudioConfig generates expected container-specific JSON payloads."""
    ogg_cfg = TimbreAudioConfig(container="ogg", encoding="oggopus", sample_rate=48000)
    assert ogg_cfg.to_dict() == {
        "container": "ogg",
        "sample_rate": 48000,
        "num_channels": 1,
        "encoding": "oggopus",
    }
    assert ogg_cfg.default_content_type == "audio/ogg"
    assert ogg_cfg.default_filename == "raktsetu_reply.ogg"

    wav_cfg = TimbreAudioConfig(container="wav", encoding="linear_pcm", sample_rate=24000, sample_width=2)
    assert wav_cfg.to_dict() == {
        "container": "wav",
        "sample_rate": 24000,
        "num_channels": 1,
        "encoding": "linear_pcm",
        "sample_width": 2,
    }
    assert wav_cfg.default_content_type == "audio/wav"

    mp3_cfg = TimbreAudioConfig(container="mp3", sample_rate=48000)
    assert mp3_cfg.to_dict() == {
        "container": "mp3",
        "sample_rate": 48000,
        "num_channels": 1,
    }
    assert mp3_cfg.default_content_type == "audio/mpeg"


@pytest.mark.anyio
async def test_synthesize_speech_binary_success() -> None:
    """Verify Timbre TTS sends expected JSON request and returns binary audio bytes."""
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            headers={"content-type": "audio/ogg"},
            content=b"OggS-fake-opus-stream-bytes",
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(base_url="https://api.vachana.ai", transport=transport) as hc:
        client = GnaniSpeechClient(
            config=GnaniConfig(api_key="timbre-key"),
            http_client=hc,
        )
        result = await client.synthesize_speech(
            text="Found 2 blood banks in Delhi.",
            voice="Nalini",
            language="en-IN",
        )

    assert captured["url"] == "https://api.vachana.ai/api/v1/tts/inference"
    assert captured["headers"]["x-api-key-id"] == "timbre-key"
    assert captured["body"]["text"] == "Found 2 blood banks in Delhi."
    assert captured["body"]["voice"] == "Nalini"
    assert captured["body"]["model"] == "timbre-v3.0"
    assert captured["body"]["language"] == "en-IN"
    assert captured["body"]["audio_config"]["container"] == "ogg"

    assert result.audio_bytes == b"OggS-fake-opus-stream-bytes"
    assert result.content_type == "audio/ogg"
    assert result.container == "ogg"
    assert result.filename == "raktsetu_reply.ogg"


@pytest.mark.anyio
async def test_synthesize_speech_base64_json_fallback() -> None:
    """Verify Timbre TTS handles JSON base64-wrapped audio payloads."""
    raw_audio = b"RIFF-fake-wav-data"
    encoded = base64.b64encode(raw_audio).decode("ascii")

    transport = httpx.MockTransport(
        lambda req: httpx.Response(
            200,
            json={"success": True, "audio": encoded},
        )
    )
    async with httpx.AsyncClient(base_url="https://api.vachana.ai", transport=transport) as hc:
        client = GnaniSpeechClient(config=GnaniConfig(api_key="k"), http_client=hc)
        result = await client.synthesize_speech(
            "Testing wav output",
            audio_config=TimbreAudioConfig(container="wav", encoding="linear_pcm"),
        )

    assert result.audio_bytes == raw_audio
    assert result.content_type == "audio/wav"
    assert result.filename == "raktsetu_reply.wav"


@pytest.mark.anyio
async def test_synthesize_speech_validation_and_errors() -> None:
    """Verify empty input, empty audio, and API error codes raise expected exceptions."""
    client = GnaniSpeechClient(config=GnaniConfig(api_key="k"))
    with pytest.raises(TimbreSynthesisError, match="empty text"):
        await client.synthesize_speech("   ")

    # Empty audio bytes response
    t_empty = httpx.MockTransport(lambda req: httpx.Response(200, headers={"content-type": "audio/ogg"}, content=b""))
    async with httpx.AsyncClient(base_url="https://api.vachana.ai", transport=t_empty) as hc:
        c = GnaniSpeechClient(config=GnaniConfig(api_key="k"), http_client=hc)
        with pytest.raises(TimbreSynthesisError, match="empty audio"):
            await c.synthesize_speech("Hello")

    # 401 Auth failure
    t_401 = httpx.MockTransport(lambda req: httpx.Response(401, text="Unauthorized"))
    async with httpx.AsyncClient(base_url="https://api.vachana.ai", transport=t_401) as hc:
        c = GnaniSpeechClient(config=GnaniConfig(api_key="bad"), http_client=hc)
        with pytest.raises(GnaniAuthError):
            await c.synthesize_speech("Hello")

    # 429 Rate limit
    t_429 = httpx.MockTransport(lambda req: httpx.Response(429, text="Busy"))
    async with httpx.AsyncClient(base_url="https://api.vachana.ai", transport=t_429) as hc:
        c = GnaniSpeechClient(config=GnaniConfig(api_key="k"), http_client=hc)
        with pytest.raises(GnaniRateLimitError):
            await c.synthesize_speech("Hello")

    # 500 Server failure -> TimbreSynthesisError
    t_500 = httpx.MockTransport(lambda req: httpx.Response(500, text="Internal error"))
    async with httpx.AsyncClient(base_url="https://api.vachana.ai", transport=t_500) as hc:
        c = GnaniSpeechClient(config=GnaniConfig(api_key="k"), http_client=hc)
        with pytest.raises(TimbreSynthesisError):
            await c.synthesize_speech("Hello")

    # JSON success: false
    t_fail = httpx.MockTransport(
        lambda req: httpx.Response(200, json={"success": False, "message": "Invalid voice"})
    )
    async with httpx.AsyncClient(base_url="https://api.vachana.ai", transport=t_fail) as hc:
        c = GnaniSpeechClient(config=GnaniConfig(api_key="k"), http_client=hc)
        with pytest.raises(TimbreSynthesisError, match="Invalid voice"):
            await c.synthesize_speech("Hello")


def test_format_spoken_discovery_summary_english_and_hindi() -> None:
    """Verify spoken summary builds clean, natural prose with mandatory verification notice."""
    sample_facilities = [
        {
            "name": "AIIMS Main Blood Bank",
            "city": "Delhi",
            "stock_reports": [
                {"blood_group": "O+", "units_reported": 12},
            ],
        },
        {
            "name": "Safdarjung Hospital Blood Bank",
            "city": "Delhi",
            "stock_reports": [
                {"blood_group": "O+", "units_reported": 4},
            ],
        },
    ]

    en_summary = format_spoken_discovery_summary(
        facilities=sample_facilities,
        total_count=2,
        blood_group="O+",
        city="Delhi",
        language="en-IN",
    )
    assert "Found 2 reported blood banks" in en_summary
    assert "O positive" in en_summary
    assert "O+" not in en_summary
    assert "AIIMS Main Blood Bank with 12 units reported" in en_summary
    assert "confirm availability directly" in en_summary

    hi_summary = format_spoken_discovery_summary(
        facilities=sample_facilities,
        total_count=2,
        blood_group="O+",
        city="Delhi",
        language="hi-IN",
    )
    assert "2 रिपोर्टेड ब्लड बैंक" in hi_summary
    assert "O positive" in hi_summary
    assert "AIIMS Main Blood Bank, 12 यूनिट उपलब्ध" in hi_summary
    assert "पुष्टि अवश्य करें" in hi_summary


def test_format_spoken_discovery_summary_empty() -> None:
    """Verify empty results spoken message in both English and Hindi."""
    en_empty = format_spoken_discovery_summary([], 0, blood_group="AB-", city="Lucknow", language="en-IN")
    assert "No active reported blood bank stock" in en_empty
    assert "A B negative" in en_empty
    assert "Lucknow" in en_empty

    hi_empty = format_spoken_discovery_summary([], 0, blood_group="AB-", city="Lucknow", language="hi-IN")
    assert "कोई सक्रिय रिपोर्टेड ब्लड बैंक स्टॉक नहीं मिला" in hi_empty
    assert "A B negative" in hi_empty
