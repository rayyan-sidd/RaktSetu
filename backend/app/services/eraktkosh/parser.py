from dataclasses import dataclass, field
from datetime import datetime, timezone
import html
import re
from typing import Any, Final, Optional

from backend.app.services.eraktkosh.normalizer import (
    DEFAULT_ERAKTKOSH_SOURCE,
    STATUS_REPORTED_UNVERIFIED,
    normalize_blood_group,
    normalize_city_and_locality,
    normalize_eraktkosh_record,
    parse_source_timestamp,
)
from backend.app.services.eraktkosh.types import NormalizedStockRecord

# Contact-identifying patterns that must be stripped and never logged/retained
CONTACT_PATTERN: Final[re.Pattern] = re.compile(
    r"(?:[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)|"
    r"(?:(?:\+?\d{1,4}[- ]?)?\(?\d{2,5}\)?[- ]?\d{5,8})|"
    r"\b(?:phone|tel|telephone|mobile|mob|fax|email|contact|call)\b",
    re.IGNORECASE,
)


# Common pincode regex for Indian postal codes (6 digits)
PINCODE_PATTERN: Final[re.Pattern] = re.compile(r"\b\d{6}\b")

# Live stock badge identifier used by e-RaktKosh portals
LIVE_STOCK_BADGE_INDICATOR: Final[str] = "live_stock"
FRESHNESS_LIVE_BADGE: Final[str] = "live_stock_badge"
FRESHNESS_SOURCE_TIMESTAMP: Final[str] = "source_timestamp"

# Placeholders that must never be treated as facility names or addresses
PLACEHOLDER_VALUES: Final[set[str]] = {
    "-",
    "--",
    "---",
    ".",
    "..",
    "null",
    "none",
    "n/a",
    "na",
    "nil",
    "undefined",
    "not available",
}

ADDRESS_START_PATTERN: Final[re.Pattern] = re.compile(
    r"^(?:\d|plot\b|khasra\b|flat\b|shop\b|floor\b|1st\b|2nd\b|3rd\b|first\b|second\b|basement\b|house\b|building\b|room\b|block\b|sector\b|road\b|street\b|lane\b|near\b|opposite\b|opp\b|behind\b|u\d+/)",
    re.IGNORECASE,
)


def is_placeholder_text(text: str) -> bool:
    """Check if a string consists solely of placeholder indicators or delimiters."""
    cleaned = text.strip()
    if not cleaned:
        return True
    if re.fullmatch(r"[\s\-_.,/|:]+", cleaned):
        return True
    lower = cleaned.lower()
    return lower in PLACEHOLDER_VALUES


@dataclass(frozen=True)
class ParsedFacilityInfo:
    """Sanitized blood bank facility details extracted from source HTML.

    Crucially, contact information (phone numbers, email addresses, faxes) is stripped
    and never retained.
    """

    facility_name: str
    locality: str
    raw_address: str
    city: str


@dataclass(frozen=True)
class ParsedAvailabilityItem:
    """Individual blood group quantity parsed from source availability text."""

    blood_group: str  # Canonical ABO/Rh group (e.g. 'A+', 'O-')
    raw_group: str  # Original label in source (e.g. 'A+Ve')
    units: int  # Non-negative integer units reported


@dataclass(frozen=True)
class ParsedRowResult:
    """Parsed outcome of a single row from an e-RaktKosh response table."""

    serial_number: Optional[str]
    facility_info: Optional[ParsedFacilityInfo]
    category: Optional[str]
    facility_type: Optional[str]
    blood_component: Optional[str]
    is_available: bool
    availability_items: list[ParsedAvailabilityItem] = field(default_factory=list)
    source_reported_timestamp: Optional[datetime] = None
    has_live_badge: bool = False
    freshness_indicator: Optional[str] = None
    raw_timestamp_text: Optional[str] = None
    errors: list[str] = field(default_factory=list)
    raw_row: list[Any] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """A row is valid if it has valid facility info and no fatal parsing errors."""
        return self.facility_info is not None and len(self.errors) == 0


@dataclass(frozen=True)
class ParsedResponseResult:
    """Aggregate result from parsing a full e-RaktKosh JSON response."""

    total_records_reported: int
    rows_parsed: int
    successful_rows: list[ParsedRowResult] = field(default_factory=list)
    failed_rows: list[ParsedRowResult] = field(default_factory=list)
    normalized_records: list[NormalizedStockRecord] = field(default_factory=list)
    duplicate_count: int = 0


