"""Command, callback query, and voice message handlers for RaktSetu Telegram Bot."""

import html
import io
import logging
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from backend.app.bot.client import DiscoveryApiClient, DiscoveryApiError
from backend.app.bot.config import BotConfig
from backend.app.bot.formatter import (
    format_api_error_message,
    format_discovery_results,
    format_empty_results,
    format_help_message,
    format_start_message,
    format_voice_error_message,
    format_voice_unconfigured_message,
    format_voice_unrecognized_message,
)
from backend.app.models.blood_bank import SUPPORTED_BLOOD_GROUPS, SUPPORTED_CITIES
from backend.app.speech.client import GnaniSpeechClient
from backend.app.speech.exceptions import GnaniError
from backend.app.speech.query_parser import extract_blood_query
from backend.app.speech.timbre import format_spoken_discovery_summary, is_valid_ogg_opus

logger = logging.getLogger(__name__)


def build_blood_group_keyboard() -> InlineKeyboardMarkup:
    """Build interactive inline keyboard for ABO/Rh blood group selection."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("A+", callback_data="group:A+"),
                InlineKeyboardButton("A-", callback_data="group:A-"),
                InlineKeyboardButton("B+", callback_data="group:B+"),
                InlineKeyboardButton("B-", callback_data="group:B-"),
            ],
            [
                InlineKeyboardButton("AB+", callback_data="group:AB+"),
                InlineKeyboardButton("AB-", callback_data="group:AB-"),
                InlineKeyboardButton("O+", callback_data="group:O+"),
                InlineKeyboardButton("O-", callback_data="group:O-"),
            ],
            [
                InlineKeyboardButton("All Blood Groups", callback_data="group:All"),
            ],
        ]
    )


def build_city_keyboard(blood_group: str) -> InlineKeyboardMarkup:
    """Build interactive inline keyboard for target city selection."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Delhi", callback_data=f"search:{blood_group}:Delhi"),
                InlineKeyboardButton("Lucknow", callback_data=f"search:{blood_group}:Lucknow"),
            ],
            [
                InlineKeyboardButton(
                    "Delhi & Lucknow (All)",
                    callback_data=f"search:{blood_group}:All",
                ),
            ],
            [
                InlineKeyboardButton("« Back to Blood Groups", callback_data="back:groups"),
            ],
        ]
    )


def _normalize_group(group: str) -> Optional[str]:
    """Validate and normalize user-provided blood group string."""
    cleaned = group.strip().upper()
    if cleaned == "ALL":
        return "All"
    if cleaned in SUPPORTED_BLOOD_GROUPS:
        return cleaned
    return None


def _normalize_city(city: str) -> Optional[str]:
    """Validate and normalize user-provided city string."""
    cleaned = city.strip().title()
    if cleaned.upper() in ("ALL", "BOTH", "ALL CITIES"):
        return "All"
    if cleaned in SUPPORTED_CITIES:
        return cleaned
    return None


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    if not update.effective_message:
        return
    config: Optional[BotConfig] = context.bot_data.get("config")
    web_url = config.web_url if config else None
    text = format_start_message(web_url=web_url)
    await update.effective_message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    if not update.effective_message:
        return
    config: Optional[BotConfig] = context.bot_data.get("config")
    web_url = config.web_url if config else None
    text = format_help_message(web_url=web_url)
    await update.effective_message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def execute_discovery_and_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    blood_group: Optional[str],
    city: Optional[str],
    is_callback: bool = False,
) -> None:
    """Execute discovery search via client and reply with clinical formatting."""
    config: BotConfig = context.bot_data.get("config") or BotConfig(bot_token="")
    client: DiscoveryApiClient = context.bot_data.get("api_client") or DiscoveryApiClient(
        base_url=config.api_base_url,
        timeout=config.request_timeout,
    )

    query_city = None if city in (None, "All") else city
    query_group = None if blood_group in (None, "All") else blood_group

    try:
        response = await client.get_blood_banks(city=query_city, blood_group=query_group)
        facilities, total_count = client.filter_and_rank_facilities(
            response,
            blood_group=query_group,
            max_facilities=config.max_facilities,
        )

        if not facilities:
            text = format_empty_results(
                blood_group=blood_group,
                city=city,
                web_url=config.web_url,
            )
        else:
            text = format_discovery_results(
                facilities=facilities,
                total_count=total_count,
                blood_group=blood_group,
                city=city,
                web_url=config.web_url,
            )
    except DiscoveryApiError:
        text = format_api_error_message()
    except Exception:
        text = format_api_error_message()

    if is_callback and update.callback_query and update.callback_query.message:
        await update.callback_query.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    elif update.effective_message:
        await update.effective_message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )


