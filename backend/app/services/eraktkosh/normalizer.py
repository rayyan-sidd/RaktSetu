from datetime import datetime, timedelta, timezone
import re
from typing import Any, Final, Optional

from backend.app.services.eraktkosh.types import (
    DEFAULT_ERAKTKOSH_SOURCE,
    STATUS_REPORTED_UNVERIFIED,
    SUPPORTED_BLOOD_GROUPS,
    SUPPORTED_CITIES,
    BatchNormalizationResult,
    NormalizationResult,
    NormalizedStockRecord,
)

# Indian Standard Time (IST) offset is UTC+05:30
IST_TIMEZONE: Final[timezone] = timezone(timedelta(hours=5, minutes=30))

# Blood group normalization mapping table
# Maps diverse real-world / e-RaktKosh notation variants to canonical ABO/Rh labels
BLOOD_GROUP_NORMALIZATION_MAP: Final[dict[str, str]] = {
    # Standard labels
    "A+": "A+",
    "A-": "A-",
    "B+": "B+",
    "B-": "B-",
    "AB+": "AB+",
    "AB-": "AB-",
    "O+": "O+",
    "O-": "O-",
    # e-RaktKosh 'Ve' variants (case-insensitive)
    "A+VE": "A+",
    "A-VE": "A-",
    "B+VE": "B+",
    "B-VE": "B-",
    "AB+VE": "AB+",
    "AB-VE": "AB-",
    "O+VE": "O+",
    "O-VE": "O-",
    # Textual descriptor variants
    "A POSITIVE": "A+",
    "A NEGATIVE": "A-",
    "B POSITIVE": "B+",
    "B NEGATIVE": "B-",
    "AB POSITIVE": "AB+",
    "AB NEGATIVE": "AB-",
    "O POSITIVE": "O+",
    "O NEGATIVE": "O-",
    "A POS": "A+",
    "A NEG": "A-",
    "B POS": "B+",
    "B NEG": "B-",
    "AB POS": "AB+",
    "AB NEG": "AB-",
    "O POS": "O+",
    "O NEG": "O-",
}

# Delhi district variations mapped to canonical "Delhi"
DELHI_DISTRICT_SYNONYMS: Final[set[str]] = {
    "delhi",
    "new delhi",
    "central delhi",
    "north delhi",
    "south delhi",
    "east delhi",
    "west delhi",
    "north west delhi",
    "north east delhi",
    "south west delhi",
    "south east delhi",
    "shahdara",
}

# Timestamp parsing formats commonly seen on Indian public portals
TIMESTAMP_FORMATS: Final[tuple[str, ...]] = (
    "%d-%b-%Y %H:%M:%S",  # e.g. "15-Oct-2026 14:30:00"
    "%d-%b-%Y %H:%M",     # e.g. "15-Oct-2026 14:30"
    "%d/%m/%Y %H:%M:%S",  # e.g. "15/10/2026 14:30:00"
    "%d/%m/%Y %H:%M",     # e.g. "15/10/2026 14:30"
    "%d-%m-%Y %H:%M:%S",  # e.g. "15-10-2026 14:30:00"
    "%d-%m-%Y %H:%M",     # e.g. "15-10-2026 14:30"
    "%Y-%m-%d %H:%M:%S",  # e.g. "2026-10-15 14:30:00"
    "%Y-%m-%d %H:%M",     # e.g. "2026-10-15 14:30"
)


def normalize_blood_group(raw_group: Any) -> tuple[Optional[str], Optional[str]]:
    """Normalize raw blood group notation into canonical ABO/Rh representation.

    Returns:
        tuple[Optional[str], Optional[str]]: (normalized_blood_group, error_message)
    """
    if raw_group is None:
        return None, "Blood group is required and cannot be empty."

    cleaned = str(raw_group).strip().upper()
    if not cleaned:
        return None, "Blood group is required and cannot be empty."

    # Handle URL decoding anomaly where '+' becomes space (e.g. 'A ')
    if str(raw_group).endswith(" ") and cleaned in ("A", "B", "AB", "O"):
        cleaned = f"{cleaned}+"

    # Direct match or mapped synonym
    if cleaned in BLOOD_GROUP_NORMALIZATION_MAP:
        return BLOOD_GROUP_NORMALIZATION_MAP[cleaned], None

    # Handle internal spaces (e.g. 'A + VE' or 'O - VE')
    collapsed = re.sub(r"\s+", "", cleaned)
    if collapsed in BLOOD_GROUP_NORMALIZATION_MAP:
        return BLOOD_GROUP_NORMALIZATION_MAP[collapsed], None

    valid_groups = ", ".join(SUPPORTED_BLOOD_GROUPS)
    return None, f"Unsupported or invalid blood group '{raw_group}'. Supported groups: {valid_groups}."


