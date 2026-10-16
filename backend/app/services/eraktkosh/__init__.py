"""e-RaktKosh data normalization and adapter foundation.

Provides pure normalization services for translating externally reported blood bank stock
records into RaktSetu's validated internal schema without network requests or database side effects.
"""

from backend.app.services.eraktkosh.client import (
    CITY_QUERY_CONFIG,
    DEFAULT_TIMEOUT_SECONDS,
    ERAKTKOSH_STOCK_URL,
    ERaktKoshClient,
    ERaktKoshRetrievalError,
)
from backend.app.services.eraktkosh.identity import generate_facility_source_id
from backend.app.services.eraktkosh.ingestion import (
    CityIngestionResult,
    ERaktKoshIngestionError,
    ingest_city_from_source,
    ingest_eraktkosh_city_payload,
)
from backend.app.services.eraktkosh.normalizer import (
    normalize_blood_group,
    normalize_city_and_locality,
    normalize_eraktkosh_batch,
    normalize_eraktkosh_record,
    parse_source_timestamp,
    parse_units,
)
from backend.app.services.eraktkosh.parser import (
    FRESHNESS_LIVE_BADGE,
    FRESHNESS_SOURCE_TIMESTAMP,
    ParsedAvailabilityItem,
    ParsedFacilityInfo,
    ParsedResponseResult,
    ParsedRowResult,
    clean_html_tags,
    parse_availability_html,
    parse_eraktkosh_response,
    parse_eraktkosh_row,
    parse_facility_html,
    parse_timestamp_field,
)
from backend.app.services.eraktkosh.types import (
    DEFAULT_ERAKTKOSH_SOURCE,
    STATUS_REPORTED_UNVERIFIED,
    SUPPORTED_BLOOD_GROUPS,
    SUPPORTED_CITIES,
    BatchNormalizationResult,
    NormalizationResult,
    NormalizedStockRecord,
)

__all__ = [
    "DEFAULT_ERAKTKOSH_SOURCE",
    "STATUS_REPORTED_UNVERIFIED",
    "SUPPORTED_BLOOD_GROUPS",
    "SUPPORTED_CITIES",
    "FRESHNESS_LIVE_BADGE",
    "FRESHNESS_SOURCE_TIMESTAMP",
    "ERAKTKOSH_STOCK_URL",
    "CITY_QUERY_CONFIG",
    "DEFAULT_TIMEOUT_SECONDS",
    "ERaktKoshClient",
    "ERaktKoshRetrievalError",
    "generate_facility_source_id",
    "CityIngestionResult",
    "ERaktKoshIngestionError",
    "ingest_eraktkosh_city_payload",
    "ingest_city_from_source",
    "NormalizedStockRecord",
    "NormalizationResult",
    "BatchNormalizationResult",
    "ParsedFacilityInfo",
    "ParsedAvailabilityItem",
    "ParsedRowResult",
    "ParsedResponseResult",
    "normalize_blood_group",
    "normalize_city_and_locality",
    "parse_units",
    "parse_source_timestamp",
    "normalize_eraktkosh_record",
    "normalize_eraktkosh_batch",
    "clean_html_tags",
    "parse_facility_html",
    "parse_availability_html",
    "parse_timestamp_field",
    "parse_eraktkosh_row",
    "parse_eraktkosh_response",
]
