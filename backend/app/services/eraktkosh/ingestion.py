from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Final, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from backend.app.core.database import SessionLocal, init_db
from backend.app.models.blood_bank import BloodBank, StockReport
from backend.app.services.eraktkosh.client import ERaktKoshClient, ERaktKoshRetrievalError
from backend.app.services.eraktkosh.identity import (
    _slugify,
    generate_facility_source_id,
)
from backend.app.services.eraktkosh.parser import (
    ParsedResponseResult,
    ParsedRowResult,
    parse_eraktkosh_response,
)
from backend.app.services.eraktkosh.types import (
    DEFAULT_ERAKTKOSH_SOURCE,
    STATUS_REPORTED_UNVERIFIED,
    SUPPORTED_CITIES,
)

SOURCE_TYPE_EXTERNAL: Final[str] = "external_source"


class ERaktKoshIngestionError(Exception):
    """Raised when an error occurs during database ingestion or reconciliation."""

    pass


@dataclass(frozen=True)
class CityIngestionResult:
    """Outcome and telemetry metrics from ingesting an e-RaktKosh snapshot for a city."""

    city: str
    component: str
    retrieval_timestamp: datetime
    is_dry_run: bool
    source_rows_count: int
    successful_rows_count: int
    failed_rows_count: int
    facilities_created: int
    facilities_updated: int
    reports_upserted: int
    reports_withdrawn: int
    warnings: list[str] = field(default_factory=list)