def clean_html_tags(raw_html: str) -> str:
    """Safely strip HTML tags and decode HTML character entities."""
    if not raw_html:
        return ""
    # Replace line breaks and paragraph closings with newlines
    converted = re.sub(r"(?i)<\s*br\s*/?>", "\n", raw_html)
    converted = re.sub(r"(?i)<\s*/p\s*>", "\n", converted)
    converted = re.sub(r"(?i)<\s*/div\s*>", "\n", converted)
    # Strip remaining tags
    stripped = re.sub(r"<[^>]+>", " ", converted)
    # Unescape HTML entities
    unescaped = html.unescape(stripped)
    # Normalize excessive internal whitespace
    return re.sub(r"[ \t]+", " ", unescaped).strip()


def extract_locality_from_address(address: str, default_city: str) -> str:
    """Extract a candidate locality name from a cleaned address string.

    Filters out pincodes, common city names, and country labels to isolate
    the neighborhood or sub-district. Falls back to default city if no specific
    locality is distinguishable.
    """
    if not address or not address.strip():
        return "Delhi NCR" if default_city.lower() == "delhi" else "Lucknow Central"

    # Split address by comma
    parts = [p.strip() for p in address.split(",") if p.strip()]
    if not parts:
        return default_city

    # Ignored geographic terms that do not constitute a specific locality
    ignored_terms = {
        "delhi",
        "new delhi",
        "uttar pradesh",
        "u.p.",
        "india",
        "lucknow",
    }

    meaningful_parts: list[str] = []
    for part in parts:
        # Skip pure pincodes or parts containing only pincode
        clean_part = PINCODE_PATTERN.sub("", part).strip()
        if not clean_part:
            continue
        if clean_part.lower() in ignored_terms:
            continue
        meaningful_parts.append(clean_part)

    if meaningful_parts:
        # Prefer the last specific sub-area or first available meaningful part
        if len(meaningful_parts) > 1:
            return meaningful_parts[-1]
        return meaningful_parts[0]

    return default_city


def parse_facility_html(
    raw_html: Any,
    default_city: str,
) -> tuple[Optional[ParsedFacilityInfo], Optional[str]]:
    """Parse facility name, locality, and address from e-RaktKosh HTML.

    Strips phone numbers, email addresses, and fax numbers without logging or storing.
    Skips placeholder lines (e.g. '-', '--', 'null', 'N/A').
    Preserves meaningful source text without inventing a facility name when the source
    only provides an address.

    Returns:
        tuple[Optional[ParsedFacilityInfo], Optional[str]]: (facility_info, error_message)
    """
    if raw_html is None:
        return None, "Facility info HTML is missing or null."

    html_str = str(raw_html).strip()
    if not html_str:
        return None, "Facility info HTML is empty."

    # Standardize line breaks
    standardized = re.sub(r"(?i)<\s*br\s*/?>", "\n", html_str)
    standardized = re.sub(r"(?i)<\s*/p\s*>", "\n", standardized)
    standardized = re.sub(r"(?i)<\s*/div\s*>", "\n", standardized)

    lines = standardized.split("\n")
    sanitized_lines: list[str] = []

    for raw_line in lines:
        cleaned_line = clean_html_tags(raw_line)
        if not cleaned_line:
            continue

        # Strip contact information (phone, email, fax, contact numbers)
        line_no_contact = CONTACT_PATTERN.sub("", cleaned_line).strip(" ,;:-")
        if not line_no_contact:
            continue

        # Skip placeholder lines
        if is_placeholder_text(line_no_contact):
            continue

        sanitized_lines.append(line_no_contact)

    if not sanitized_lines:
        return (
            None,
            "Facility info HTML contained no parseable facility name or address.",
        )


    # If multiple non-placeholder lines exist, line 0 is facility name, remainder is address
    if len(sanitized_lines) > 1:
        facility_name = sanitized_lines[0].strip(" ,;:-")
        address_lines = sanitized_lines[1:]
        raw_address = ", ".join(address_lines).strip(" ,;:-") if address_lines else facility_name
    else:
        # Exactly one meaningful line: evaluate whether it starts with a facility name or is address-only
        single_line = sanitized_lines[0].strip(" ,;:-")
        parts = [p.strip(" ,;:-") for p in single_line.split(",") if p.strip(" ,;:-")]

        if len(parts) > 1 and not ADDRESS_START_PATTERN.search(parts[0]):
            # Parts start with a plausible facility name (e.g. "Lady Hardinge Medical College", "Blood Centre main Hospital")
            if len(parts) > 1 and any(
                kw in parts[1].lower()
                for kw in ["campus", "hospital", "institute", "medical", "centre", "center"]
            ):
                facility_name = f"{parts[0]}, {parts[1]}"
                address_parts = parts[2:]
                raw_address = ", ".join(address_parts).strip(" ,;:-") if address_parts else facility_name
            else:
                facility_name = parts[0]
                address_parts = parts[1:]
                raw_address = ", ".join(address_parts).strip(" ,;:-") if address_parts else facility_name
        else:
            # Source only provided an address or single un-splittable text.
            # Invariant: Preserve meaningful source text without inventing a facility name.
            facility_name = single_line
            raw_address = single_line

    if not facility_name:
        return None, "Extracted facility name is empty."

    # Extract locality candidate
    raw_locality = extract_locality_from_address(raw_address, default_city)

    # Normalize city and locality against RaktSetu domain model
    norm_city, norm_locality, city_err = normalize_city_and_locality(
        default_city, raw_locality=raw_locality
    )
    if city_err or norm_city is None or norm_locality is None:
        return None, f"Failed to normalize city/locality: {city_err}"

    return (
        ParsedFacilityInfo(
            facility_name=facility_name,
            locality=norm_locality,
            raw_address=raw_address,
            city=norm_city,
        ),
        None,
    )



