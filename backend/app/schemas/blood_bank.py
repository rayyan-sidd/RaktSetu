from datetime import datetime, timezone
from typing import Any, Final, Optional
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

DEFAULT_DATA_NOTICE: Final[str] = (
    "All records are synthetic demonstration data and do not reflect real-time "
    "hospital inventory or guaranteed physical blood availability."
)


class StockReportRead(BaseModel):
    """Schema representing reported blood group stock inventory for a blood bank."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Unique database identifier for the stock report record", examples=[1])
    blood_bank_id: int = Field(description="Foreign key ID referencing the associated blood bank", examples=[1])
    blood_group: str = Field(
        description="Blood group label (e.g. A+, A-, B+, B-, AB+, AB-, O+, O-)",
        examples=["O+"],
    )
    blood_component: str = Field(
        default="Unspecified",
        description="Blood component (e.g. Whole Blood, Packed Red Blood Cells), or 'Unspecified' if unspecified/legacy",
        examples=["Whole Blood"],
    )
    units_reported: int = Field(
        description="Reported quantity of units in the record (snapshot, not an absolute guarantee of physical availability)",
        examples=[8],
    )
    source_name: str = Field(
        description="Provenance attribution for the data source",
        examples=["Synthetic demo dataset"],
    )
    data_timestamp: datetime = Field(
        description="ISO 8601 UTC timestamp when the record snapshot was captured (legacy field)",
        examples=["2026-10-15T12:00:00Z"],
    )
    source_reported_timestamp: Optional[datetime] = Field(
        default=None,
        description="Source-reported external update timestamp in UTC, or None if unavailable/badge",
        examples=["2026-10-15T12:00:00Z"],
    )
    retrieval_timestamp: Optional[datetime] = Field(
        default=None,
        description="Timezone-aware UTC timestamp when RaktSetu ingested the record",
        examples=["2026-10-16T00:00:00Z"],
    )
    freshness_indicator: Optional[str] = Field(
        default=None,
        description="Freshness marker (e.g. 'live_stock_badge' or 'source_timestamp')",
        examples=["source_timestamp"],
    )
    verification_status: str = Field(
        description="Verification level flag for the stock report",
        examples=["demo"],
    )

    @field_validator("data_timestamp", "source_reported_timestamp", "retrieval_timestamp", mode="after")
    @classmethod
    def ensure_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Attach explicit UTC timezone if naive or convert to UTC."""
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @field_serializer("data_timestamp")
    def serialize_utc_datetime(self, dt: datetime, _info: Any) -> str:
        """Serialize datetime to an unambiguous UTC ISO 8601 string with 'Z' suffix."""
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @field_serializer("source_reported_timestamp", "retrieval_timestamp")
    def serialize_optional_utc_datetime(self, dt: Optional[datetime], _info: Any) -> Optional[str]:
        """Serialize optional datetime to UTC ISO 8601 string with 'Z' suffix."""
        if dt is None:
            return None
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class BloodBankRead(BaseModel):
    """Schema representing a blood bank facility and its reported stock inventory."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Unique database identifier for the blood bank", examples=[1])
    name: str = Field(
        description="Name of the blood bank facility",
        examples=["Demo Central Blood Transfusion Facility"],
    )
    city: str = Field(
        description="City where the blood bank is situated (Delhi or Lucknow)",
        examples=["Delhi"],
    )
    locality: str = Field(
        description="Broad area or neighborhood locality of the facility",
        examples=["Connaught Place (Central Delhi)"],
    )
    source_type: str = Field(
        default="demo",
        description="Facility source classification: 'demo' or 'external_source'",
        examples=["demo"],
    )
    source_name: str = Field(
        default="Synthetic demo dataset",
        description="Attribution of facility data origin",
        examples=["Synthetic demo dataset"],
    )
    source_facility_id: Optional[str] = Field(
        default=None,
        description="Source-specific facility identity or deterministic fallback slug",
        examples=["demo:1"],
    )
    raw_address: Optional[str] = Field(
        default=None,
        description="Sanitized street address without sensitive contact info",
        examples=["Connaught Place, New Delhi 110001"],
    )
    category: Optional[str] = Field(
        default=None,
        description="Facility category (e.g. Govt., Private, Charitable/Vol)",
        examples=["Govt."],
    )
    facility_type: Optional[str] = Field(
        default=None,
        description="Facility classification (e.g. Blood Bank, BSU)",
        examples=["Blood Bank"],
    )
    stock_reports: list[StockReportRead] = Field(
        default_factory=list,
        description="List of snapshot stock reports associated with this blood bank",
    )


class BloodBankListResponse(BaseModel):
    """Envelope schema for blood bank discovery endpoint response."""

    items: list[BloodBankRead] = Field(
        description="List of matching blood banks and their snapshot stock reports",
    )
    count: int = Field(
        description="Total number of matching blood banks returned",
        examples=[8],
    )
    data_notice: str = Field(
        default=DEFAULT_DATA_NOTICE,
        description="Notice indicating data authenticity, synthetic origin, and non-guarantee of physical stock",
        examples=[DEFAULT_DATA_NOTICE],
    )
