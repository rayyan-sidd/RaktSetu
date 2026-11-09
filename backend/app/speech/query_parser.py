"""Deterministic parser for extracting blood bank search queries from transcribed speech."""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class ExtractedBloodQuery:
    """Structured blood discovery parameters extracted from natural language."""

    raw_text: str
    blood_group: Optional[str] = None
    city: Optional[str] = None
    ambiguous_blood_groups: Tuple[str, ...] = ()
    ambiguous_city: bool = False

    @property
    def is_complete(self) -> bool:
        """Return True if both blood group and city were unambiguously identified."""
        return self.blood_group is not None and self.city is not None

    @property
    def has_any(self) -> bool:
        """Return True if at least one search parameter was identified."""
        return self.blood_group is not None or self.city is not None


_NON_BLOOD_AFTER_MODIFIER = re.compile(
    r"^\s+(?:test|tests|report|reports|result|results|attitude|mindset|response|"
    r"sign|signs|case|cases|outcome|experience|feedback|reply|change|impact|"
    r"effect|note|way|thing|person|review|answer|comment|news|feeling|"
    r"approach|vibe|outlook|signal|number|value|score|trend|grade)\b",
    re.IGNORECASE,
)

_NON_REQUEST_BEFORE_A = re.compile(
    r"\b(?:have|has|had|is|was|are|were|being|been|with|like|quite|very|"
    r"give|gave|got|received|show|showed|shows|made|make|see|saw|seen)\s+$",
    re.IGNORECASE,
)

_BLOOD_CONTEXT_AFTER = re.compile(
    r"^\s+(?:blood|group|type|donor|donors|unit|units|chahiye|needed|required|mein|me|in|for|at|चाहिए)\b",
    re.IGNORECASE,
)