def parse_availability_html(
    raw_html: Any,
) -> tuple[bool, Optional[str], list[ParsedAvailabilityItem], list[str]]:
    """Parse stock availability HTML into component and individual group quantities.

    Handles both available listings (e.g. "Available, B+Ve:2, O+Ve:2") and
    unavailable messages (e.g. "Whole Blood Not Available Search for another Component").

    Returns:
        tuple[bool, Optional[str], list[ParsedAvailabilityItem], list[str]]:
        (is_available, component_name, parsed_items, errors)
    """
    errors: list[str] = []
    if raw_html is None:
        return False, None, [], ["Availability HTML is missing or null."]

    html_str = str(raw_html).strip()
    if not html_str:
        return False, None, [], ["Availability HTML is empty."]

    # 1. Extract embedded component name if tagged (e.g. <b>Whole Blood</b>)
    component_match = re.search(r"<b>\s*([^<]+?)\s*</b>", html_str)
    extracted_component: Optional[str] = None
    if component_match:
        extracted_component = clean_html_tags(component_match.group(1)).strip()

    # 2. Clean HTML text for semantic inspection
    clean_text = clean_html_tags(html_str)
    lower_text = clean_text.lower()

    # 3. Check for explicit unavailable-stock messages
    if "not available" in lower_text or "unavailable" in lower_text:
        # Verified unavailable: do not invent zero-stock quantities for unreported groups
        return False, extracted_component, [], []

    # 4. Check for availability indicator
    if "available" in lower_text:
        # Parse group:quantity pairs like "B+Ve:2" or "O+Ve: 5"
        pair_pattern = re.compile(r"([A-Za-z0-9\+\-]+)\s*:\s*(\d+)")
        matches = pair_pattern.findall(clean_text)

        items: list[ParsedAvailabilityItem] = []
        for raw_group, raw_units in matches:
            norm_group, group_err = normalize_blood_group(raw_group)
            if group_err or norm_group is None:
                errors.append(f"Ignored unrecognized blood group label '{raw_group}'.")
                continue

            try:
                units = int(raw_units)
                if units < 0:
                    errors.append(f"Invalid negative units '{units}' for group '{raw_group}'.")
                    continue
                items.append(
                    ParsedAvailabilityItem(
                        blood_group=norm_group,
                        raw_group=raw_group,
                        units=units,
                    )
                )
            except ValueError:
                errors.append(f"Unparseable units '{raw_units}' for group '{raw_group}'.")
                continue

        if not items and not errors:
            errors.append(
                "Availability text indicated available stock, but no valid blood group quantities were parsed."
            )

        return True, extracted_component, items, errors

    # Unrecognized availability structure
    errors.append(f"Unrecognized availability format: '{clean_text}'.")
    return False, extracted_component, [], errors