def ingest_eraktkosh_city_payload(
    db: Session,
    city: str,
    payload: dict[str, Any],
    component: str = "Whole Blood",
    apply: bool = False,
    reconcile_scope: str = "city",
    retrieval_timestamp: Optional[datetime] = None,
) -> CityIngestionResult:
    """Parse, normalize, and ingest an e-RaktKosh city response payload into the database.

    Invariants & Safety Rules:
    1. Dry-run by default: does not modify database unless apply=True.
    2. Strict provenance:
       - source_name = 'e-RaktKosh (MoHFW)'
       - source_type = 'external_source'
       - verification_status = 'reported_unverified'
    3. Demo isolation: never matches, overwrites, or deletes synthetic demo records.
    4. Contact info redaction: phone numbers, faxes, emails are stripped by the parser
       and never stored in raw_address or locality.
    5. Safe reconciliation:
       - Re-ingestion is idempotent.
       - Facilities reporting no stock have their previous reports for this component withdrawn.
       - Facilities dropping a blood group have that specific group report withdrawn.
       - Unreported groups are never converted to zero-stock records.
       - If any failure occurs, the transaction is rolled back and no records are deleted.

    Args:
        db: SQLAlchemy session.
        city: Target city ('Delhi' or 'Lucknow').
        payload: e-RaktKosh raw JSON response dictionary.
        component: Blood component name (defaults to 'Whole Blood').
        apply: If True, writes changes to the database transactionally.
        reconcile_scope: 'city' to reconcile all external facilities in city, or
                         'facilities_in_payload' to reconcile only facilities present in payload.
        retrieval_timestamp: Explicit UTC retrieval timestamp or defaults to current UTC time.

    Returns:
        CityIngestionResult: Metric counts and warnings.
    """
    if city not in SUPPORTED_CITIES:
        raise ValueError(f"Unsupported city '{city}'. Supported cities: {SUPPORTED_CITIES}.")

    rec_retrieval_ts = retrieval_timestamp or datetime.now(timezone.utc)
    if rec_retrieval_ts.tzinfo is None:
        rec_retrieval_ts = rec_retrieval_ts.replace(tzinfo=timezone.utc)

    # 1. Parse raw response through validated parser & normalizer
    parsed: ParsedResponseResult = parse_eraktkosh_response(
        payload=payload,
        default_city=city,
        default_component=component,
        retrieval_timestamp=rec_retrieval_ts,
    )

    warnings: list[str] = []
    for failed_row in parsed.failed_rows:
        warnings.extend(failed_row.errors)

    # Group successful rows by deterministic facility ID to handle intra-payload duplicates
    facilities_map: dict[str, list[ParsedRowResult]] = {}
    ambiguous_facility_ids: set[str] = set()

    for row in parsed.successful_rows:
        if row.facility_info is None:
            continue
        fac_id = generate_facility_source_id(
            city=row.facility_info.city,
            facility_name=row.facility_info.facility_name,
            locality=row.facility_info.locality,
            raw_address=row.facility_info.raw_address,
        )

        if fac_id in ambiguous_facility_ids:
            # Already determined to be ambiguous; skip subsequent occurrences
            continue

        if fac_id in facilities_map:
            # Verify that rows sharing fac_id are genuinely the identical facility
            existing_row = facilities_map[fac_id][0]
            assert existing_row.facility_info is not None

            same_name = (
                _slugify(row.facility_info.facility_name)
                == _slugify(existing_row.facility_info.facility_name)
            )
            same_address = (
                _slugify(row.facility_info.raw_address)
                == _slugify(existing_row.facility_info.raw_address)
            )

            if not (same_name and same_address):
                # Ambiguous collision: different facilities produced the same ID.
                # Invariant: Never silently merge ambiguous facilities. Flag and reject both.
                ambiguous_facility_ids.add(fac_id)
                del facilities_map[fac_id]
                warnings.append(
                    f"Ambiguous facility identity collision on '{fac_id}': "
                    f"conflicting facilities '{existing_row.facility_info.facility_name}' and "
                    f"'{row.facility_info.facility_name}' were rejected for safety."
                )
                continue

        facilities_map.setdefault(fac_id, []).append(row)


    # Telemetry counters
    facilities_created_count = 0
    facilities_updated_count = 0
    reports_upserted_count = 0
    reports_withdrawn_count = 0

    if not apply:
        # Dry-run: compute simulation metrics without any DB writes
        simulated_reports = 0
        for fac_id, rows in facilities_map.items():
            # Combine items across rows for this facility
            seen_groups = set()
            for r in rows:
                if r.is_available:
                    for item in r.availability_items:
                        if item.blood_group not in seen_groups:
                            seen_groups.add(item.blood_group)
                            simulated_reports += 1

        return CityIngestionResult(
            city=city,
            component=component,
            retrieval_timestamp=rec_retrieval_ts,
            is_dry_run=True,
            source_rows_count=parsed.rows_parsed,
            successful_rows_count=len(parsed.successful_rows),
            failed_rows_count=len(parsed.failed_rows),
            facilities_created=len(facilities_map),
            facilities_updated=0,
            reports_upserted=simulated_reports,
            reports_withdrawn=0,
            warnings=warnings,
        )

    # Apply mode: execute transactionally
    try:
        # Collect facility IDs processed in this snapshot
        processed_facility_db_ids: set[int] = set()

        for fac_id, rows in facilities_map.items():
            # Pick primary row representation (prefer row with source timestamp if available)
            primary_row = rows[0]
            for r in rows[1:]:
                if r.source_reported_timestamp and not primary_row.source_reported_timestamp:
                    primary_row = r

            # Consolidate available items across intra-payload duplicates for this facility
            consolidated_items: dict[str, int] = {}
            row_freshness: Optional[str] = primary_row.freshness_indicator
            row_source_ts: Optional[datetime] = primary_row.source_reported_timestamp

            is_any_row_available = any(r.is_available for r in rows)
            if is_any_row_available:
                for r in rows:
                    if r.is_available:
                        for item in r.availability_items:
                            # Keep higher units if duplicate group appears within payload
                            if (
                                item.blood_group not in consolidated_items
                                or item.units > consolidated_items[item.blood_group]
                            ):
                                consolidated_items[item.blood_group] = item.units
                        if r.source_reported_timestamp:
                            row_source_ts = r.source_reported_timestamp
                        if r.freshness_indicator:
                            row_freshness = r.freshness_indicator

            # 1. Lookup or create BloodBank facility strictly isolated from demo records
            bank = db.scalar(
                select(BloodBank).where(
                    BloodBank.source_name == DEFAULT_ERAKTKOSH_SOURCE,
                    BloodBank.source_facility_id == fac_id,
                )
            )

            if bank is None:
                bank = BloodBank(
                    name=primary_row.facility_info.facility_name,
                    city=primary_row.facility_info.city,
                    locality=primary_row.facility_info.locality,
                    source_type=SOURCE_TYPE_EXTERNAL,
                    source_name=DEFAULT_ERAKTKOSH_SOURCE,
                    source_facility_id=fac_id,
                    raw_address=primary_row.facility_info.raw_address,
                    category=primary_row.category,
                    facility_type=primary_row.facility_type,
                )
                db.add(bank)
                db.flush()
                facilities_created_count += 1
            else:
                # Update facility metadata if changed
                bank.locality = primary_row.facility_info.locality
                bank.raw_address = primary_row.facility_info.raw_address
                if primary_row.category:
                    bank.category = primary_row.category
                if primary_row.facility_type:
                    bank.facility_type = primary_row.facility_type
                facilities_updated_count += 1

            processed_facility_db_ids.add(bank.id)

            # 2. Upsert available stock reports for this facility
            reported_groups_for_fac: set[str] = set()

            for group, units in consolidated_items.items():
                reported_groups_for_fac.add(group)

                report = db.scalar(
                    select(StockReport).where(
                        StockReport.blood_bank_id == bank.id,
                        StockReport.blood_group == group,
                        StockReport.blood_component == component,
                    )
                )

                if report is None:
                    report = StockReport(
                        blood_bank_id=bank.id,
                        blood_group=group,
                        blood_component=component,
                        units_reported=units,
                        source_name=DEFAULT_ERAKTKOSH_SOURCE,
                        source_reported_timestamp=row_source_ts,
                        retrieval_timestamp=rec_retrieval_ts,
                        freshness_indicator=row_freshness,
                        data_timestamp=rec_retrieval_ts,
                        verification_status=STATUS_REPORTED_UNVERIFIED,
                    )
                    db.add(report)
                    reports_upserted_count += 1
                else:
                    report.units_reported = units
                    report.source_name = DEFAULT_ERAKTKOSH_SOURCE
                    report.source_reported_timestamp = row_source_ts
                    report.retrieval_timestamp = rec_retrieval_ts
                    report.freshness_indicator = row_freshness
                    report.data_timestamp = rec_retrieval_ts
                    report.verification_status = STATUS_REPORTED_UNVERIFIED
                    reports_upserted_count += 1

            # 3. Reconcile withdrawn groups for this specific facility
            # (Delete reports for groups no longer reported or if facility reports no stock)
            withdrawn_reports = db.scalars(
                select(StockReport).where(
                    StockReport.blood_bank_id == bank.id,
                    StockReport.blood_component == component,
                    StockReport.source_name == DEFAULT_ERAKTKOSH_SOURCE,
                    StockReport.blood_group.not_in(reported_groups_for_fac),
                )
            ).all()

            for old_rep in withdrawn_reports:
                db.delete(old_rep)
                reports_withdrawn_count += 1

        # 4. Reconcile absent external facilities in city (if reconcile_scope == 'city')
        if reconcile_scope == "city" and processed_facility_db_ids:
            # Find any external facilities in this city that were NOT in the current snapshot
            absent_external_banks = db.scalars(
                select(BloodBank).where(
                    BloodBank.city == city,
                    BloodBank.source_name == DEFAULT_ERAKTKOSH_SOURCE,
                    BloodBank.id.not_in(processed_facility_db_ids),
                )
            ).all()

            for absent_bank in absent_external_banks:
                absent_reports = db.scalars(
                    select(StockReport).where(
                        StockReport.blood_bank_id == absent_bank.id,
                        StockReport.blood_component == component,
                        StockReport.source_name == DEFAULT_ERAKTKOSH_SOURCE,
                    )
                ).all()
                for old_rep in absent_reports:
                    db.delete(old_rep)
                    reports_withdrawn_count += 1

        db.commit()

    except Exception as exc:
        db.rollback()
        raise ERaktKoshIngestionError(
            f"Transactional database update failed for city '{city}': {exc}"
        ) from exc

    return CityIngestionResult(
        city=city,
        component=component,
        retrieval_timestamp=rec_retrieval_ts,
        is_dry_run=False,
        source_rows_count=parsed.rows_parsed,
        successful_rows_count=len(parsed.successful_rows),
        failed_rows_count=len(parsed.failed_rows),
        facilities_created=facilities_created_count,
        facilities_updated=facilities_updated_count,
        reports_upserted=reports_upserted_count,
        reports_withdrawn=reports_withdrawn_count,
        warnings=warnings,
    )