# Patterns are collected across ALL groups (never break early) and resolved by
# longest-span precedence so compound tokens like 'AB+' or 'O-positive' prevent
# shorter sub-matches like 'B+' or 'O-'.
_BLOOD_GROUP_PATTERNS: Tuple[Tuple[str, re.Pattern[str]], ...] = (
    # AB+ (word/compound and bare +)
    (
        "AB+",
        re.compile(
            r"\b(?:a\s*b|ab)(?:[\s-]+(?:\+\s*ve|plus|pos(?:itive)?)|\s*\+(?!\s*ve\b))"
            r"|(?:ए\s*बी|एबी)\s*(?:\+|पॉजिटिव|पॉज़िटिव|प्लस|धनात्मक)",
            re.IGNORECASE,
        ),
    ),
    # AB- (word/compound and safe bare -)
    (
        "AB-",
        re.compile(
            r"\b(?:a\s*b|ab)(?:[\s-]+(?:-\s*ve|minus|neg(?:ative)?)|\s*-(?![a-zA-Z0-9])(?!\s*(?:pos(?:itive)?|plus|grade)\b))"
            r"|(?:ए\s*बी|एबी)\s*(?:-|नेगेटिव|माइनस|ऋणात्मक)",
            re.IGNORECASE,
        ),
    ),
    # O+
    (
        "O+",
        re.compile(
            r"\b(?:o|oh|0)(?:[\s-]+(?:\+\s*ve|plus|pos(?:itive)?)|\s*\+(?!\s*ve\b))"
            r"|ओ\s*(?:\+|पॉजिटिव|पॉज़िटिव|प्लस|धनात्मक)",
            re.IGNORECASE,
        ),
    ),
    # O-
    (
        "O-",
        re.compile(
            r"\b(?:o|oh|0)(?:[\s-]+(?:-\s*ve|minus|neg(?:ative)?)|\s*-(?![a-zA-Z0-9])(?!\s*(?:pos(?:itive)?|plus|grade)\b))"
            r"|ओ\s*(?:-|नेगेटिव|माइनस|ऋणात्मक)",
            re.IGNORECASE,
        ),
    ),
    # A+
    (
        "A+",
        re.compile(
            r"\b(?:a)(?:[\s-]+(?:\+\s*ve|plus|pos(?:itive)?)|\s*\+(?!\s*ve\b))"
            r"|(?<![ए])ए\s*(?:\+|पॉजिटिव|पॉज़िटिव|प्लस|धनात्मक)",
            re.IGNORECASE,
        ),
    ),
    # A-
    (
        "A-",
        re.compile(
            r"\b(?:a)(?:[\s-]+(?:-\s*ve|minus|neg(?:ative)?)|\s*-(?![a-zA-Z0-9])(?!\s*(?:pos(?:itive)?|plus|grade)\b))"
            r"|(?<![ए])ए\s*(?:-|नेगेटिव|माइनस|ऋणात्मक)",
            re.IGNORECASE,
        ),
    ),
    # B+ (no bare 'be' to avoid matching English 'can it be positive')
    (
        "B+",
        re.compile(
            r"\b(?:b)(?:[\s-]+(?:\+\s*ve|plus|pos(?:itive)?)|\s*\+(?!\s*ve\b))"
            r"|बी\s*(?:\+|पॉजिटिव|पॉज़िटिव|प्लस|धनात्मक)",
            re.IGNORECASE,
        ),
    ),
    # B-
    (
        "B-",
        re.compile(
            r"\b(?:b)(?:[\s-]+(?:-\s*ve|minus|neg(?:ative)?)|\s*-(?![a-zA-Z0-9])(?!\s*(?:pos(?:itive)?|plus|grade)\b))"
            r"|बी\s*(?:-|नेगेटिव|माइनस|ऋणात्मक)",
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
    r"\b(?:all\s+cities|both\s+cities"
    r"|(?:new\s+delhi|delhi|dilli|dehli)\s+(?:and|or|ya|aur)\s+(?:lucknow|luckhnow|lko)"
    r"|(?:lucknow|luckhnow|lko)\s+(?:and|or|ya|aur)\s+(?:new\s+delhi|delhi|dilli|dehli))\b"
    r"|(?:दोनों\s+शहर|सभी\s+शहर|(?:दिल्ली|नई\s+दिल्ली)\s+(?:और|या)\s+लखनऊ|लखनऊ\s+(?:और|या)\s+(?:दिल्ली|नई\s+दिल्ली))",
    re.IGNORECASE,
)
_CITY_NEGATION_PATTERN = re.compile(
    r"\b(?:not|no|except|neither|don't\s+want|dont\s+want|nahi|nahin|mat)\s+"
    r"(?:in\s+|from\s+|for\s+|at\s+)?"
    r"(?:new\s+delhi|delhi|dilli|dehli|lucknow|luckhnow|lko)\b"
    r"|\b(?:new\s+delhi|delhi|dilli|dehli|lucknow|luckhnow|lko)\s+(?:nahi|nahin|not)\b"
    r"|(?:नहीं)\s+(?:नई\s+दिल्ली|दिल्ली|लखनऊ)"
    r"|(?:नई\s+दिल्ली|दिल्ली|लखनऊ)\s+(?:नहीं|मत)",
    re.IGNORECASE,
)


def _is_false_positive_a_phrase(text: str, start: int, end: int, matched_str: str) -> bool:
    """Filter out English grammar phrases like 'a positive test' or 'a negative report'."""
    if not re.match(r"^a\s+(?:pos(?:itive)?|neg(?:ative)?)$", matched_str.strip(), re.IGNORECASE):
        return False

    after = text[end:]
    if _NON_BLOOD_AFTER_MODIFIER.match(after):
        return True

    before = text[:start]
    if _NON_REQUEST_BEFORE_A.search(before) and not _BLOOD_CONTEXT_AFTER.match(after):
        return True

    return False


def extract_blood_query(text: str) -> ExtractedBloodQuery:
    """Extract normalized blood group and target city from natural language speech text.

    Supports English, Hinglish, and Hindi Devanagari transcripts.
    Fails closed (returns None and sets ambiguity flags) when contradictory
    or multiple distinct blood groups or cities are detected.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return ExtractedBloodQuery(raw_text="")

    # 1. Collect all candidate blood-group match spans
    candidates: List[Tuple[int, int, str]] = []
    for group_name, pattern in _BLOOD_GROUP_PATTERNS:
        for match in pattern.finditer(cleaned):
            start, end = match.span()
            if group_name in ("A+", "A-") and _is_false_positive_a_phrase(
                cleaned, start, end, match.group(0)
            ):
                continue
            candidates.append((start, end, group_name))

    # Resolve overlaps by longest span first, then earliest start
    candidates.sort(key=lambda item: (-(item[1] - item[0]), item[0]))
    accepted: List[Tuple[int, int, str]] = []
    for start, end, group_name in candidates:
        overlaps = any(not (end <= a_start or start >= a_end) for a_start, a_end, _ in accepted)
        if not overlaps:
            accepted.append((start, end, group_name))

    # Re-order accepted matches left-to-right to preserve spoken order
    accepted.sort(key=lambda item: item[0])
    distinct_groups: List[str] = []
    for _, _, grp in accepted:
        if grp not in distinct_groups:
            distinct_groups.append(grp)

    blood_group: Optional[str] = None
    ambiguous_groups: Tuple[str, ...] = ()
    if len(distinct_groups) == 1:
        blood_group = distinct_groups[0]
    elif len(distinct_groups) > 1:
        ambiguous_groups = tuple(distinct_groups)

    # 2. Extract and validate city without collapsing negated/contradictory mentions
    city: Optional[str] = None
    ambiguous_city = False
    has_delhi = bool(_DELHI_PATTERN.search(cleaned))
    has_lucknow = bool(_LUCKNOW_PATTERN.search(cleaned))
    has_city_negation = bool(_CITY_NEGATION_PATTERN.search(cleaned))

    if has_city_negation and (has_delhi or has_lucknow):
        ambiguous_city = True
    elif _ALL_CITIES_PATTERN.search(cleaned):
        city = "All"
    elif has_delhi and has_lucknow:
        # Both cities mentioned without explicit conjunction ("and"/"or"/"ya") -> clarify
        ambiguous_city = True
    elif has_delhi:
        city = "Delhi"
    elif has_lucknow:
        city = "Lucknow"

    return ExtractedBloodQuery(
        raw_text=cleaned,
        blood_group=blood_group,
        city=city,
        ambiguous_blood_groups=ambiguous_groups,
        ambiguous_city=ambiguous_city,
    )
