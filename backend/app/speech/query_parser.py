"""Deterministic parser for extracting blood bank search queries from transcribed speech."""

import re
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class ExtractedBloodQuery:
    """Structured blood discovery parameters extracted from natural language."""

    raw_text: str
    blood_group: Optional[str] = None
    city: Optional[str] = None

    @property
    def is_complete(self) -> bool:
        """Return True if both blood group and city were identified."""
        return self.blood_group is not None and self.city is not None

    @property
    def has_any(self) -> bool:
        """Return True if at least one search parameter was identified."""
        return self.blood_group is not None or self.city is not None


# Order matters: AB must be checked before A and B so 'AB+' does not match 'B+'.
_BLOOD_GROUP_PATTERNS: Tuple[Tuple[str, re.Pattern[str]], ...] = (
    # AB+
    (
        "AB+",
        re.compile(
            r"(?:\b(?:a\s*b|ab)\s*(?:\+|plus|pos(?:itive)?|\+\s*ve)\b"
            r"|(?:ए\s*बी|एबी)\s*(?:\+|पॉजिटिव|पॉज़िटिव|प्लस|धनात्मक))"
            r"|\b(?:a\s*b|ab)\s*\+",
            re.IGNORECASE,
        ),
    ),
    # AB-
    (
        "AB-",
        re.compile(
            r"(?:\b(?:a\s*b|ab)\s*(?:-|minus|neg(?:ative)?|-\s*ve)\b"
            r"|(?:ए\s*बी|एबी)\s*(?:-|नेगेटिव|माइनस|ऋणात्मक))"
            r"|\b(?:a\s*b|ab)\s*-",
            re.IGNORECASE,
        ),
    ),
    # O+
    (
        "O+",
        re.compile(
            r"(?:\b(?:o|oh|0)\s*(?:\+|plus|pos(?:itive)?|\+\s*ve)\b"
            r"|ओ\s*(?:\+|पॉजिटिव|पॉज़िटिव|प्लस|धनात्मक))"
            r"|\b(?:o|oh|0)\s*\+",
            re.IGNORECASE,
        ),
    ),
    # O-
    (
        "O-",
        re.compile(
            r"(?:\b(?:o|oh|0)\s*(?:-|minus|neg(?:ative)?|-\s*ve)\b"
            r"|ओ\s*(?:-|नेगेटिव|माइनस|ऋणात्मक))"
            r"|\b(?:o|oh|0)\s*-",
            re.IGNORECASE,
        ),
    ),
    # A+
    (
        "A+",
        re.compile(
            r"(?:\b(?:a)\s*(?:\+|plus|pos(?:itive)?|\+\s*ve)\b"
            r"|(?<![ए])ए\s*(?:\+|पॉजिटिव|पॉज़िटिव|प्लस|धनात्मक))"
            r"|(?<![a-zA-Z])a\s*\+",
            re.IGNORECASE,
        ),
    ),
    # A-
    (
        "A-",
        re.compile(
            r"(?:\b(?:a)\s*(?:-|minus|neg(?:ative)?|-\s*ve)\b"
            r"|(?<![ए])ए\s*(?:-|नेगेटिव|माइनस|ऋणात्मक))"
            r"|(?<![a-zA-Z])a\s*-",
            re.IGNORECASE,
        ),
    ),
    # B+
    (
        "B+",
        re.compile(
            r"(?:\b(?:b|be)\s*(?:\+|plus|pos(?:itive)?|\+\s*ve)\b"
            r"|बी\s*(?:\+|पॉजिटिव|पॉज़िटिव|प्लस|धनात्मक))"
            r"|(?<![a-zA-Z])b\s*\+",
            re.IGNORECASE,
        ),
    ),
    # B-
    (
        "B-",
        re.compile(
            r"(?:\b(?:b|be)\s*(?:-|minus|neg(?:ative)?|-\s*ve)\b"
            r"|बी\s*(?:-|नेगेटिव|माइनस|ऋणात्मक))"
            r"|(?<![a-zA-Z])b\s*-",
            re.IGNORECASE,
        ),
    ),
    # All blood groups
    (
        "All",
        re.compile(
            r"\b(?:all\s+(?:blood\s+)?groups?|any\s+blood(?:\s+group)?)\b"
            r"|(?:सभी\s+ब्लड\s+ग्रुप|कोई\s+भी\s+ब्लड)",
            re.IGNORECASE,
        ),
    ),
)

_DELHI_PATTERN = re.compile(
    r"\b(?:new\s+delhi|delhi|dilli|dehli)\b|(?:नई\s+दिल्ली|दिल्ली|दिलली)",
    re.IGNORECASE,
)
_LUCKNOW_PATTERN = re.compile(
    r"\b(?:lucknow|luckhnow|lko)\b|(?:लखनऊ|लखनउ)",
    re.IGNORECASE,
)
_ALL_CITIES_PATTERN = re.compile(
    r"\b(?:all\s+cities|both\s+cities|delhi\s+and\s+lucknow|lucknow\s+and\s+delhi)\b"
    r"|(?:दोनों\s+शहर|सभी\s+शहर)",
    re.IGNORECASE,
)


def extract_blood_query(text: str) -> ExtractedBloodQuery:
    """Extract normalized blood group and target city from natural language speech text.

    Supports English, Hinglish, and Hindi Devanagari transcripts.
    Deterministic and safe against partial/ambiguous matches.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return ExtractedBloodQuery(raw_text="")

    blood_group: Optional[str] = None
    for group_name, pattern in _BLOOD_GROUP_PATTERNS:
        if pattern.search(cleaned):
            blood_group = group_name
            break

    city: Optional[str] = None
    has_delhi = bool(_DELHI_PATTERN.search(cleaned))
    has_lucknow = bool(_LUCKNOW_PATTERN.search(cleaned))
    if _ALL_CITIES_PATTERN.search(cleaned) or (has_delhi and has_lucknow):
        city = "All"
    elif has_delhi:
        city = "Delhi"
    elif has_lucknow:
        city = "Lucknow"

    return ExtractedBloodQuery(
        raw_text=cleaned,
        blood_group=blood_group,
        city=city,
    )
