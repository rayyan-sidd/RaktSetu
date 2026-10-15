from datetime import datetime, timezone
from typing import Any, Final, Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, TypeDecorator, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base

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


class UTCDateTime(TypeDecorator):
    """DateTime type that guarantees timezone-aware UTC datetime instances across dialects (including SQLite)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_result_value(self, value: Optional[datetime], dialect: Any) -> Optional[datetime]:
        if value is not None:
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return value


class BloodBank(Base):
    """SQLAlchemy model representing a blood bank or storage center."""

    __tablename__ = "blood_banks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(50), nullable=False)
    locality: Mapped[str] = mapped_column(String(255), nullable=False)

    stock_reports: Mapped[list["StockReport"]] = relationship(
        "StockReport",
        back_populates="blood_bank",
        cascade="all, delete-orphan",
        order_by="StockReport.blood_group",
    )

    __table_args__ = (
        CheckConstraint(
            f"city IN ({', '.join(repr(c) for c in SUPPORTED_CITIES)})",
            name="ck_blood_bank_city",
        ),
    )

    def __repr__(self) -> str:
        return f"<BloodBank(id={self.id}, name={self.name!r}, city={self.city!r}, locality={self.locality!r})>"


class StockReport(Base):
    """SQLAlchemy model representing an aggregated snapshot of reported units for a blood group."""

    __tablename__ = "stock_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    blood_bank_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("blood_banks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    blood_group: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    units_reported: Mapped[int] = mapped_column(Integer, nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    data_timestamp: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    verification_status: Mapped[str] = mapped_column(String(50), nullable=False)

    blood_bank: Mapped["BloodBank"] = relationship(
        "BloodBank",
        back_populates="stock_reports",
    )

    __table_args__ = (
        UniqueConstraint(
            "blood_bank_id",
            "blood_group",
            name="uq_blood_bank_blood_group",
        ),
        CheckConstraint(
            f"blood_group IN ({', '.join(repr(bg) for bg in SUPPORTED_BLOOD_GROUPS)})",
            name="ck_stock_report_blood_group",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<StockReport(id={self.id}, bank_id={self.blood_bank_id}, group={self.blood_group!r}, "
            f"units={self.units_reported}, source={self.source_name!r})>"
        )
