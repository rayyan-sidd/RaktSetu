"""Tests for Telegram bot voice/audio message handling with Gnani Prisma & Timbre."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import MessageHandler

from backend.app.bot.client import DiscoveryApiClient, DiscoveryApiError
from backend.app.bot.config import BotConfig
from backend.app.bot.handlers import voice_message_handler
from backend.app.bot.main import build_bot_application
from backend.app.schemas.blood_bank import (
    BloodBankListResponse,
    BloodBankRead,
    StockReportRead,
)
from backend.app.speech.client import GnaniSpeechClient
from backend.app.speech.config import GnaniConfig
from backend.app.speech.exceptions import (
    PrismaTranscriptionError,
    TimbreSynthesisError,
)
from backend.app.speech.prisma import PrismaTranscriptionResult
from backend.app.speech.timbre import TimbreSynthesisResult


@pytest.fixture
def sample_discovery_response() -> BloodBankListResponse:
    """Provide sample blood bank discovery data."""
    now = datetime(2026, 10, 16, 6, 0, 0, tzinfo=timezone.utc)
    return BloodBankListResponse(
        items=[
            BloodBankRead(
                id=10,
                name="AIIMS Main Blood Bank",
                city="Delhi",
                locality="Ansari Nagar",
                source_type="external_source",
                source_name="e-RaktKosh (MoHFW)",
                stock_reports=[
                    StockReportRead(
                        id=1,
                        blood_bank_id=10,
                        blood_group="O+",
                        blood_component="Whole Blood",
                        units_reported=15,
                        source_name="e-RaktKosh (MoHFW)",
                        verification_status="reported_unverified",
                        source_reported_timestamp=now,
                        retrieval_timestamp=now,
                        data_timestamp=now,
                    )
                ],
            )
        ],
        count=1,
        data_notice="Sample notice",
        data_timestamp=now,
    )


def _make_voice_update(
    file_id: str = "voice_file_1",
    is_audio: bool = False,
    mime_type: str = "audio/ogg",
    file_name: str = "clip.mp3",
) -> tuple[Update, MagicMock]:
    """Create mocked Telegram Update with voice or audio message."""
    update = MagicMock(spec=Update)
    message = MagicMock()
    message.reply_text = AsyncMock()
    message.reply_voice = AsyncMock()

    media = MagicMock()
    media.file_id = file_id
    media.mime_type = mime_type
    if is_audio:
        media.file_name = file_name
        message.voice = None
        message.audio = media
    else:
        message.voice = media
        message.audio = None

    update.effective_message = message
    return update, message


def _make_context(
    speech_configured: bool = True,
    downloaded_bytes: bytes = b"fake-ogg-opus-bytes",
) -> MagicMock:
    """Create mocked Telegram Context with config, api_client, speech_client, and bot."""
    gnani_cfg = GnaniConfig(api_key="gnani-test-key" if speech_configured else "")
    bot_cfg = BotConfig(
        bot_token="mock_bot_token",
        api_base_url="http://mock-api:8000",
        max_facilities=5,
        gnani=gnani_cfg,
    )

    api_client = MagicMock(spec=DiscoveryApiClient)
    speech_client = MagicMock(spec=GnaniSpeechClient)
    speech_client.config = gnani_cfg

    tg_file = MagicMock()
    tg_file.download_as_bytearray = AsyncMock(return_value=bytearray(downloaded_bytes))

    bot = MagicMock()
    bot.get_file = AsyncMock(return_value=tg_file)

    context = MagicMock()
    context.bot = bot
    context.bot_data = {
        "config": bot_cfg,
        "api_client": api_client,
        "speech_client": speech_client if speech_configured else None,
    }
    return context


@pytest.mark.anyio
async def test_voice_handler_when_gnani_unconfigured() -> None:
    """When Gnani key is not configured, politely inform user and offer keyboard."""
    update, message = _make_voice_update()
    context = _make_context(speech_configured=False)

    await voice_message_handler(update, context)

    context.bot.get_file.assert_not_awaited()
    message.reply_text.assert_awaited_once()
    args, kwargs = message.reply_text.call_args
    assert "Voice Search Not Configured" in args[0]
    assert isinstance(kwargs.get("reply_markup"), InlineKeyboardMarkup)


@pytest.mark.anyio
async def test_voice_handler_full_english_flow(
    sample_discovery_response: BloodBankListResponse,
) -> None:
    """Full voice flow: download -> Prisma STT -> discovery search -> text + Timbre TTS voice reply."""
    update, message = _make_voice_update()
    context = _make_context(speech_configured=True)

    speech_client = context.bot_data["speech_client"]
    speech_client.transcribe_audio = AsyncMock(
        return_value=PrismaTranscriptionResult(
            transcript="Need O+ blood in Delhi urgently",
            detected_language_code="en-IN",
        )
    )
    speech_client.synthesize_speech = AsyncMock(
        return_value=TimbreSynthesisResult(
            audio_bytes=b"OggS-synthesized-reply",
            content_type="audio/ogg",
            container="ogg",
            filename="raktsetu_reply.ogg",
        )
    )

    api_client = context.bot_data["api_client"]
    api_client.get_blood_banks = AsyncMock(return_value=sample_discovery_response)
    api_client.filter_and_rank_facilities = MagicMock(
        return_value=([sample_discovery_response.items[0]], 1)
    )

    await voice_message_handler(update, context)

    # Verify STT called with downloaded bytes
    context.bot.get_file.assert_awaited_once_with("voice_file_1")
    speech_client.transcribe_audio.assert_awaited_once_with(
        b"fake-ogg-opus-bytes",
        filename="voice.ogg",
        content_type="audio/ogg",
    )

    # Verify discovery API queried
    api_client.get_blood_banks.assert_awaited_once_with(city="Delhi", blood_group="O+")

    # Verify two text messages: heard acknowledgment + discovery results
    assert message.reply_text.await_count == 2
    ack_text = message.reply_text.call_args_list[0].args[0]
    results_text = message.reply_text.call_args_list[1].args[0]
    assert "Need O+ blood in Delhi urgently" in ack_text
    assert "AIIMS Main Blood Bank" in results_text

    # Verify Timbre TTS synthesis & voice reply
    speech_client.synthesize_speech.assert_awaited_once()
    tts_kwargs = speech_client.synthesize_speech.call_args.kwargs
    assert tts_kwargs["language"] == "en-IN"
    assert "AIIMS Main Blood Bank" in tts_kwargs["text"]
    assert "O positive" in tts_kwargs["text"]

    message.reply_voice.assert_awaited_once()
    voice_kwargs = message.reply_voice.call_args.kwargs
    assert voice_kwargs["filename"] == "raktsetu_reply.ogg"
    assert voice_kwargs["voice"].read() == b"OggS-synthesized-reply"


@pytest.mark.anyio
async def test_voice_handler_hindi_audio_flow(
    sample_discovery_response: BloodBankListResponse,
) -> None:
    """Hindi voice/audio query resolves hi-IN for Timbre TTS reply."""
    update, message = _make_voice_update(is_audio=True, mime_type="audio/mpeg", file_name="query.mp3")
    context = _make_context(speech_configured=True)

    speech_client = context.bot_data["speech_client"]
    speech_client.transcribe_audio = AsyncMock(
        return_value=PrismaTranscriptionResult(
            transcript="दिल्ली में ओ पॉजिटिव ब्लड बैंक",
            detected_language_code="hi-IN",
        )
    )
    speech_client.synthesize_speech = AsyncMock(
        return_value=TimbreSynthesisResult(
            audio_bytes=b"hindi-ogg",
            content_type="audio/ogg",
            container="ogg",
            filename="raktsetu_reply.ogg",
        )
    )

    api_client = context.bot_data["api_client"]
    api_client.get_blood_banks = AsyncMock(return_value=sample_discovery_response)
    api_client.filter_and_rank_facilities = MagicMock(
        return_value=([sample_discovery_response.items[0]], 1)
    )

    await voice_message_handler(update, context)

    speech_client.transcribe_audio.assert_awaited_once_with(
        b"fake-ogg-opus-bytes",
        filename="query.mp3",
        content_type="audio/mpeg",
    )
    api_client.get_blood_banks.assert_awaited_once_with(city="Delhi", blood_group="O+")
    tts_kwargs = speech_client.synthesize_speech.call_args.kwargs
    assert tts_kwargs["language"] == "hi-IN"
    assert "रिपोर्टेड ब्लड बैंक" in tts_kwargs["text"]
    message.reply_voice.assert_awaited_once()


@pytest.mark.anyio
async def test_voice_handler_partial_and_unrecognized_queries() -> None:
    """Partial or unrecognized transcripts prompt user with interactive keyboards."""
    # Group only -> asks for city
    update1, msg1 = _make_voice_update()
    ctx1 = _make_context(speech_configured=True)
    ctx1.bot_data["speech_client"].transcribe_audio = AsyncMock(
        return_value=PrismaTranscriptionResult(transcript="I need AB negative blood")
    )
    await voice_message_handler(update1, ctx1)
    msg1.reply_text.assert_awaited_once()
    assert "Detected Blood Group: <b>AB-</b>" in msg1.reply_text.call_args.args[0]
    assert isinstance(msg1.reply_text.call_args.kwargs["reply_markup"], InlineKeyboardMarkup)

    # City only -> asks for blood group
    update2, msg2 = _make_voice_update()
    ctx2 = _make_context(speech_configured=True)
    ctx2.bot_data["speech_client"].transcribe_audio = AsyncMock(
        return_value=PrismaTranscriptionResult(transcript="Find blood bank in Lucknow")
    )
    await voice_message_handler(update2, ctx2)
    msg2.reply_text.assert_awaited_once()
    assert "Detected City: <b>Lucknow</b>" in msg2.reply_text.call_args.args[0]
    assert isinstance(msg2.reply_text.call_args.kwargs["reply_markup"], InlineKeyboardMarkup)

    # Unrecognized -> prompts guidance & blood group keyboard
    update3, msg3 = _make_voice_update()
    ctx3 = _make_context(speech_configured=True)
    ctx3.bot_data["speech_client"].transcribe_audio = AsyncMock(
        return_value=PrismaTranscriptionResult(transcript="Hello good morning")
    )
    await voice_message_handler(update3, ctx3)
    msg3.reply_text.assert_awaited_once()
    assert "couldn't identify both" in msg3.reply_text.call_args.args[0]

    # Empty transcript
    update4, msg4 = _make_voice_update()
    ctx4 = _make_context(speech_configured=True)
    ctx4.bot_data["speech_client"].transcribe_audio = AsyncMock(
        return_value=PrismaTranscriptionResult(transcript="   ")
    )
    await voice_message_handler(update4, ctx4)
    msg4.reply_text.assert_awaited_once()
    assert "couldn't hear clear speech" in msg4.reply_text.call_args.args[0]


@pytest.mark.anyio
async def test_voice_handler_resilience_on_stt_tts_and_api_errors(
    sample_discovery_response: BloodBankListResponse,
) -> None:
    """Handler gracefully degrades on STT failure, TTS failure, and Discovery API errors."""
    # 1. STT failure
    u1, m1 = _make_voice_update()
    c1 = _make_context(speech_configured=True)
    c1.bot_data["speech_client"].transcribe_audio = AsyncMock(
        side_effect=PrismaTranscriptionError("STT down")
    )
    await voice_message_handler(u1, c1)
    m1.reply_text.assert_awaited_once()
    assert "Could Not Process Voice Message" in m1.reply_text.call_args.args[0]

    # 2. TTS failure should NOT prevent sending discovery text results
    u2, m2 = _make_voice_update()
    c2 = _make_context(speech_configured=True)
    c2.bot_data["speech_client"].transcribe_audio = AsyncMock(
        return_value=PrismaTranscriptionResult(transcript="O+ in Delhi")
    )
    c2.bot_data["speech_client"].synthesize_speech = AsyncMock(
        side_effect=TimbreSynthesisError("TTS unavailable")
    )
    c2.bot_data["api_client"].get_blood_banks = AsyncMock(return_value=sample_discovery_response)
    c2.bot_data["api_client"].filter_and_rank_facilities = MagicMock(
        return_value=([sample_discovery_response.items[0]], 1)
    )
    await voice_message_handler(u2, c2)
    assert m2.reply_text.await_count == 2
    assert "AIIMS Main Blood Bank" in m2.reply_text.call_args_list[1].args[0]
    m2.reply_voice.assert_not_awaited()

    # 3. Discovery API error
    u3, m3 = _make_voice_update()
    c3 = _make_context(speech_configured=True)
    c3.bot_data["speech_client"].transcribe_audio = AsyncMock(
        return_value=PrismaTranscriptionResult(transcript="O+ in Delhi")
    )
    c3.bot_data["api_client"].get_blood_banks = AsyncMock(
        side_effect=DiscoveryApiError("Backend down")
    )
    await voice_message_handler(u3, c3)
    assert m3.reply_text.await_count == 2
    assert "Discovery Service Temporarily Unavailable" in m3.reply_text.call_args_list[1].args[0]


def test_build_bot_application_registers_voice_handler_and_speech_client() -> None:
    """Verify build_bot_application wires MessageHandler for voice/audio and stores speech_client."""
    cfg = BotConfig(
        bot_token="123456:TESTTOKEN",
        gnani=GnaniConfig(api_key="gnani-abc"),
    )
    app = build_bot_application(cfg)

    assert app.bot_data["speech_client"] is not None
    assert isinstance(app.bot_data["speech_client"], GnaniSpeechClient)

    handlers = app.handlers.get(0, [])
    assert any(isinstance(h, MessageHandler) for h in handlers)
