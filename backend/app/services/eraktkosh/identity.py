import hashlib
import re
from typing import Final

PREFIX: Final[str] = "eraktkosh"
MAX_ID_LENGTH: Final[int] = 100


def _slugify(text: str) -> str:
    """Normalize arbitrary string into a lower-case alphanumeric hyphenated slug."""
    # Convert non-alphanumeric chars to hyphens
    cleaned = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", cleaned).strip("-")


def generate_facility_source_id(
    city: str,
    facility_name: str,
    locality: str,
) -> str:
    """Generate a stable, deterministic fallback identity slug for an e-RaktKosh facility.

    Format: eraktkosh:{norm_city}:{slugified_name}:{slugified_locality}

    Architectural Invariants & Limitations:
    1. e-RaktKosh public JSON response does not expose an internal integer hospital ID
       in its search results table rows.
    2. Therefore, identity is derived deterministically from the facility's canonical
       city, sanitized facility name, and sanitized locality.
    3. If a facility's name or address changes in the source portal HTML across crawls,
       a new identity slug may be generated.
    4. Two distinct facilities that share the exact same name and locality within the
       same city will map to the same slug. In practice, facilities within a locality
       possess distinct branch or hospital identifiers.
    5. The resulting slug is strictly capped at 100 characters to comply with the
       database `source_facility_id` column limit `String(100)`. If a candidate slug
       exceeds 100 characters, it is truncated and appended with a deterministic 8-character
       SHA-256 hash digest.
    """
    city_slug = _slugify(city) or "unknown"
    name_slug = _slugify(facility_name) or "facility"
    loc_slug = _slugify(locality) or "unspecified"

    candidate = f"{PREFIX}:{city_slug}:{name_slug}:{loc_slug}"

    if len(candidate) <= MAX_ID_LENGTH:
        return candidate

    # For slugs exceeding 100 chars: keep prefix up to 90 chars and append 8-char SHA256
    hash_suffix = hashlib.sha256(candidate.encode("utf-8")).hexdigest()[:8]
    trimmed_prefix = candidate[: MAX_ID_LENGTH - 9].rstrip("-")
    return f"{trimmed_prefix}-{hash_suffix}"
