"""Deployment seeding service for RaktSetu.

Loads the version-controlled deployment snapshot into the database strictly when the
database is completely empty. Refuses to overwrite populated or partially initialized datasets.
"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.blood_bank import BloodBank, StockReport

logger = logging.getLogger(__name__)

DEFAULT_SNAPSHOT_FILE = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "data"
    / "deployment_snapshot.json"
)


def parse_iso_datetime(val: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 UTC timestamp string into timezone-aware UTC datetime."""
    if not val:
        return None
    clean = val.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(clean)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_database_completely_empty(db: Session) -> bool:
    """Check whether both blood_banks and stock_reports tables are completely empty."""
    banks_count = db.scalar(select(func.count(BloodBank.id))) or 0
    reports_count = db.scalar(select(func.count(StockReport.id))) or 0
    return banks_count == 0 and reports_count == 0


def seed_deployment_snapshot(
    db: Session,
    snapshot_path: Optional[Path] = None,
) -> tuple[int, int]:
    """Load deployment snapshot into database if and only if database is completely empty.

    Args:
        db: Active SQLAlchemy session.
        snapshot_path: Optional custom path to deployment snapshot JSON.

    Returns:
        tuple[int, int]: (seeded_facilities_count, seeded_stock_reports_count).
        If database is already populated or partially initialized, returns (0, 0).
    """
    banks_count = db.scalar(select(func.count(BloodBank.id))) or 0
    reports_count = db.scalar(select(func.count(StockReport.id))) or 0

    if banks_count > 0 or reports_count > 0:
        logger.info(
            "[RaktSetu Seeder] Database is not completely empty (found %d facilities, %d stock reports). "
            "Skipping snapshot initialization to preserve existing data.",
            banks_count,
            reports_count,
        )
        return 0, 0

    target_path = snapshot_path or DEFAULT_SNAPSHOT_FILE
    if not target_path.exists():
        logger.warning("[RaktSetu Seeder] Snapshot fixture file not found at: %s", target_path)
        return 0, 0

    with open(target_path, "r", encoding="utf-8") as f:
        facilities_data = json.load(f)

    total_banks = 0
    total_reports = 0

    for facility_item in facilities_data:
        bank = BloodBank(
            id=facility_item.get("id"),
            name=facility_item["name"],
            city=facility_item["city"],
            locality=facility_item["locality"],
            source_type=facility_item.get("source_type", "demo"),
            source_name=facility_item.get("source_name", "Synthetic demo dataset"),
            source_facility_id=facility_item.get("source_facility_id"),
            raw_address=None,  # Raw address strictly excluded from deployed snapshots
            category=facility_item.get("category"),
            facility_type=facility_item.get("facility_type"),
        )
        db.add(bank)
        db.flush()

        for report_item in facility_item.get("stock_reports", []):
            dt = parse_iso_datetime(report_item["data_timestamp"])
            src_dt = parse_iso_datetime(report_item.get("source_reported_timestamp"))
            ret_dt = parse_iso_datetime(report_item.get("retrieval_timestamp")) or dt

            stock_report = StockReport(
                id=report_item.get("id"),
                blood_bank_id=bank.id,
                blood_group=report_item["blood_group"],
                blood_component=report_item.get("blood_component", "Unspecified"),
                units_reported=report_item["units_reported"],
                source_name=report_item["source_name"],
                data_timestamp=dt,
                source_reported_timestamp=src_dt,
                retrieval_timestamp=ret_dt,
                freshness_indicator=report_item.get("freshness_indicator"),
                verification_status=report_item["verification_status"],
            )
            db.add(stock_report)
            total_reports += 1

        total_banks += 1

    db.commit()
    logger.info(
        "[RaktSetu Seeder] Successfully initialized database with %d facilities and %d stock reports.",
        total_banks,
        total_reports,
    )
    return total_banks, total_reports
