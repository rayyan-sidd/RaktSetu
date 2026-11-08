"""Configuration loader for Gnani AI speech services (Prisma STT and Timbre TTS)."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from dotenv import load_dotenv

REPO_ROOT: Path = Path(__file__).resolve().parents[3]
DEFAULT_ENV_PATH: Path = REPO_ROOT / ".env"

DEFAULT_GNANI_BASE_URL: str = "https://api.vachana.ai"
DEFAULT_STT_MODEL: str = "prisma-v3.0"
DEFAULT_STT_LANGUAGE_CODE: str = "indic-auto"
DEFAULT_STT_FORMAT: str = "transcribe"

DEFAULT_TTS_MODEL: str = "timbre-v3.0"
DEFAULT_TTS_VOICE: str = "Nalini"
DEFAULT_TTS_LANGUAGE: str = "hi-IN"
DEFAULT_TTS_SPEED: float = 1.0
DEFAULT_REQUEST_TIMEOUT: float = 15.0


@dataclass
class GnaniConfig:
    """Runtime configuration settings for Gnani AI speech services."""

    api_key: str = ""
    api_key_id: Optional[str] = None
    api_base_url: str = DEFAULT_GNANI_BASE_URL
    stt_model: str = DEFAULT_STT_MODEL
    stt_language_code: str = DEFAULT_STT_LANGUAGE_CODE
    stt_format: str = DEFAULT_STT_FORMAT
    tts_model: str = DEFAULT_TTS_MODEL
    tts_voice: str = DEFAULT_TTS_VOICE
    tts_language: str = DEFAULT_TTS_LANGUAGE
    tts_speed: float = DEFAULT_TTS_SPEED
    request_timeout: float = DEFAULT_REQUEST_TIMEOUT

    @property
    def is_configured(self) -> bool:
        """Return True if an API key or API key ID is available."""
        return bool((self.api_key_id and self.api_key_id.strip()) or (self.api_key and self.api_key.strip()))

    @property
    def auth_key(self) -> str:
        """Return the effective authentication key for X-API-Key-ID headers."""
        if self.api_key_id and self.api_key_id.strip():
            return self.api_key_id.strip()
        return self.api_key.strip()

    def __repr__(self) -> str:
        """Mask secrets to prevent accidental leakage in logs."""
        masked_key = "***" if self.auth_key else "NOT_SET"
        return (
            f"GnaniConfig(auth_key='{masked_key}', "
            f"api_base_url='{self.api_base_url}', "
            f"stt_model='{self.stt_model}', "
            f"stt_language_code='{self.stt_language_code}', "
            f"stt_format='{self.stt_format}', "
            f"tts_model='{self.tts_model}', "
            f"tts_voice='{self.tts_voice}', "
            f"tts_language='{self.tts_language}', "
            f"tts_speed={self.tts_speed}, "
            f"request_timeout={self.request_timeout})"
        )


def load_gnani_config(
    require_key: bool = False,
    env_file: Optional[Union[Path, str]] = None,
) -> GnaniConfig:
    """Load Gnani configuration from environment variables and repository-root .env.

    Args:
        require_key: If True, raises ValueError when no API key is set.
        env_file: Optional explicit path to a .env file (primarily for isolated testing).
    """
    target_env = Path(env_file) if env_file is not None else DEFAULT_ENV_PATH
    if target_env.is_file():
        load_dotenv(dotenv_path=target_env, override=False)

    api_key = os.getenv("GNANI_API_KEY", "").strip()
    api_key_id_env = os.getenv("GNANI_API_KEY_ID", "").strip()
    api_key_id = api_key_id_env if api_key_id_env else None

    if require_key and not (api_key or api_key_id):
        raise ValueError(
            "GNANI_API_KEY (or GNANI_API_KEY_ID) environment variable is not set. "
            "Please provide a valid Gnani AI key in your .env or shell environment."
        )

    api_base = os.getenv("GNANI_API_BASE_URL", DEFAULT_GNANI_BASE_URL).strip().rstrip("/")
    if not api_base:
        api_base = DEFAULT_GNANI_BASE_URL

    stt_model = os.getenv("GNANI_STT_MODEL", DEFAULT_STT_MODEL).strip() or DEFAULT_STT_MODEL
    stt_language_code = os.getenv("GNANI_STT_LANGUAGE_CODE", DEFAULT_STT_LANGUAGE_CODE).strip() or DEFAULT_STT_LANGUAGE_CODE
    stt_format = os.getenv("GNANI_STT_FORMAT", DEFAULT_STT_FORMAT).strip() or DEFAULT_STT_FORMAT

    tts_model = os.getenv("GNANI_TTS_MODEL", DEFAULT_TTS_MODEL).strip() or DEFAULT_TTS_MODEL
    tts_voice = os.getenv("GNANI_TTS_VOICE", DEFAULT_TTS_VOICE).strip() or DEFAULT_TTS_VOICE
    tts_language = os.getenv("GNANI_TTS_LANGUAGE", DEFAULT_TTS_LANGUAGE).strip() or DEFAULT_TTS_LANGUAGE

    speed_raw = os.getenv("GNANI_TTS_SPEED", str(DEFAULT_TTS_SPEED)).strip()
    try:
        tts_speed = float(speed_raw)
        if tts_speed <= 0:
            tts_speed = DEFAULT_TTS_SPEED
    except ValueError:
        tts_speed = DEFAULT_TTS_SPEED

    timeout_raw = os.getenv("GNANI_REQUEST_TIMEOUT", str(DEFAULT_REQUEST_TIMEOUT)).strip()
    try:
        request_timeout = float(timeout_raw)
        if request_timeout <= 0:
            request_timeout = DEFAULT_REQUEST_TIMEOUT
    except ValueError:
        request_timeout = DEFAULT_REQUEST_TIMEOUT

    return GnaniConfig(
        api_key=api_key,
        api_key_id=api_key_id,
        api_base_url=api_base,
        stt_model=stt_model,
        stt_language_code=stt_language_code,
        stt_format=stt_format,
        tts_model=tts_model,
        tts_voice=tts_voice,
        tts_language=tts_language,
        tts_speed=tts_speed,
        request_timeout=request_timeout,
    )
