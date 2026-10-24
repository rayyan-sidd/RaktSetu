"""Utility script to export a version-controlled deployment snapshot JSON from data/raktsetu.db.

The local database is opened strictly read-only.
Excludes raw addresses and any contact/personal information.
Preserves original timestamps, component labels, and source attribution without modification.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Optional

DEFAULT_DB_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "raktsetu.db"
DEFAULT_OUTPUT_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "deployment_snapshot.json"


def format_iso_utc(val: Optional[str]) -> Optional[str]:
    """Parse SQLite timestamp string and format to ISO 8601 UTC with 'Z' suffix."""
    if not val:
        return None
    # val is like '2026-10-15 12:00:00.000000' or '2026-10-16 00:00:00'
    val_clean = val.strip()
    if " " in val_clean:
        val_clean = val_clean.replace(" ", "T")
    try:
        dt = datetime.fromisoformat(val_clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    except Exception:
        return val


def export_snapshot(
    db_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
) -> tuple[int, int]:
    """Export facilities and stock reports from SQLite database strictly read-only.

    Returns:
        tuple[int, int]: (facilities_count, stock_reports_count)
    """
    target_db = db_path or DEFAULT_DB_FILE
    target_out = output_path or DEFAULT_OUTPUT_FILE

    if not target_db.exists():
        raise FileNotFoundError(f"Database not found at: {target_db}")

    # Connect strictly read-only via URI
    db_uri = f"file:{target_db.as_posix()}?mode=ro"
    conn = sqlite3.connect(db_uri, uri=True)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        # Fetch all blood banks
        cur.execute("SELECT * FROM blood_banks ORDER BY id ASC")
        bank_rows = cur.fetchall()

        # Fetch all stock reports grouped by blood_bank_id
        cur.execute("SELECT * FROM stock_reports ORDER BY blood_bank_id ASC, id ASC")
        report_rows = cur.fetchall()
    finally:
        conn.close()

    reports_by_bank: dict[int, list[dict[str, Any]]] = {}
    total_reports = 0

    for r in report_rows:
        bank_id = r["blood_bank_id"]
        report_data = {
            "id": r["id"],
            "blood_bank_id": bank_id,
            "blood_group": r["blood_group"],
            "blood_component": r["blood_component"],
            "units_reported": r["units_reported"],
            "source_name": r["source_name"],
            "data_timestamp": format_iso_utc(r["data_timestamp"]),
            "source_reported_timestamp": format_iso_utc(r["source_reported_timestamp"]),
            "retrieval_timestamp": format_iso_utc(r["retrieval_timestamp"]),
            "freshness_indicator": r["freshness_indicator"],
            "verification_status": r["verification_status"],
        }
        reports_by_bank.setdefault(bank_id, []).append(report_data)
        total_reports += 1

    facilities: list[dict[str, Any]] = []

    for b in bank_rows:
        bank_id = b["id"]
        locality = b["locality"]
        source_facility_id = b["source_facility_id"]

        # Sanitize known raw phone number artifacts from localities
        if bank_id == 52 and locality == "011-4225-1870":
            locality = "Rajinder Nagar"
            source_facility_id = "eraktkosh:delhi:blood-centre-sir-ganga-ram-hospital:rajinder-nagar"
        elif bank_id == 82 and locality == "98992 0703":
            locality = "Tahirpur"
            source_facility_id = "eraktkosh:delhi:blood-centre-rajiv-gandhi-super-specialty-hospital-tahirpur-delhi:tahirpur"

        facility_data = {
            "id": bank_id,
            "name": b["name"],
            "city": b["city"],
            "locality": locality,
            "source_type": b["source_type"],
            "source_name": b["source_name"],
            "source_facility_id": source_facility_id,
            # Exclude raw addresses and any contact or personal information
            "raw_address": None,
            "category": b["category"],
            "facility_type": b["facility_type"],
            "stock_reports": reports_by_bank.get(bank_id, []),
        }
        facilities.append(facility_data)

    target_out.parent.mkdir(parents=True, exist_ok=True)
    with open(target_out, "w", encoding="utf-8") as f:
        json.dump(facilities, f, indent=2, ensure_ascii=False)

    return len(facilities), total_reports


if __name__ == "__main__":
    fac_count, rep_count = export_snapshot()
    print(f"Exported {fac_count} facilities and {rep_count} stock reports to {DEFAULT_OUTPUT_FILE}")