def normalize_city_and_locality(
    raw_city: Any,
    raw_locality: Any = None,
    raw_district: Any = None,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Normalize city name to supported cities ('Delhi' or 'Lucknow') and determine locality.

    Returns:
        tuple[Optional[str], Optional[str], Optional[str]]: (normalized_city, normalized_locality, error_message)
    """
    if raw_city is None:
        return None, None, "City is required and cannot be empty."

    cleaned_city = str(raw_city).strip()
    if not cleaned_city:
        return None, None, "City is required and cannot be empty."

    city_lower = cleaned_city.lower()
    district_lower = str(raw_district).strip().lower() if raw_district else ""
    locality_cleaned = str(raw_locality).strip() if raw_locality else ""

    # Check for Delhi and its constituent districts
    if city_lower in DELHI_DISTRICT_SYNONYMS or district_lower in DELHI_DISTRICT_SYNONYMS:
        canonical_city = "Delhi"
        if locality_cleaned:
            canonical_locality = locality_cleaned
        elif raw_district and str(raw_district).strip():
            canonical_locality = str(raw_district).strip().title()
        elif city_lower != "delhi":
            canonical_locality = cleaned_city.title()
        else:
            canonical_locality = "Delhi NCR"
        return canonical_city, canonical_locality, None

    # Check for Lucknow
    if city_lower == "lucknow" or "lucknow" in district_lower:
        canonical_city = "Lucknow"
        canonical_locality = locality_cleaned or "Lucknow Central"
        return canonical_city, canonical_locality, None

    valid_cities = ", ".join(SUPPORTED_CITIES)
    return None, None, f"Unsupported city '{raw_city}'. Only {valid_cities} are supported."


def parse_units(raw_units: Any) -> tuple[Optional[int], Optional[str]]:
    """Parse and validate reported stock unit quantity.

    Must parse to a non-negative integer. Does not invent quantities if missing.

    Returns:
        tuple[Optional[int], Optional[str]]: (units_integer, error_message)
    """
    if raw_units is None:
        return None, "Missing units_reported quantity."

    # If already integer or numeric float
    if isinstance(raw_units, (int, float)):
        if raw_units < 0:
            return None, f"Invalid units_reported: cannot be negative ({raw_units})."
        return int(raw_units), None

    units_str = str(raw_units).strip()
    if not units_str:
        return None, "Missing units_reported quantity."

    # Explicit negative check
    if units_str.startswith("-"):
        return None, f"Invalid units_reported: cannot be negative ({raw_units})."

    # Direct integer string conversion
    if units_str.isdigit():
        return int(units_str), None

    # Parse common formatted strings, e.g. "Available: 15 Units" or "12 Units"
    digits_matches = re.findall(r"\b\d+\b", units_str)
    if len(digits_matches) == 1:
        return int(digits_matches[0]), None

    return (
        None,
        f"Unparseable units_reported quantity '{raw_units}'. Must be a clear, non-negative integer.",
    )


def parse_source_timestamp(raw_timestamp: Any) -> tuple[Optional[datetime], Optional[str]]:
    """Parse source timestamp and convert to timezone-aware UTC datetime.

    If naive, assumes Indian Standard Time (IST, UTC+05:30) as used by e-RaktKosh.
    If absent/None, returns (None, None) without inventing a value.

    Returns:
        tuple[Optional[datetime], Optional[str]]: (utc_datetime, error_message)
    """
    if raw_timestamp is None:
        return None, None

    if isinstance(raw_timestamp, datetime):
        if raw_timestamp.tzinfo is None:
            # Assume IST for naive datetime
            return raw_timestamp.replace(tzinfo=IST_TIMEZONE).astimezone(timezone.utc), None
        return raw_timestamp.astimezone(timezone.utc), None

    ts_str = str(raw_timestamp).strip()
    if not ts_str:
        return None, None

    # 1. Try ISO 8601 parsing
    try:
        iso_clean = ts_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso_clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=IST_TIMEZONE)
        return dt.astimezone(timezone.utc), None
    except ValueError:
        pass

    # 2. Try common portal date/time formats
    for fmt in TIMESTAMP_FORMATS:
        try:
            naive_dt = datetime.strptime(ts_str, fmt)
            ist_dt = naive_dt.replace(tzinfo=IST_TIMEZONE)
            return ist_dt.astimezone(timezone.utc), None
        except ValueError:
            continue

    return None, f"Malformed source timestamp format '{raw_timestamp}'. Unable to parse date/time."


def normalize_eraktkosh_record(
    raw: dict[str, Any],
    retrieval_timestamp: Optional[datetime] = None,
) -> NormalizationResult:
    """Normalize a single raw record from e-RaktKosh into a validated NormalizedStockRecord.

    Args:
        raw: Dictionary containing raw fields from external record.
        retrieval_timestamp: Timestamp when RaktSetu ingested the record (defaults to current UTC).

    Returns:
        NormalizationResult: Contains validated record if valid, or list of error descriptions.
    """
    errors: list[str] = []

    # 1. Facility Name
    raw_name = raw.get("facility_name") or raw.get("name") or raw.get("blood_bank_name")
    if not raw_name or not str(raw_name).strip():
        errors.append("Facility name is required and cannot be empty.")
        clean_name = ""
    else:
        clean_name = str(raw_name).strip()

    # 2. City & Locality
    raw_city = raw.get("city") or raw.get("state")
    raw_locality = raw.get("locality") or raw.get("address")
    raw_district = raw.get("district")
    norm_city, norm_locality, city_err = normalize_city_and_locality(
        raw_city, raw_locality, raw_district
    )
    if city_err:
        errors.append(city_err)

    # 3. Blood Group
    raw_group = raw.get("blood_group")
    norm_group, group_err = normalize_blood_group(raw_group)
    if group_err:
        errors.append(group_err)

    # 4. Blood Component (Optional)
    raw_comp = raw.get("blood_component") or raw.get("component")
    clean_component: Optional[str] = str(raw_comp).strip() if raw_comp else None

    # 5. Units Reported
    raw_units = raw.get("units_reported") or raw.get("units") or raw.get("availability")
    norm_units, units_err = parse_units(raw_units)
    if units_err:
        errors.append(units_err)

    # 6. Source-Reported Timestamp
    raw_ts = (
        raw.get("source_reported_timestamp")
        or raw.get("last_updated")
        or raw.get("data_timestamp")
    )
    norm_ts, ts_err = parse_source_timestamp(raw_ts)
    if ts_err:
        errors.append(ts_err)

    # 7. RaktSetu Retrieval Timestamp (Guaranteed UTC)
    if retrieval_timestamp is None:
        rec_retrieval_ts = datetime.now(timezone.utc)
    else:
        rec_retrieval_ts = (
            retrieval_timestamp.astimezone(timezone.utc)
            if retrieval_timestamp.tzinfo
            else retrieval_timestamp.replace(tzinfo=timezone.utc)
        )

    # 8. Source Attribution
    source_name = str(raw.get("source_name") or DEFAULT_ERAKTKOSH_SOURCE).strip()

    if errors:
        return NormalizationResult(
            is_valid=False,
            record=None,
            errors=errors,
            raw_input=raw,
        )

    assert norm_city is not None
    assert norm_locality is not None
    assert norm_group is not None
    assert norm_units is not None

    record = NormalizedStockRecord(
        facility_name=clean_name,
        city=norm_city,
        locality=norm_locality,
        blood_group=norm_group,
        blood_component=clean_component,
        units_reported=norm_units,
        source_reported_timestamp=norm_ts,
        retrieval_timestamp=rec_retrieval_ts,
        source_name=source_name,
        verification_status=STATUS_REPORTED_UNVERIFIED,
    )

    return NormalizationResult(
        is_valid=True,
        record=record,
        errors=[],
        raw_input=raw,
    )


def normalize_eraktkosh_batch(
    records: list[dict[str, Any]],
    retrieval_timestamp: Optional[datetime] = None,
) -> BatchNormalizationResult:
    """Normalize a batch of raw e-RaktKosh records, validating and deduplicating them.

    Deduplication Policy:
        Records with identical (facility_name, city, blood_group, blood_component) are deduplicated.
        The record with the newest source_reported_timestamp is kept. If neither has a timestamp,
        the later record in the batch replaces the earlier one.

    Args:
        records: List of raw input record dictionaries.
        retrieval_timestamp: Ingestion timestamp.

    Returns:
        BatchNormalizationResult: Struct with validated records, invalid results, and duplicate count.
    """
    valid_map: dict[tuple[str, str, str, Optional[str]], NormalizedStockRecord] = {}
    invalid_records: list[NormalizationResult] = []
    duplicate_count = 0

    for raw in records:
        result = normalize_eraktkosh_record(raw, retrieval_timestamp=retrieval_timestamp)
        if not result.is_valid or result.record is None:
            invalid_records.append(result)
            continue

        rec = result.record
        dedup_key = (
            rec.facility_name.strip().lower(),
            rec.city,
            rec.blood_group,
            rec.blood_component.strip().lower() if rec.blood_component else None,
        )

        if dedup_key in valid_map:
            duplicate_count += 1
            existing = valid_map[dedup_key]
            # Keep the record with the newer source_reported_timestamp if available
            if rec.source_reported_timestamp and existing.source_reported_timestamp:
                if rec.source_reported_timestamp >= existing.source_reported_timestamp:
                    valid_map[dedup_key] = rec
            elif rec.source_reported_timestamp and not existing.source_reported_timestamp:
                valid_map[dedup_key] = rec
            else:
                # Latest in batch wins
                valid_map[dedup_key] = rec
        else:
            valid_map[dedup_key] = rec

    return BatchNormalizationResult(
        valid_records=list(valid_map.values()),
        invalid_records=invalid_records,
        duplicate_count=duplicate_count,
    )
