"""Entrypoint and application factory for RaktSetu Telegram Bot."""

import sys
from typing import Optional

from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from backend.app.bot.client import DiscoveryApiClient
from backend.app.bot.config import BotConfig, load_bot_config
from backend.app.bot.handlers import (
    callback_query_handler,
    find_command,
    help_command,
    start_command,
    voice_message_handler,
)
from backend.app.speech.client import GnaniSpeechClient


def build_bot_application(
    config: BotConfig,
    client: Optional[DiscoveryApiClient] = None,
    speech_client: Optional[GnaniSpeechClient] = None,
) -> Application:
    """Build and configure the Telegram Bot Application instance."""
    api_client = client or DiscoveryApiClient(
        base_url=config.api_base_url,
        timeout=config.request_timeout,
    )
    gnani_client = speech_client or (
        GnaniSpeechClient(config=config.gnani)
        if config.gnani and config.gnani.is_configured
        else None
    )

    app = ApplicationBuilder().token(config.bot_token).build()

    # Store shared services in bot_data for handlers
    app.bot_data["config"] = config
    app.bot_data["api_client"] = api_client
    app.bot_data["speech_client"] = gnani_client

    # Register handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("find", find_command))
    app.add_handler(CallbackQueryHandler(callback_query_handler))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, voice_message_handler))

    return app


def main() -> None:
    """Run the RaktSetu Telegram Bot via long-polling."""
    try:
        config = load_bot_config(require_token=True)
    except ValueError as exc:
        print(f"Configuration Error: {exc}", file=sys.stderr)
        print("Configure TELEGRAM_BOT_TOKEN in your .env file or shell environment before running:", file=sys.stderr)
        print("  .env file: TELEGRAM_BOT_TOKEN=your_token_from_botfather", file=sys.stderr)
        print("  PowerShell: $env:TELEGRAM_BOT_TOKEN=\"your_token_from_botfather\"", file=sys.stderr)
        print("  Bash/Linux: export TELEGRAM_BOT_TOKEN=\"your_token_from_botfather\"", file=sys.stderr)
        sys.exit(1)

    print("Starting RaktSetu Telegram Discovery Bot...")
    print(f"Connecting to Discovery API at: {config.api_base_url}")
    if config.web_url:
        print(f"Web Console configured: {config.web_url}")
    if config.gnani and config.gnani.is_configured:
        print(
            f"Gnani AI Speech enabled (STT: {config.gnani.stt_model}, "
            f"TTS: {config.gnani.tts_model}/{config.gnani.tts_voice})"
        )
    else:
        print("Gnani AI Speech not configured (running in text-only discovery mode)")

    app = build_bot_application(config)
    print("Bot initialized successfully. Starting long polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
