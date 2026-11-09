"""Timbre Text-to-Speech (TTS) models and spoken summary helpers."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class TimbreAudioConfig:
    """Output audio container and codec configuration for Gnani Timbre TTS."""

    container: str = "ogg"
    encoding: Optional[str] = "oggopus"
    sample_rate: int = 48000
    num_channels: int = 1
    sample_width: int = 2

    def to_dict(self) -> Dict[str, Any]:
        """Serialize audio configuration for the Timbre inference API."""
        payload: Dict[str, Any] = {
            "container": self.container,
            "sample_rate": self.sample_rate,
            "num_channels": self.num_channels,
        }
        if self.encoding and self.container.lower() != "mp3":
            payload["encoding"] = self.encoding
        if self.container.lower() in ("wav", "raw"):
            payload["sample_width"] = self.sample_width
        return payload

    @property
    def default_content_type(self) -> str:
        """Return standard MIME type for the configured container."""
        mapping = {
            "ogg": "audio/ogg",
            "wav": "audio/wav",
            "mp3": "audio/mpeg",
        }
        return mapping.get(self.container.lower(), "application/octet-stream")

    @property
    def default_filename(self) -> str:
        """Return filename with appropriate extension."""
        ext = self.container.lower() or "ogg"
        return f"raktsetu_reply.{ext}"


@dataclass
class TimbreSynthesisResult:
    """Encapsulates synthesized speech audio returned by Gnani Timbre TTS."""

    audio_bytes: bytes
    content_type: str
    container: str
    filename: str


def _sanitize_spoken_text(text: str) -> str:
    """Normalize text for clean TTS narration without special markup."""
    # Replace blood group shorthand + and - with spoken words for clear pronunciation
    cleaned = text.replace("AB+", "A B positive").replace("AB-", "A B negative")
    cleaned = cleaned.replace("O+", "O positive").replace("O-", "O negative")
    cleaned = cleaned.replace("A+", "A positive").replace("A-", "A negative")
    cleaned = cleaned.replace("B+", "B positive").replace("B-", "B negative")
    return " ".join(cleaned.split())


def format_spoken_discovery_summary(
    facilities: List[Dict[str, Any]],
    total_count: int,
    blood_group: Optional[str] = None,
    city: Optional[str] = None,
    language: str = "en-IN",
    max_spoken_facilities: int = 3,
) -> str:
    """Build a concise, natural-sounding spoken summary of blood bank discovery results.

    Includes mandatory safety verification guidance without HTML tags or raw symbols.
    """
    group_label = blood_group if blood_group and blood_group != "All" else "all blood groups"
    city_label = city if city and city != "All" else "Delhi and Lucknow"

    is_hindi = language.lower().startswith("hi")

    if not facilities:
        if is_hindi:
            msg = (
                f"{city_label} में {group_label} के लिए अभी कोई सक्रिय रिपोर्टेड ब्लड बैंक स्टॉक नहीं मिला। "
                "कृपया सीधे नजदीकी अस्पताल के ब्लड बैंक या ई-रक्तकोश पोर्टल से संपर्क करें।"
            )
        else:
            msg = (
                f"No active reported blood bank stock was found for {group_label} in {city_label}. "
                "Please contact nearby hospital blood banks directly or check e-RaktKosh."
            )
        return _sanitize_spoken_text(msg)

    top_facilities = facilities[:max_spoken_facilities]
    facility_descriptions: List[str] = []

    for idx, fac in enumerate(top_facilities, start=1):
        name = fac.get("name", "Unnamed blood bank")
        fac_city = fac.get("city", "")
        reports = fac.get("stock_reports") or []

        # Summarize stock if matching group or available
        stock_note = ""
        matching_units = None
        for r in reports:
            if not blood_group or blood_group == "All" or r.get("blood_group") == blood_group:
                units = r.get("units_reported")
                if units is not None and units > 0:
                    matching_units = units
                    break

        if matching_units is not None:
            if is_hindi:
                stock_note = f", {matching_units} यूनिट उपलब्ध"
            else:
                stock_note = f" with {matching_units} units reported"

        loc_part = f" ({fac_city})" if fac_city and city in (None, "All") else ""
        facility_descriptions.append(f"{idx}. {name}{loc_part}{stock_note}")

    facilities_joined = "; ".join(facility_descriptions)

    if is_hindi:
        summary = (
            f"{city_label} में {group_label} के लिए {total_count} रिपोर्टेड ब्लड बैंक मिले हैं। "
            f"प्रमुख केंद्र हैं: {facilities_joined}। "
            "ध्यान दें, यह केवल रिपोर्टेड जानकारी है। कृपया जाने से पहले अस्पताल से सीधे पुष्टि अवश्य करें।"
        )
    else:
        summary = (
            f"Found {total_count} reported blood banks for {group_label} in {city_label}. "
            f"Top facilities: {facilities_joined}. "
            "Important notice: this stock information is unverified. Always call and confirm availability directly with the hospital before traveling."
        )

    return _sanitize_spoken_text(summary)
