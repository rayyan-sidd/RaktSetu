"""Custom exceptions for Gnani AI speech integration."""

from typing import Optional


class GnaniError(Exception):
    """Base exception for all Gnani speech integration errors."""

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class GnaniConfigurationError(GnaniError):
    """Raised when Gnani credentials or essential configuration settings are missing."""


class GnaniNetworkError(GnaniError):
    """Raised when communication with Gnani API fails due to network/transport issues."""


class GnaniTimeoutError(GnaniNetworkError):
    """Raised when a request to Gnani API exceeds the configured timeout."""


class GnaniAuthError(GnaniError):
    """Raised when Gnani API rejects credentials (HTTP 401/403)."""


class GnaniRateLimitError(GnaniError):
    """Raised when Gnani API rate limits requests (HTTP 429)."""


class GnaniApiError(GnaniError):
    """Raised when Gnani API responds with an unhandled 4xx or 5xx status code."""


class PrismaTranscriptionError(GnaniApiError):
    """Raised when Prisma STT fails to transcribe the audio payload."""


class TimbreSynthesisError(GnaniApiError):
    """Raised when Timbre TTS fails to synthesize speech audio."""