def parse_timestamp_field(
    raw_timestamp: Any,
) -> tuple[Optional[datetime], bool, Optional[str], Optional[str], Optional[str]]:
    """Parse source timestamp field, handling both IST date-times and live badges.

    If a live stock badge image is present, does NOT invent an exact timestamp.
    Preserves freshness indicator separately.

    Returns:
        tuple[Optional[datetime], bool, Optional[str], Optional[str], Optional[str]]:
        (source_reported_timestamp_utc, has_live_badge, freshness_indicator, raw_text, error)
    """
    if raw_timestamp is None:
        return None, False, None, None, None

    field_str = str(raw_timestamp).strip()
    if not field_str:
        return None, False, None, None, None

    # Check for live stock badge image (e.g. <img src='...live_stock.png'>)
    if LIVE_STOCK_BADGE_INDICATOR in field_str.lower():
        # Source indicates live stock status without providing an explicit datetime.
        # Invariant: Do NOT invent a timestamp or assume an exact update time.
        return None, True, FRESHNESS_LIVE_BADGE, "live_stock_badge", None

    # Strip any enclosing HTML tags
    cleaned_text = clean_html_tags(field_str)
    if not cleaned_text:
        return None, False, None, None, None

    # Parse source datetime into timezone-aware UTC
    utc_dt, err = parse_source_timestamp(cleaned_text)
    if err:
        return None, False, None, cleaned_text, err

    freshness = FRESHNESS_SOURCE_TIMESTAMP if utc_dt else None
    return utc_dt, False, freshness, cleaned_text, None


def parse_eraktkosh_row(
    row: Any,
    default_city: str,
    default_component: Optional[str] = None,
) -> ParsedRowResult:
    """Parse a single raw row from e-RaktKosh response.

    Expected structure:
    [serial_number, facility_info_html, category, availability_html, timestamp_field, facility_type]
    """
    if not isinstance(row, (list, tuple)):
        return ParsedRowResult(
            serial_number=None,
            facility_info=None,
            category=None,
            facility_type=None,
            blood_component=default_component,
            is_available=False,
            errors=[f"Expected row to be list or tuple, got {type(row).__name__}"],
            raw_row=[],
        )

    errors: list[str] = []

    # Safe element access
    sno = str(row[0]).strip() if len(row) > 0 and row[0] is not None else None
    raw_facility_html = row[1] if len(row) > 1 else None
    raw_category = row[2] if len(row) > 2 else None
    raw_availability_html = row[3] if len(row) > 3 else None
    raw_timestamp = row[4] if len(row) > 4 else None
    raw_facility_type = row[5] if len(row) > 5 else None

    # 1. Facility Information
    fac_info, fac_err = parse_facility_html(raw_facility_html, default_city=default_city)
    if fac_err:
        errors.append(fac_err)

    # 2. Category normalization (Govt., Private, Charitable/Vol, etc.)
    category: Optional[str] = None
    if raw_category is not None:
        clean_cat = str(raw_category).strip()
        if clean_cat and clean_cat.lower() != "null":
            category = clean_cat

    # 3. Facility Type (Blood Bank, BSU, etc.)
    facility_type: Optional[str] = None
    if raw_facility_type is not None:
        clean_type = str(raw_facility_type).strip()
        if clean_type and clean_type.lower() != "null":
            facility_type = clean_type

    # 4. Availability HTML
    is_avail, extracted_comp, avail_items, avail_errs = parse_availability_html(
        raw_availability_html
    )
    if avail_errs:
        errors.extend(avail_errs)

    # Resolve component
    effective_component = extracted_comp or default_component

    # 5. Timestamp and freshness
    src_ts, has_live, freshness, raw_ts_text, ts_err = parse_timestamp_field(raw_timestamp)
    if ts_err:
        errors.append(ts_err)

    return ParsedRowResult(
        serial_number=sno,
        facility_info=fac_info,
        category=category,
        facility_type=facility_type,
        blood_component=effective_component,
        is_available=is_avail,
        availability_items=avail_items,
        source_reported_timestamp=src_ts,
        has_live_badge=has_live,
        freshness_indicator=freshness,
        raw_timestamp_text=raw_ts_text,
        errors=errors,
        raw_row=list(row),
    )


