from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Final, Optional

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_ERAKTKOSH_SOURCE: Final[str] = "e-RaktKosh (MoHFW)"
STATUS_REPORTED_UNVERIFIED: Final[str] = "reported_unverified"

# Reference tuples matching RaktSetu domain model
SUPPORTED_CITIES: Final[tuple[str, ...]] = ("Delhi", "Lucknow")
SUPPORTED_BLOOD_GROUPS: Final[tuple[str, ...]] = (
    "A+",
    "A-",
    "B+",
    "B-",
    "AB+",
    "AB-",
    "O+",
    "O-",
)


class NormalizedStockRecord(BaseModel):
    """Validated, normalized stock record originating from an external source (e.g. e-RaktKosh).

    Preserves explicit provenance:
    - Never marked as 'demo' (which is reserved for synthetic test seed data).
    - Never marked as 'confirmed' or 'real-time' without direct hospital verification.
    - Explicitly distinguishes between source_reported_timestamp (external last-updated time)
      and retrieval_timestamp (time RaktSetu ingested/retrieved the record).
    """

    model_config = ConfigDict(frozen=True)

    facility_name: str = Field(
        ...,
        min_length=1,
        description="Cleaned canonical name of the blood bank or storage facility",
    )
    city: str = Field(
        ...,
        description="Normalized city name ('Delhi' or 'Lucknow')",
    )
    locality: str = Field(
        ...,
        description="Locality, district, or neighborhood area of the facility",
    )
    blood_group: str = Field(
        ...,
        description="Standard ABO/Rh blood group ('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-')",
    )
    blood_component: Optional[str] = Field(
        default=None,
        description="Specific blood component if reported (e.g. 'Whole Blood', 'Packed Red Blood Cells')",
    )
    units_reported: int = Field(
        ...,
        ge=0,
        description="Reported quantity of units (non-negative integer; not a physical guarantee)",
    )
    source_reported_timestamp: Optional[datetime] = Field(
        default=None,
        description="Timestamp reported by the external source, converted to UTC with tzinfo. None if absent in source.",
    )
    retrieval_timestamp: datetime = Field(
        ...,
        description="Timezone-aware UTC timestamp when RaktSetu parsed or retrieved the record",
    )
    source_name: str = Field(
        default=DEFAULT_ERAKTKOSH_SOURCE,
        description="Provenance attribution of data source",
    )
    verification_status: str = Field(
        default=STATUS_REPORTED_UNVERIFIED,
        description="Provenance status: strictly 'reported_unverified', never 'demo' or 'confirmed'",
    )


@dataclass(frozen=True)
class NormalizationResult:
    """Outcome of attempting to normalize a single external record."""

    is_valid: bool
    record: Optional[NormalizedStockRecord] = None
    errors: list[str] = field(default_factory=list)
    raw_input: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BatchNormalizationResult:
    """Outcome of normalizing a batch of external records."""

    valid_records: list[NormalizedStockRecord] = field(default_factory=list)
    invalid_records: list[NormalizationResult] = field(default_factory=list)
    duplicate_count: int = 0
