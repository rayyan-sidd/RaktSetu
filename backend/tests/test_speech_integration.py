"""End-to-end integration test for Gnani Prisma STT + Discovery API + Timbre TTS pipeline."""

import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from telegram import Update

from backend.app.bot.client import DiscoveryApiClient
from backend.app.bot.config import BotConfig
from backend.app.bot.handlers import voice_message_handler
from backend.app.speech.client import GnaniSpeechClient
from backend.app.speech.config import GnaniConfig


_VALID_OGG_OPUS_E2E = (
    b"OggS\x00\x02"
    + b"\x00" * 20
    + bytes([1, 19])
    + b"OpusHead\x01\x01\x38\x01\x80\xbb\x00\x00\x00\x00\x00"
    + b"e2e-audio-response"
)


@pytest.mark.anyio
async def test_end_to_end_voice_discovery_pipeline() -> None:
    """Verify full pipeline from Telegram voice note through Gnani STT, Discovery API, and Gnani TTS."""
    requests_seen: list[str] = []

    def gnani_handler(request: httpx.Request) -> httpx.Response:
        requests_seen.append(f"GNANI:{request.method} {request.url.path}")
        assert request.headers.get("x-api-key-id") == "e2e-gnani-key"

        if request.url.path == "/stt/v3":
            assert b"voice-audio-sample" in request.content
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "request_id": "stt-e2e-1",
                    "transcript": "I need B negative blood in Lucknow urgently",
                    "detected_language_code": "en-IN",
                },
            )

        if request.url.path == "/api/v1/tts/inference":
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["language"] == "en-IN"
            assert payload["model"] == "timbre-v3.0"
            assert payload["voice"] == "Shivani"
            assert "King George Medical University" in payload["text"]
            assert "B negative" in payload["text"]
            assert "Always call and confirm" in payload["text"]
            return httpx.Response(
                200,
                headers={"content-type": "audio/ogg"},
                content=_VALID_OGG_OPUS_E2E,
            )

        return httpx.Response(404)

    def discovery_handler(request: httpx.Request) -> httpx.Response:
        requests_seen.append(f"API:{request.method} {request.url.path}?{request.url.query.decode()}")
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": 21,
                        "name": "King George Medical University Blood Bank",
                        "city": "Lucknow",
                        "locality": "Chowk",
                        "category": "Government",
                        "source_type": "external_source",
                        "source_name": "e-RaktKosh (MoHFW)",
                        "stock_reports": [
                            {
                                "id": 201,
                                "blood_bank_id": 21,
                                "blood_group": "B-",
                                "blood_component": "Whole Blood",
                                "units_reported": 7,
                                "source_name": "e-RaktKosh (MoHFW)",
                                "verification_status": "reported_unverified",
                                "source_reported_timestamp": "2026-10-16T06:00:00Z",
                                "retrieval_timestamp": "2026-10-16T06:15:00Z",
                                "data_timestamp": "2026-10-16T06:15:00Z",
                            }
                        ],
                    }
                ],
                "count": 1,
                "data_notice": "e-RaktKosh notice",
                "data_timestamp": "2026-10-16T06:15:00Z",
            },
        )

    gnani_http = httpx.AsyncClient(
        base_url="https://api.vachana.ai",
        transport=httpx.MockTransport(gnani_handler),
    )

    gnani_cfg = GnaniConfig(api_key="e2e-gnani-key")
    bot_cfg = BotConfig(
        bot_token="e2e-bot-token",
        api_base_url="http://127.0.0.1:8000",
        gnani=gnani_cfg,
    )

    speech_client = GnaniSpeechClient(config=gnani_cfg, http_client=gnani_http)
    api_client = DiscoveryApiClient(
        base_url="http://127.0.0.1:8000",
        transport=httpx.MockTransport(discovery_handler),
    )

    tg_file = MagicMock()
    tg_file.download_as_bytearray = AsyncMock(return_value=bytearray(b"voice-audio-sample"))

    bot = MagicMock()
    bot.get_file = AsyncMock(return_value=tg_file)

    message = MagicMock()
    message.voice = MagicMock(
        file_id="tg-voice-99",
        mime_type="audio/ogg",
        file_size=1024,
        duration=4,
    )
    message.audio = None
    message.reply_text = AsyncMock()
    message.reply_voice = AsyncMock()

    update = MagicMock(spec=Update)
    update.effective_message = message

    context = MagicMock()
    context.bot = bot
    context.bot_data = {
        "config": bot_cfg,
        "api_client": api_client,
        "speech_client": speech_client,
    }

    try:
        await voice_message_handler(update, context)
    finally:
        await gnani_http.aclose()

    assert requests_seen == [
        "GNANI:POST /stt/v3",
        "API:GET /api/blood-banks?city=Lucknow&blood_group=B-",
        "GNANI:POST /api/v1/tts/inference",
    ]

    assert message.reply_text.await_count == 2
    assert "I need B negative blood in Lucknow urgently" in message.reply_text.call_args_list[0].args[0]
    assert "King George Medical University Blood Bank" in message.reply_text.call_args_list[1].args[0]

    message.reply_voice.assert_awaited_once()
    voice_call = message.reply_voice.call_args.kwargs
    assert voice_call["voice"].read() == _VALID_OGG_OPUS_E2E
    assert voice_call["filename"] == "raktsetu_reply.ogg"


@pytest.mark.anyio
async def test_end_to_end_non_ogg_tts_preserves_text_and_skips_reply_voice() -> None:
    """When Gnani TTS returns WAV bytes despite OGG request, text results send safely and reply_voice is skipped."""
    wav_bytes = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00fake-wav-body"

    def gnani_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/stt/v3":
            return httpx.Response(
                200,
                json={"success": True, "transcript": "Need O-positive blood in Delhi"},
            )
        if request.url.path == "/api/v1/tts/inference":
            return httpx.Response(
                200,
                headers={"content-type": "audio/ogg"},
                content=wav_bytes,
            )
        return httpx.Response(404)

    def discovery_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "items": [],
                "count": 0,
                "data_notice": "e-RaktKosh notice",
                "data_timestamp": "2026-10-16T06:15:00Z",
            },
        )

    gnani_http = httpx.AsyncClient(
        base_url="https://api.vachana.ai",
        transport=httpx.MockTransport(gnani_handler),
    )
    gnani_cfg = GnaniConfig(api_key="e2e-gnani-key")
    speech_client = GnaniSpeechClient(config=gnani_cfg, http_client=gnani_http)
    api_client = DiscoveryApiClient(
        base_url="http://127.0.0.1:8000",
        transport=httpx.MockTransport(discovery_handler),
    )

    tg_file = MagicMock()
    tg_file.download_as_bytearray = AsyncMock(return_value=bytearray(b"voice-sample"))
    bot = MagicMock()
    bot.get_file = AsyncMock(return_value=tg_file)

    message = MagicMock()
    message.voice = MagicMock(file_id="v2", mime_type="audio/ogg", file_size=512, duration=3)
    message.audio = None
    message.reply_text = AsyncMock()
    message.reply_voice = AsyncMock()

    update = MagicMock(spec=Update)
    update.effective_message = message

    context = MagicMock()
    context.bot = bot
    context.bot_data = {
        "config": BotConfig(bot_token="tok", gnani=gnani_cfg),
        "api_client": api_client,
        "speech_client": speech_client,
    }

    try:
        await voice_message_handler(update, context)
    finally:
        await gnani_http.aclose()

    assert message.reply_text.await_count == 2
    assert "No Reported Facilities Found" in message.reply_text.call_args_list[1].args[0]
    message.reply_voice.assert_not_awaited()
