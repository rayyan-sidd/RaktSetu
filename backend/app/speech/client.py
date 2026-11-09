"""Base HTTP client for Gnani AI speech API."""

import base64
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
    TimbreSynthesisError,
)
from backend.app.speech.prisma import PrismaTranscriptionResult
from backend.app.speech.timbre import TimbreAudioConfig, TimbreSynthesisResult


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

    async def synthesize_speech(
        self,
        text: str,
        voice: Optional[str] = None,
        model: Optional[str] = None,
        language: Optional[str] = None,
        speed: Optional[float] = None,
        audio_config: Optional[TimbreAudioConfig] = None,
    ) -> TimbreSynthesisResult:
        """Synthesize spoken audio from text using Gnani Timbre TTS.

        Args:
            text: Text content to synthesize into spoken audio.
            voice: Override configured Timbre voice (e.g. 'Nalini').
            model: Override configured Timbre model (e.g. 'timbre-v3.0', 'timbre-v2.5').
            language: Override target language code (e.g. 'hi-IN', 'en-IN').
            speed: Override speaking speed multiplier (default 1.0).
            audio_config: Audio container and encoding configuration.
        """
        cleaned_text = (text or "").strip()
        if not cleaned_text:
            raise TimbreSynthesisError("Cannot synthesize speech from empty text.")

        effective_audio = audio_config or TimbreAudioConfig()
        headers = self._get_headers(content_type="application/json")
        body: Dict[str, Any] = {
            "text": cleaned_text,
            "voice": voice or self.config.tts_voice,
            "model": model or self.config.tts_model,
            "language": language or self.config.tts_language,
            "speed": speed if speed is not None else self.config.tts_speed,
            "audio_config": effective_audio.to_dict(),
        }

        try:
            response = await self.client.post(
                "/api/v1/tts/inference",
                headers=headers,
                json=body,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            mapped = self._map_http_error(exc)
            if type(mapped) is GnaniApiError:
                raise TimbreSynthesisError(mapped.message, status_code=mapped.status_code) from exc
            raise mapped from exc
        except httpx.HTTPError as exc:
            raise self._map_http_error(exc) from exc

        resp_ct = response.headers.get("content-type", "").lower()
        audio_bytes: bytes

        if "application/json" in resp_ct:
            try:
                data = response.json()
            except ValueError as exc:
                raise TimbreSynthesisError(f"Invalid JSON payload from Timbre TTS: {exc}") from exc

            if isinstance(data, dict) and data.get("success") is False:
                err_msg = data.get("message") or str(data.get("detail") or "TTS synthesis failed")
                raise TimbreSynthesisError(f"Timbre TTS failed: {err_msg}")

            b64_audio = (
                data.get("audio")
                or data.get("audio_base64")
                or data.get("audio_content")
                if isinstance(data, dict)
                else None
            )
            if not b64_audio or not isinstance(b64_audio, str):
                raise TimbreSynthesisError("Timbre TTS returned JSON without audio data.")
            try:
                audio_bytes = base64.b64decode(b64_audio)
            except Exception as exc:
                raise TimbreSynthesisError(f"Failed to decode base64 audio from Timbre TTS: {exc}") from exc
            resolved_ct = effective_audio.default_content_type
        else:
            audio_bytes = response.content
            resolved_ct = resp_ct or effective_audio.default_content_type

        if not audio_bytes:
            raise TimbreSynthesisError("Timbre TTS returned empty audio bytes.")

        return TimbreSynthesisResult(
            audio_bytes=audio_bytes,
            content_type=resolved_ct,
            container=effective_audio.container,
            filename=effective_audio.default_filename,
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
