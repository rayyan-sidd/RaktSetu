"""Base HTTP client for Gnani AI speech API."""

from types import TracebackType
from typing import Any, Dict, Optional, Type

import httpx

from backend.app.speech.config import GnaniConfig, load_gnani_config
from backend.app.speech.exceptions import (
    GnaniApiError,
    GnaniAuthError,
    GnaniConfigurationError,
    GnaniError,
    GnaniNetworkError,
    GnaniRateLimitError,
    GnaniTimeoutError,
    PrismaTranscriptionError,
)
from backend.app.speech.prisma import PrismaTranscriptionResult


class GnaniSpeechClient:
    """Asynchronous HTTP client for interacting with Gnani AI speech endpoints."""

    def __init__(
        self,
        config: Optional[GnaniConfig] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.config = config or load_gnani_config()
        self._custom_client = http_client is not None
        self._client: Optional[httpx.AsyncClient] = http_client

    @property
    def client(self) -> httpx.AsyncClient:
        """Lazily initialize and return the underlying httpx AsyncClient."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.api_base_url.rstrip("/"),
                timeout=httpx.Timeout(self.config.request_timeout),
            )
        return self._client

    def _get_headers(self, content_type: Optional[str] = None) -> Dict[str, str]:
        """Construct authentication and standard request headers."""
        if not self.config.is_configured:
            raise GnaniConfigurationError(
                "Gnani speech services are not configured. "
                "Please configure GNANI_API_KEY in your .env or shell environment."
            )

        headers = {
            "X-API-Key-ID": self.config.auth_key,
            "User-Agent": "RaktSetu-SpeechClient/1.0",
        }
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def _map_http_error(self, exc: Exception) -> GnaniError:
        """Map httpx exceptions to typed Gnani exceptions."""
        if isinstance(exc, httpx.TimeoutException):
            return GnaniTimeoutError(f"Gnani API request timed out: {exc}")
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            error_body = exc.response.text[:200]
            if status in (401, 403):
                return GnaniAuthError(
                    f"Gnani authentication failed ({status}): Invalid or unauthorized API key.",
                    status_code=status,
                )
            if status == 429:
                return GnaniRateLimitError(
                    f"Gnani rate limit exceeded ({status}). Please retry with backoff.",
                    status_code=status,
                )
            return GnaniApiError(
                f"Gnani API error ({status}): {error_body}",
                status_code=status,
            )
        if isinstance(exc, httpx.RequestError):
            return GnaniNetworkError(f"Gnani network connection error: {exc}")
        return GnaniError(f"Unexpected Gnani speech client error: {exc}")

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        filename: str = "voice.ogg",
        content_type: str = "audio/ogg",
        model: Optional[str] = None,
        language_code: Optional[str] = None,
        output_format: Optional[str] = None,
    ) -> PrismaTranscriptionResult:
        """Transcribe audio bytes using Gnani Prisma Speech-to-Text (STT).

        Args:
            audio_bytes: Raw binary content of the audio clip.
            filename: Filename hint for multipart upload (e.g. 'voice.ogg', 'audio.wav').
            content_type: MIME type of the audio payload.
            model: Override configured Prisma model (e.g. 'prisma-v3.0', 'prisma-v2.5').
            language_code: Override configured language hint (e.g. 'indic-auto', 'hi-IN', 'en-IN').
            output_format: Override output format ('transcribe', 'verbatim', etc.).
        """
        if not audio_bytes:
            raise PrismaTranscriptionError("Cannot transcribe empty audio payload.")

        headers = self._get_headers()
        files = {
            "audio_file": (filename, audio_bytes, content_type),
        }
        data = {
            "model": model or self.config.stt_model,
            "language_code": language_code or self.config.stt_language_code,
            "format": output_format or self.config.stt_format,
        }

        try:
            response = await self.client.post(
                "/stt/v3",
                headers=headers,
                files=files,
                data=data,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            mapped = self._map_http_error(exc)
            if type(mapped) is GnaniApiError:
                raise PrismaTranscriptionError(mapped.message, status_code=mapped.status_code) from exc
            raise mapped from exc
        except httpx.HTTPError as exc:
            raise self._map_http_error(exc) from exc
        except ValueError as exc:
            raise PrismaTranscriptionError(f"Invalid JSON response from Prisma STT: {exc}") from exc

        if not isinstance(payload, dict):
            raise PrismaTranscriptionError("Unexpected response format from Prisma STT.")

        if payload.get("success") is False:
            err_msg = payload.get("message") or str(payload.get("detail") or "Transcription failed")
            raise PrismaTranscriptionError(f"Prisma STT failed: {err_msg}")

        transcript = payload.get("transcript")
        if transcript is None:
            transcript = payload.get("text", "")

        return PrismaTranscriptionResult(
            transcript=str(transcript).strip(),
            detected_language_code=payload.get("detected_language_code"),
            request_id=payload.get("request_id"),
            processing_time=payload.get("processing_time"),
            raw_response=payload,
        )

    async def aclose(self) -> None:
        """Close the underlying HTTP client session if internally created."""
        if self._client is not None and not self._custom_client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "GnaniSpeechClient":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        await self.aclose()
