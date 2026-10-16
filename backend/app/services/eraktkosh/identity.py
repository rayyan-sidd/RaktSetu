import hashlib
import re
from typing import Final, Optional

PREFIX: Final[str] = "eraktkosh"
MAX_ID_LENGTH: Final[int] = 100

PLACEHOLDER_SLUGS: Final[set[str]] = {
    "",
    "-",
    "--",
    "---",
    "facility",
    "blood-bank",
    "unknown",
    "unspecified",
    "null",
    "none",
    "na",
}


def _slugify(text: str) -> str:
    """Normalize arbitrary string into a lower-case alphanumeric hyphenated slug."""
    # Convert non-alphanumeric chars to hyphens
    cleaned = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", cleaned).strip("-")


def is_placeholder_slug(slug: str) -> bool:
    """Check if a slug represents an empty or generic placeholder value."""
    if not slug:
        return True
    if re.fullmatch(r"[-]+", slug):
        return True
    return slug in PLACEHOLDER_SLUGS


def generate_facility_source_id(
    city: str,
    facility_name: Optional[str],
    locality: str,
    raw_address: Optional[str] = None,
) -> str:
    """Generate a stable, deterministic fallback identity slug for an e-RaktKosh facility.

    Format: eraktkosh:{norm_city}:{slugified_name}:{slugified_locality}

    Architectural Invariants & Safety:
    1. e-RaktKosh public responses do not expose an internal integer hospital ID.
    2. Identity is derived deterministically from the facility's canonical city,
       sanitized facility name, sanitized locality, and sanitized address where available.
    3. Never collapses different rows into a shared fallback merely because the facility name
       was missing or a placeholder. When a facility name is absent or a placeholder, the
       sanitized address material is used to construct a distinct, stable identity.
    4. Row numbers are never used as permanent IDs because row ordering can change across queries.
    5. The resulting slug is strictly capped at 100 characters to comply with the database
       `source_facility_id` column limit `String(100)`. If a candidate slug exceeds 100
       characters, it is truncated and appended with a deterministic 8-character SHA-256 hash.
    """
    city_slug = _slugify(city) or "unknown"
    loc_slug = _slugify(locality) or "unspecified"

    clean_name = (facility_name or "").strip()
    name_slug = _slugify(clean_name)

    # Never generate the same generic fallback (like 'facility') for different rows.
    # If the facility name is missing or generic, fall back to address material.
    if is_placeholder_slug(name_slug):
        clean_addr = (raw_address or "").strip()
        addr_slug = _slugify(clean_addr)
        if not is_placeholder_slug(addr_slug):
            name_slug = addr_slug
        else:
            # Deterministic hash fallback when only city/locality are present
            raw_material = f"{city}:{clean_name}:{locality}:{clean_addr}"
            h = hashlib.sha256(raw_material.encode("utf-8")).hexdigest()[:12]
            name_slug = f"unnamed-{h}"

    candidate = f"{PREFIX}:{city_slug}:{name_slug}:{loc_slug}"

    if len(candidate) <= MAX_ID_LENGTH:
        return candidate

    # For slugs exceeding 100 chars: keep prefix up to 90 chars and append 8-char SHA256
    hash_suffix = hashlib.sha256(candidate.encode("utf-8")).hexdigest()[:8]
    trimmed_prefix = candidate[: MAX_ID_LENGTH - 9].rstrip("-")
    return f"{trimmed_prefix}-{hash_suffix}"
