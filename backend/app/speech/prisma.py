"""Prisma Speech-to-Text (STT) models and response representations."""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class PrismaTranscriptionResult:
    """Encapsulates the transcription result from Gnani Prisma STT."""

    transcript: str
    detected_language_code: Optional[str] = None
    request_id: Optional[str] = None
    processing_time: Optional[float] = None
    raw_response: Optional[Dict[str, Any]] = None

    @property
    def is_empty(self) -> bool:
        """Return True if transcript contains no meaningful speech."""
        return not bool(self.transcript and self.transcript.strip())
