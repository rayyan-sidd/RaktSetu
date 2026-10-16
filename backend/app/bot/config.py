"""Configuration loader for RaktSetu Telegram Bot."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class BotConfig:
    """Runtime configuration settings for RaktSetu Telegram Bot."""

    bot_token: str
    api_base_url: str = "http://127.0.0.1:8000"
    web_url: Optional[str] = None
    request_timeout: float = 10.0
    max_facilities: int = 5

    def __repr__(self) -> str:
        """Mask bot token in string representation to prevent accidental secret leakage."""
        masked_token = "***" if self.bot_token else "NOT_SET"
        return (
            f"BotConfig(bot_token='{masked_token}', "
            f"api_base_url='{self.api_base_url}', "
            f"web_url={self.web_url!r}, "
            f"request_timeout={self.request_timeout}, "
            f"max_facilities={self.max_facilities})"
        )


def load_bot_config(require_token: bool = True) -> BotConfig:
    """Load bot configuration from environment variables.

    Environment variables (such as TELEGRAM_BOT_TOKEN) must be set in the shell
    environment prior to launching the process (e.g. via PowerShell `$env:TELEGRAM_BOT_TOKEN="..."`
    or Bash `export TELEGRAM_BOT_TOKEN="..."`). Standalone Python processes in this project
    do not automatically read or inject `.env` files into environment variables.

    Args:
        require_token: If True, raises ValueError when TELEGRAM_BOT_TOKEN is missing or blank.
                       If False, allows empty token (useful in offline unit testing).
    """
    raw_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if require_token and not raw_token:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN environment variable is not set. "
            "Please provide a valid bot token from @BotFather."
        )

    api_base = os.getenv("RAKTSETU_API_BASE_URL", "http://127.0.0.1:8000").strip().rstrip("/")
    if not api_base:
        api_base = "http://127.0.0.1:8000"

    raw_web_url = os.getenv("RAKTSETU_WEB_URL", "").strip().rstrip("/")
    web_url = raw_web_url if raw_web_url else None

    return BotConfig(
        bot_token=raw_token,
        api_base_url=api_base,
        web_url=web_url,
    )
