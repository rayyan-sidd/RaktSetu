from datetime import datetime, timezone
from typing import Any, Final
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
    units_reported: int = Field(
        description="Reported quantity of units in the record (snapshot, not an absolute guarantee of physical availability)",
        examples=[8],
    )
    source_name: str = Field(
        description="Provenance attribution for the data source",
        examples=["Synthetic demo dataset"],
    )
    data_timestamp: datetime = Field(
        description="ISO 8601 UTC timestamp when the record snapshot was captured",
        examples=["2026-10-15T12:00:00Z"],
    )
    verification_status: str = Field(
        description="Verification level flag for the stock report",
        examples=["demo"],
    )

    @field_validator("data_timestamp", mode="after")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        """Attach explicit UTC timezone if naive or convert to UTC."""
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @field_serializer("data_timestamp")
    def serialize_utc_datetime(self, dt: datetime, _info: Any) -> str:
        """Serialize datetime to an unambiguous UTC ISO 8601 string with 'Z' suffix."""
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