async def find_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /find command with optional direct arguments or interactive keyboard."""
    if not update.effective_message:
        return

    args = context.args or []

    # Case 1: Direct arguments provided e.g. /find O+ Delhi
    if len(args) >= 2:
        group_raw = args[0]
        city_raw = " ".join(args[1:])

        normalized_group = _normalize_group(group_raw)
        normalized_city = _normalize_city(city_raw)

        if not normalized_group:
            valid_groups = ", ".join(sorted(SUPPORTED_BLOOD_GROUPS))
            err_msg = (
                f"❌ Invalid blood group <code>{html.escape(group_raw)}</code>.\n"
                f"Supported groups: {valid_groups}, or <code>All</code>.\n\n"
                "Please select your blood group below:"
            )
            await update.effective_message.reply_text(
                err_msg,
                reply_markup=build_blood_group_keyboard(),
                parse_mode=ParseMode.HTML,
            )
            return

        if not normalized_city:
            valid_cities = ", ".join(sorted(SUPPORTED_CITIES))
            err_msg = (
                f"❌ Invalid city <code>{html.escape(city_raw)}</code>.\n"
                f"Supported cities: {valid_cities}, or <code>All</code>.\n\n"
                f"Select target city for group <b>{normalized_group}</b>:"
            )
            await update.effective_message.reply_text(
                err_msg,
                reply_markup=build_city_keyboard(normalized_group),
                parse_mode=ParseMode.HTML,
            )
            return

        await execute_discovery_and_reply(
            update,
            context,
            blood_group=normalized_group,
            city=normalized_city,
        )
        return

    # Case 2: Incomplete single argument provided
    if len(args) == 1:
        group_raw = args[0]
        normalized_group = _normalize_group(group_raw)
        if normalized_group:
            await update.effective_message.reply_text(
                f"🩸 Selected Blood Group: <b>{normalized_group}</b>\nNow choose target city:",
                reply_markup=build_city_keyboard(normalized_group),
                parse_mode=ParseMode.HTML,
            )
            return

    # Case 3: No arguments, interactive selection flow
    prompt = (
        "🩸 <b>Select Required Blood Group:</b>\n"
        "Choose an ABO/Rh blood group to discover reported hospital facilities:"
    )
    await update.effective_message.reply_text(
        prompt,
        reply_markup=build_blood_group_keyboard(),
        parse_mode=ParseMode.HTML,
    )


async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle interactive inline keyboard button clicks."""
    query = update.callback_query
    if not query:
        return

    await query.answer()
    data = query.data or ""

    if data.startswith("group:"):
        selected_group = data.split(":", 1)[1]
        grp_display = html.escape(selected_group if selected_group != "All" else "All Groups")
        await query.edit_message_text(
            f"🩸 Selected Blood Group: <b>{grp_display}</b>\n"
            "Now select target city to search:",
            reply_markup=build_city_keyboard(selected_group),
            parse_mode=ParseMode.HTML,
        )
        return

    if data == "back:groups":
        prompt = (
            "🩸 <b>Select Required Blood Group:</b>\n"
            "Choose an ABO/Rh blood group to discover reported hospital facilities:"
        )
        await query.edit_message_text(
            prompt,
            reply_markup=build_blood_group_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return

    if data.startswith("search:"):
        parts = data.split(":")
        if len(parts) >= 3:
            selected_group = parts[1]
            selected_city = parts[2]
            grp_display = html.escape(selected_group if selected_group != "All" else "All Groups")
            city_display = html.escape(selected_city if selected_city != "All" else "Delhi & Lucknow")

            await query.edit_message_text(
                f"⏳ Searching e-RaktKosh records for <b>{grp_display}</b> in <b>{city_display}</b>...",
                parse_mode=ParseMode.HTML,
            )

            await execute_discovery_and_reply(
                update,
                context,
                blood_group=selected_group,
                city=selected_city,
                is_callback=True,
            )


def _resolve_reply_language(
    transcript: str,
    detected_code: Optional[str],
    default_language: str = "hi-IN",
) -> str:
    """Choose response TTS language based on detected language or script heuristic."""
    if detected_code:
        lower = detected_code.lower()
        if lower.startswith("hi"):
            return "hi-IN"
        if lower.startswith("en"):
            return "en-IN"
    if any("\u0900" <= ch <= "\u097f" for ch in transcript):
        return "hi-IN"
    if transcript.isascii():
        return "en-IN"
    return default_language


def _format_audio_size_limit(max_bytes: int) -> str:
    """Return human-readable label for configured byte limit."""
    max_mb = max_bytes / (1024 * 1024)
    if max_mb >= 1:
        return f"{max_mb:.1f} MB"
    return f"{max(1, max_bytes // 1024)} KB"


async def voice_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming Telegram voice notes or audio messages via Gnani Prisma & Timbre."""
    message = update.effective_message
    if not message:
        return

    media = message.voice or message.audio
    if not media:
        return

    config: BotConfig = context.bot_data.get("config") or BotConfig(bot_token="")
    shared_speech_client: Optional[GnaniSpeechClient] = context.bot_data.get("speech_client")
    owns_client = False
    speech_client = shared_speech_client

    if speech_client is None and config.gnani and config.gnani.is_configured:
        speech_client = GnaniSpeechClient(config=config.gnani)
        owns_client = True

    if speech_client is None or not speech_client.config.is_configured:
        await message.reply_text(
            format_voice_unconfigured_message(),
            reply_markup=build_blood_group_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        max_bytes = speech_client.config.max_audio_bytes
        max_duration = speech_client.config.max_audio_duration_seconds
        media_duration = getattr(media, "duration", None)
        media_size = getattr(media, "file_size", None)

        if (
            isinstance(media_duration, (int, float))
            and not isinstance(media_duration, bool)
            and media_duration > max_duration
        ):
            await message.reply_text(
                f"⚠️ <b>Voice Message Too Long</b>\n\n"
                f"Please keep voice notes within <b>{max_duration} seconds</b>, "
                "or search directly using <code>/find</code>:",
                reply_markup=build_blood_group_keyboard(),
                parse_mode=ParseMode.HTML,
            )
            return

        if (
            isinstance(media_size, int)
            and not isinstance(media_size, bool)
            and media_size > max_bytes
        ):
            size_label = _format_audio_size_limit(max_bytes)
            await message.reply_text(
                f"⚠️ <b>Audio File Too Large</b>\n\n"
                f"Please send a voice note smaller than <b>{size_label}</b>, "
                "or search directly using <code>/find</code>:",
                reply_markup=build_blood_group_keyboard(),
                parse_mode=ParseMode.HTML,
            )
            return

        try:
            # 1. Download voice/audio bytes from Telegram
            tg_file = await context.bot.get_file(media.file_id)
            raw_audio = await tg_file.download_as_bytearray()
            audio_bytes = bytes(raw_audio)

            if len(audio_bytes) > max_bytes:
                size_label = _format_audio_size_limit(max_bytes)
                await message.reply_text(
                    f"⚠️ <b>Audio File Too Large</b>\n\n"
                    f"Please send a voice note smaller than <b>{size_label}</b>, "
                    "or search directly using <code>/find</code>:",
                    reply_markup=build_blood_group_keyboard(),
                    parse_mode=ParseMode.HTML,
                )
                return

            if message.voice:
                filename = "voice.ogg"
                content_type = getattr(media, "mime_type", None) or "audio/ogg"
            else:
                filename = getattr(media, "file_name", None) or "audio.mp3"
                content_type = getattr(media, "mime_type", None) or "audio/mpeg"

            # 2. Transcribe audio using Gnani Prisma STT
            transcription = await speech_client.transcribe_audio(
                audio_bytes,
                filename=filename,
                content_type=content_type,
            )
        except GnaniError as exc:
            logger.warning("Prisma voice transcription error: %s", exc)
            await message.reply_text(
                format_voice_error_message(),
                reply_markup=build_blood_group_keyboard(),
                parse_mode=ParseMode.HTML,
            )
            return
        except Exception as exc:
            logger.exception("Unexpected error processing Telegram voice note: %s", exc)
            await message.reply_text(
                format_voice_error_message(),
                reply_markup=build_blood_group_keyboard(),
                parse_mode=ParseMode.HTML,
            )
            return

        if transcription.is_empty:
            await message.reply_text(
                "🎙️ I couldn't hear clear speech in your voice note. "
                "Please try speaking again or use <code>/find</code>:",
                reply_markup=build_blood_group_keyboard(),
                parse_mode=ParseMode.HTML,
            )
            return

        parsed = extract_blood_query(transcription.transcript)
        safe_transcript = html.escape(transcription.transcript)

        # Case 1: Blood group unambiguous, city missing or ambiguous -> prompt for city
        if parsed.blood_group and not parsed.city:
            city_prompt = (
                "Multiple or negated cities mentioned. Please confirm the target city below:"
                if parsed.ambiguous_city
                else "Now choose target city:"
            )
            await message.reply_text(
                f"🗣️ <b>Heard:</b> \"<i>{safe_transcript}</i>\"\n"
                f"🩸 Detected Blood Group: <b>{html.escape(parsed.blood_group)}</b>\n"
                f"{city_prompt}",
                reply_markup=build_city_keyboard(parsed.blood_group),
                parse_mode=ParseMode.HTML,
            )
            return

        # Case 2: Blood group missing or ambiguous -> clarify via blood group keyboard
        if not parsed.blood_group:
            if parsed.ambiguous_blood_groups:
                groups_disp = ", ".join(html.escape(g) for g in parsed.ambiguous_blood_groups)
                city_note = (
                    f"\n📍 Detected City: <b>{html.escape(parsed.city if parsed.city != 'All' else 'Delhi & Lucknow')}</b>"
                    if parsed.city
                    else ""
                )
                await message.reply_text(
                    f"🗣️ <b>Heard:</b> \"<i>{safe_transcript}</i>\"{city_note}\n"
                    f"❓ Multiple blood groups mentioned (<b>{groups_disp}</b>).\n"
                    "Please choose the exact blood group you need below:",
                    reply_markup=build_blood_group_keyboard(),
                    parse_mode=ParseMode.HTML,
                )
            elif parsed.city:
                city_disp = html.escape(parsed.city if parsed.city != "All" else "Delhi & Lucknow")
                await message.reply_text(
                    f"🗣️ <b>Heard:</b> \"<i>{safe_transcript}</i>\"\n"
                    f"📍 Detected City: <b>{city_disp}</b>\n"
                    "Please choose the required blood group below:",
                    reply_markup=build_blood_group_keyboard(),
                    parse_mode=ParseMode.HTML,
                )
            else:
                await message.reply_text(
                    format_voice_unrecognized_message(transcription.transcript),
                    reply_markup=build_blood_group_keyboard(),
                    parse_mode=ParseMode.HTML,
                )
            return

        # Case 3: Both blood group and city unambiguously extracted -> query Discovery API
        grp_display = html.escape(parsed.blood_group if parsed.blood_group != "All" else "All Groups")
        city_display = html.escape(parsed.city if parsed.city != "All" else "Delhi & Lucknow")
        await message.reply_text(
            f"🗣️ <b>Heard:</b> \"<i>{safe_transcript}</i>\"\n"
            f"⏳ Searching e-RaktKosh records for <b>{grp_display}</b> in <b>{city_display}</b>...",
            parse_mode=ParseMode.HTML,
        )

        api_client: DiscoveryApiClient = context.bot_data.get("api_client") or DiscoveryApiClient(
            base_url=config.api_base_url,
            timeout=config.request_timeout,
        )
        query_city = None if parsed.city in (None, "All") else parsed.city
        query_group = None if parsed.blood_group in (None, "All") else parsed.blood_group

        try:
            response = await api_client.get_blood_banks(city=query_city, blood_group=query_group)
            facilities, total_count = api_client.filter_and_rank_facilities(
                response,
                blood_group=query_group,
                max_facilities=config.max_facilities,
            )

            if not facilities:
                text_reply = format_empty_results(
                    blood_group=parsed.blood_group,
                    city=parsed.city,
                    web_url=config.web_url,
                )
            else:
                text_reply = format_discovery_results(
                    facilities=facilities,
                    total_count=total_count,
                    blood_group=parsed.blood_group,
                    city=parsed.city,
                    web_url=config.web_url,
                )
        except DiscoveryApiError:
            await message.reply_text(
                format_api_error_message(),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            return
        except Exception:
            await message.reply_text(
                format_api_error_message(),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            return

        await message.reply_text(
            text_reply,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )

        # 3. Synthesize spoken voice summary with Gnani Timbre TTS (best-effort, OGG Opus only)
        reply_lang = _resolve_reply_language(
            transcription.transcript,
            transcription.detected_language_code,
            default_language=speech_client.config.tts_language,
        )
        fac_dicts = [f.model_dump() for f in facilities]
        spoken_text = format_spoken_discovery_summary(
            facilities=fac_dicts,
            total_count=total_count,
            blood_group=parsed.blood_group,
            city=parsed.city,
            language=reply_lang,
        )

        try:
            tts_result = await speech_client.synthesize_speech(
                text=spoken_text,
                language=reply_lang,
            )
            if not (tts_result.is_ogg_opus and is_valid_ogg_opus(tts_result.audio_bytes)):
                logger.warning(
                    "Skipping Telegram voice reply: Timbre TTS did not return valid OGG Opus "
                    "(container=%s, content_type=%s, filename=%s).",
                    tts_result.container,
                    tts_result.content_type,
                    tts_result.filename,
                )
            else:
                await message.reply_voice(
                    voice=io.BytesIO(tts_result.audio_bytes),
                    filename=tts_result.filename,
                    caption="🔊 Spoken summary (unverified reported stock — verify directly with hospital)",
                )
        except GnaniError as exc:
            logger.warning("Timbre TTS synthesis failed (text response already sent): %s", exc)
        except Exception as exc:
            logger.warning("Unexpected error sending Telegram voice reply: %s", exc)
    finally:
        if owns_client:
            await speech_client.aclose()
