import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.database import SessionLocal, init_db
from backend.app.models.blood_bank import BloodBank, StockReport

DEFAULT_SEED_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "demo" / "blood_banks.json"


def seed_demo_data(db: Session, seed_file_path: Optional[Path] = None) -> tuple[int, int]:
    """Seed the database with synthetic demo blood banks and stock reports if empty.

    Returns:
        tuple[int, int]: (seeded_blood_banks_count, seeded_stock_reports_count).
        If database already contains records, returns (0, 0) idempotently.
    """
    existing_banks_count = db.scalar(select(func.count(BloodBank.id))) or 0
    if existing_banks_count > 0:
        return 0, 0

    target_path = seed_file_path or DEFAULT_SEED_FILE
    if not target_path.exists():
        raise FileNotFoundError(f"Demo seed dataset file not found at: {target_path}")

    with open(target_path, "r", encoding="utf-8") as f:
        demo_banks_data = json.load(f)

    total_banks = 0
    total_stock_reports = 0

    for bank_item in demo_banks_data:
        bank = BloodBank(
            name=bank_item["name"],
            city=bank_item["city"],
            locality=bank_item["locality"],
            source_type="demo",
            source_name="Synthetic demo dataset",
        )
        db.add(bank)
        db.flush()  # Populate bank.id for stock reports and explicit demo ID
        bank.source_facility_id = f"demo:{bank.id}"
        db.flush()

        for report_item in bank_item.get("stock_reports", []):
            raw_ts = report_item["data_timestamp"]
            # Parse ISO 8601 UTC timestamp format
            dt = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))

            stock_report = StockReport(
                blood_bank_id=bank.id,
                blood_group=report_item["blood_group"],
                blood_component=report_item.get("blood_component", "Unspecified"),
                units_reported=report_item["units_reported"],
                source_name=report_item["source_name"],
                data_timestamp=dt,
                source_reported_timestamp=None,  # Legacy demo rows have no external source timestamp
                retrieval_timestamp=dt,
                freshness_indicator=None,
                verification_status=report_item["verification_status"],
            )
            db.add(stock_report)
            total_stock_reports += 1

        total_banks += 1

    db.commit()
    return total_banks, total_stock_reports


def main() -> None:
    """CLI entrypoint for explicit idempotent demo database seeding."""
    init_db()
    with SessionLocal() as db:
        existing = db.scalar(select(func.count(BloodBank.id))) or 0
        if existing > 0:
            print(f"[seed_demo] Database already populated ({existing} blood banks). Skipping seed (idempotent).")
            sys.exit(0)

        banks_count, stock_count = seed_demo_data(db)
        print(f"[seed_demo] Successfully seeded {banks_count} blood banks and {stock_count} stock reports.")


if __name__ == "__main__":
    main()