def ingest_city_from_source(
    db: Session,
    city: str,
    client: Optional[ERaktKoshClient] = None,
    component: str = "Whole Blood",
    apply: bool = False,
    reconcile_scope: str = "city",
) -> CityIngestionResult:
    """Retrieve stock details via client and ingest into database.

    Args:
        db: SQLAlchemy session.
        city: City to query ("Delhi" or "Lucknow").
        client: ERaktKoshClient instance (or creates default).
        component: Blood component (default "Whole Blood").
        apply: True to commit to DB, False for dry run.
        reconcile_scope: 'city' or 'facilities_in_payload'.
    """
    retrieval_client = client or ERaktKoshClient()
    payload = retrieval_client.fetch_stock_details(city=city, component=component)

    return ingest_eraktkosh_city_payload(
        db=db,
        city=city,
        payload=payload,
        component=component,
        apply=apply,
        reconcile_scope=reconcile_scope,
    )


def run_ingestion_cli(
    argv: Optional[list[str]] = None,
    session_factory: Optional[Any] = None,
) -> int:
    """CLI handler for e-RaktKosh data retrieval and ingestion."""
    import argparse

    parser = argparse.ArgumentParser(
        description="RaktSetu e-RaktKosh blood stock ingestion pipeline.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--city",
        choices=["Delhi", "Lucknow", "all"],
        default="all",
        help="Target city to ingest.",
    )
    parser.add_argument(
        "--component",
        default="Whole Blood",
        help="Blood component name to ingest.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Apply and persist changes to the database. Defaults to dry-run mode.",
    )
    parser.add_argument(
        "--fixture",
        type=str,
        default=None,
        help="Path to an offline JSON fixture file to ingest instead of making network calls.",
    )

    args = parser.parse_args(argv)

    cities_to_process = (
        ["Delhi", "Lucknow"] if args.city == "all" else [args.city]
    )

    print("=" * 64)
    print("           RaktSetu e-RaktKosh Ingestion Pipeline           ")
    print("=" * 64)
    mode_label = (
        "LIVE APPLY (changes committed to database)"
        if args.apply
        else "DRY RUN (no database changes)  [Use --apply to persist]"
    )
    print(f"Mode:      {mode_label}")
    print(f"Component: {args.component}")
    print(f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("-" * 64)

    if session_factory is None:
        init_db()
        db_factory = SessionLocal
    else:
        db_factory = session_factory

    fixture_data: Optional[dict[str, Any]] = None
    if args.fixture:
        fixture_path = Path(args.fixture)
        if not fixture_path.exists():
            print(f"[Error] Fixture file not found: {fixture_path}")
            return 1
        with open(fixture_path, "r", encoding="utf-8") as f:
            fixture_data = json.load(f)

    with db_factory() as db:
        for c in cities_to_process:
            print(f"\n[Processing City: {c}]")
            try:
                if fixture_data is not None:
                    # Resolve fixture payload for city
                    city_key = f"synthetic_{c.lower()}_response"
                    payload = (
                        fixture_data.get(city_key)
                        or fixture_data.get("data")
                        or fixture_data
                    )
                    res = ingest_eraktkosh_city_payload(
                        db=db,
                        city=c,
                        payload=payload,
                        component=args.component,
                        apply=args.apply,
                    )
                else:
                    client = ERaktKoshClient()
                    res = ingest_city_from_source(
                        db=db,
                        city=c,
                        client=client,
                        component=args.component,
                        apply=args.apply,
                    )

                print(f"  Source rows retrieved:    {res.source_rows_count}")
                print(f"  Rows parsed successfully: {res.successful_rows_count}")
                print(f"  Rows rejected / failed:   {res.failed_rows_count}")
                print(f"  Facilities created:       {res.facilities_created}")
                print(f"  Facilities updated:       {res.facilities_updated}")
                print(f"  Stock reports upserted:   {res.reports_upserted}")
                print(f"  Stock reports withdrawn:  {res.reports_withdrawn}")

                if res.warnings:
                    print(f"  Warnings ({len(res.warnings)}):")
                    for w in res.warnings[:5]:
                        # Sanitized warning output (never prints phone numbers/emails)
                        print(f"    - {w}")
                    if len(res.warnings) > 5:
                        print(f"    ... and {len(res.warnings) - 5} more warnings.")

            except (ERaktKoshRetrievalError, ERaktKoshIngestionError, ValueError) as err:
                print(f"  [Error] Failed to process {c}: {err}")
                return 1

    print("\n" + "=" * 64)
    if args.apply:
        print("Success: Database updated transactionally.")
    else:
        print("Success: Dry run completed. Database was NOT modified.")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(run_ingestion_cli())
