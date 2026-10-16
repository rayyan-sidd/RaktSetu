"""Configuration loader for RaktSetu Telegram Bot."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from dotenv import load_dotenv

REPO_ROOT: Path = Path(__file__).resolve().parents[3]
DEFAULT_ENV_PATH: Path = REPO_ROOT / ".env"


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


def load_bot_config(
    require_token: bool = True,
    env_file: Optional[Union[Path, str]] = None,
) -> BotConfig:
    """Load bot configuration from environment variables and repository-root .env.

    Loads the repository-root `.env` file before reading environment variables,
    resolving the path relative to this source file so startup works when launched
    from any working directory. Uses `load_dotenv(..., override=False)` so existing
    shell environment variables take precedence over `.env`.

    Args:
        require_token: If True, raises ValueError when TELEGRAM_BOT_TOKEN is missing or blank.
                       If False, allows empty token (useful in offline unit testing).
        env_file: Optional explicit path to a .env file (primarily for isolated testing).
                  If None, defaults to the repository-root `.env` file.
    """
    target_env = Path(env_file) if env_file is not None else DEFAULT_ENV_PATH
    if target_env.is_file():
        load_dotenv(dotenv_path=target_env, override=False)

    raw_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if require_token and not raw_token:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN environment variable is not set. "
            "Please provide a valid bot token from @BotFather in your .env or shell environment."
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