def parse_eraktkosh_response(
    payload: Any,
    default_city: str,
    default_component: Optional[str] = None,
    retrieval_timestamp: Optional[datetime] = None,
) -> ParsedResponseResult:
    """Parse a full e-RaktKosh response into validated NormalizedStockRecord instances.

    Deduplicates records across the response safely, preferring newer source timestamps.
    Does not write to the database or modify application state.

    Args:
        payload: Dict containing 'data' list of rows, or directly a list of rows.
        default_city: Fallback city ('Delhi' or 'Lucknow').
        default_component: Fallback component if not explicitly in HTML (e.g. 'Whole Blood').
        retrieval_timestamp: Ingestion timestamp in UTC (defaults to current UTC).

    Returns:
        ParsedResponseResult: Struct with validated records, parsed rows, and metrics.
    """
    # Guarantee timezone-aware UTC retrieval timestamp
    if retrieval_timestamp is None:
        rec_retrieval_ts = datetime.now(timezone.utc)
    else:
        rec_retrieval_ts = (
            retrieval_timestamp.astimezone(timezone.utc)
            if retrieval_timestamp.tzinfo
            else retrieval_timestamp.replace(tzinfo=timezone.utc)
        )

    # Extract rows list
    total_reported = 0
    raw_rows: list[Any] = []

    if isinstance(payload, dict):
        total_reported = payload.get("recordsTotal") or payload.get("recordsFiltered") or 0
        raw_rows = payload.get("data", [])
        if not isinstance(raw_rows, list):
            raw_rows = []
    elif isinstance(payload, list):
        raw_rows = payload
        total_reported = len(raw_rows)
    else:
        return ParsedResponseResult(
            total_records_reported=0,
            rows_parsed=0,
            successful_rows=[],
            failed_rows=[],
            normalized_records=[],
            duplicate_count=0,
        )

    successful_rows: list[ParsedRowResult] = []
    failed_rows: list[ParsedRowResult] = []

    # Map for deduplication: (facility_name_lower, city, blood_group, component_lower) -> record
    valid_record_map: dict[tuple[str, str, str, Optional[str]], NormalizedStockRecord] = {}
    duplicate_count = 0

    for raw_row in raw_rows:
        row_result = parse_eraktkosh_row(
            row=raw_row,
            default_city=default_city,
            default_component=default_component,
        )

        if not row_result.is_valid or row_result.facility_info is None:
            failed_rows.append(row_result)
            continue

        successful_rows.append(row_result)

        # If stock is available and group quantities exist, create NormalizedStockRecord
        if row_result.is_available and row_result.availability_items:
            for item in row_result.availability_items:
                raw_record_dict = {
                    "facility_name": row_result.facility_info.facility_name,
                    "city": row_result.facility_info.city,
                    "locality": row_result.facility_info.locality,
                    "blood_group": item.blood_group,
                    "blood_component": row_result.blood_component,
                    "units_reported": item.units,
                    "source_reported_timestamp": row_result.source_reported_timestamp,
                    "source_name": DEFAULT_ERAKTKOSH_SOURCE,
                }

                norm_result = normalize_eraktkosh_record(
                    raw_record_dict,
                    retrieval_timestamp=rec_retrieval_ts,
                )

                if norm_result.is_valid and norm_result.record is not None:
                    rec = norm_result.record
                    dedup_key = (
                        rec.facility_name.strip().lower(),
                        rec.city,
                        rec.blood_group,
                        rec.blood_component.strip().lower() if rec.blood_component else None,
                    )

                    if dedup_key in valid_record_map:
                        duplicate_count += 1
                        existing = valid_record_map[dedup_key]
                        # Keep the one with newer source_reported_timestamp if available
                        if rec.source_reported_timestamp and existing.source_reported_timestamp:
                            if rec.source_reported_timestamp >= existing.source_reported_timestamp:
                                valid_record_map[dedup_key] = rec
                        elif rec.source_reported_timestamp and not existing.source_reported_timestamp:
                            valid_record_map[dedup_key] = rec
                        else:
                            valid_record_map[dedup_key] = rec
                    else:
                        valid_record_map[dedup_key] = rec

    return ParsedResponseResult(
        total_records_reported=total_reported or len(raw_rows),
        rows_parsed=len(raw_rows),
        successful_rows=successful_rows,
        failed_rows=failed_rows,
        normalized_records=list(valid_record_map.values()),
        duplicate_count=duplicate_count,
    )
