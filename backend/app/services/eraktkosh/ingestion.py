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
    reconcile_scope: str = "facilities_in_payload"
    facilities_parsed: int = 0
    facilities_with_available_stock: int = 0
    facilities_with_unavailable_stock: int = 0
    stock_observations_parsed: int = 0
    facilities_unchanged: int = 0
    reports_created: int = 0
    reports_updated: int = 0
    reports_unchanged: int = 0


def ingest_eraktkosh_city_payload(
    db: Session,
    city: str,
    payload: dict[str, Any],
    component: str = "Whole Blood",
    apply: bool = False,
    reconcile_scope: str = "facilities_in_payload",
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
       - Scope defaults strictly to 'facilities_in_payload'.
       - Missing facilities from a source response are NEVER deleted or marked unavailable.
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
        reconcile_scope: 'facilities_in_payload' (safe facility-level reconciliation).
                         'city' is permanently disabled as source responses lack completeness proof.
        retrieval_timestamp: Explicit UTC retrieval timestamp or defaults to current UTC time.

    Returns:
        CityIngestionResult: Metric counts and warnings.
    """
    if reconcile_scope == "city":
        raise ValueError(
            "City-wide reconciliation is disabled for e-RaktKosh because upstream source responses "
            "do not provide independent proof of snapshot completeness. Use "
            "reconcile_scope='facilities_in_payload' to reconcile only observed facilities."
        )
    if reconcile_scope != "facilities_in_payload":
        raise ValueError(
            f"Unsupported reconcile_scope '{reconcile_scope}'. Supported: 'facilities_in_payload'."
        )

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


    # Consolidate per facility
    facilities_parsed_count = len(facilities_map)
    facilities_with_available_stock_count = 0
    facilities_with_unavailable_stock_count = 0
    stock_observations_parsed_count = 0

    consolidated_per_facility: dict[str, dict[str, int]] = {}
    primary_row_per_facility: dict[str, ParsedRowResult] = {}

    for fac_id, rows in facilities_map.items():
        primary_row = rows[0]
        for r in rows[1:]:
            if r.source_reported_timestamp and not primary_row.source_reported_timestamp:
                primary_row = r
        primary_row_per_facility[fac_id] = primary_row

        is_any_row_available = any(r.is_available for r in rows)
        consolidated_items: dict[str, int] = {}
        if is_any_row_available:
            facilities_with_available_stock_count += 1
            for r in rows:
                if r.is_available:
                    for item in r.availability_items:
                        if (
                            item.blood_group not in consolidated_items
                            or item.units > consolidated_items[item.blood_group]
                        ):
                            consolidated_items[item.blood_group] = item.units
        else:
            facilities_with_unavailable_stock_count += 1

        consolidated_per_facility[fac_id] = consolidated_items
        stock_observations_parsed_count += len(consolidated_items)

    if not apply:
        # Dry-run: compute simulation metrics by inspecting current DB state (read-only)
        sim_facilities_created = 0
        sim_facilities_updated = 0
        sim_facilities_unchanged = 0
        sim_reports_created = 0
        sim_reports_updated = 0
        sim_reports_unchanged = 0
        sim_reports_withdrawn = 0

        for fac_id, primary_row in primary_row_per_facility.items():
            consolidated_items = consolidated_per_facility[fac_id]
            existing_bank = db.scalar(
                select(BloodBank).where(
                    BloodBank.source_name == DEFAULT_ERAKTKOSH_SOURCE,
                    BloodBank.source_facility_id == fac_id,
                )
            )

            if existing_bank is None:
                sim_facilities_created += 1
                sim_reports_created += len(consolidated_items)
            else:
                has_meta_diff = (
                    existing_bank.locality != primary_row.facility_info.locality
                    or existing_bank.raw_address != primary_row.facility_info.raw_address
                    or (primary_row.category and existing_bank.category != primary_row.category)
                    or (primary_row.facility_type and existing_bank.facility_type != primary_row.facility_type)
                )
                if has_meta_diff:
                    sim_facilities_updated += 1
                else:
                    sim_facilities_unchanged += 1

                existing_reports = {
                    r.blood_group: r
                    for r in existing_bank.stock_reports
                    if r.blood_component == component and r.source_name == DEFAULT_ERAKTKOSH_SOURCE
                }

                for grp, units in consolidated_items.items():
                    if grp not in existing_reports:
                        sim_reports_created += 1
                    elif existing_reports[grp].units_reported != units:
                        sim_reports_updated += 1
                    else:
                        sim_reports_unchanged += 1

                for grp in existing_reports:
                    if grp not in consolidated_items:
                        sim_reports_withdrawn += 1

        sim_reports_upserted = sim_reports_created + sim_reports_updated + sim_reports_unchanged

        return CityIngestionResult(
            city=city,
            component=component,
            retrieval_timestamp=rec_retrieval_ts,
            is_dry_run=True,
            source_rows_count=parsed.rows_parsed,
            successful_rows_count=len(parsed.successful_rows),
            failed_rows_count=len(parsed.failed_rows),
            facilities_created=sim_facilities_created,
            facilities_updated=sim_facilities_updated,
            facilities_unchanged=sim_facilities_unchanged,
            reports_created=sim_reports_created,
            reports_updated=sim_reports_updated,
            reports_unchanged=sim_reports_unchanged,
            reports_upserted=sim_reports_upserted,
            reports_withdrawn=sim_reports_withdrawn,
            reconcile_scope=reconcile_scope,
            facilities_parsed=facilities_parsed_count,
            facilities_with_available_stock=facilities_with_available_stock_count,
            facilities_with_unavailable_stock=facilities_with_unavailable_stock_count,
            stock_observations_parsed=stock_observations_parsed_count,
            warnings=warnings,
        )

    # Apply mode: execute transactionally
    facilities_created_count = 0
    facilities_updated_count = 0
    facilities_unchanged_count = 0
    reports_created_count = 0
    reports_updated_count = 0
    reports_unchanged_count = 0
    reports_upserted_count = 0
    reports_withdrawn_count = 0

    try:
        for fac_id, primary_row in primary_row_per_facility.items():
            consolidated_items = consolidated_per_facility[fac_id]
            row_freshness: Optional[str] = primary_row.freshness_indicator
            row_source_ts: Optional[datetime] = primary_row.source_reported_timestamp
            for r in facilities_map[fac_id]:
                if r.source_reported_timestamp:
                    row_source_ts = r.source_reported_timestamp
                if r.freshness_indicator:
                    row_freshness = r.freshness_indicator

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
                has_meta_diff = (
                    bank.locality != primary_row.facility_info.locality
                    or bank.raw_address != primary_row.facility_info.raw_address
                    or (primary_row.category and bank.category != primary_row.category)
                    or (primary_row.facility_type and bank.facility_type != primary_row.facility_type)
                )
                if has_meta_diff:
                    bank.locality = primary_row.facility_info.locality
                    bank.raw_address = primary_row.facility_info.raw_address
                    if primary_row.category:
                        bank.category = primary_row.category
                    if primary_row.facility_type:
                        bank.facility_type = primary_row.facility_type
                    facilities_updated_count += 1
                else:
                    facilities_unchanged_count += 1

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
                    reports_created_count += 1
                    reports_upserted_count += 1
                else:
                    units_changed = (report.units_reported != units)
                    report.units_reported = units
                    report.source_name = DEFAULT_ERAKTKOSH_SOURCE
                    report.source_reported_timestamp = row_source_ts
                    report.retrieval_timestamp = rec_retrieval_ts
                    report.freshness_indicator = row_freshness
                    report.data_timestamp = rec_retrieval_ts
                    report.verification_status = STATUS_REPORTED_UNVERIFIED
                    if units_changed:
                        reports_updated_count += 1
                    else:
                        reports_unchanged_count += 1
                    reports_upserted_count += 1

            # 3. Reconcile withdrawn groups for this specific facility
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

        # NOTE: Absent external facilities in the city are intentionally NOT withdrawn.
        # Rationale: e-RaktKosh responses provide no independent proof of snapshot completeness.
        # A missing facility in a snapshot must never trigger deletion of existing records.

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
        facilities_unchanged=facilities_unchanged_count,
        reports_created=reports_created_count,
        reports_updated=reports_updated_count,
        reports_unchanged=reports_unchanged_count,
        reports_upserted=reports_upserted_count,
        reports_withdrawn=reports_withdrawn_count,
        reconcile_scope=reconcile_scope,
        facilities_parsed=facilities_parsed_count,
        facilities_with_available_stock=facilities_with_available_stock_count,
        facilities_with_unavailable_stock=facilities_with_unavailable_stock_count,
        stock_observations_parsed=stock_observations_parsed_count,
        warnings=warnings,
    )


def ingest_city_from_source(
    db: Session,
    city: str,
    client: Optional[ERaktKoshClient] = None,
    component: str = "Whole Blood",
    apply: bool = False,
    reconcile_scope: str = "facilities_in_payload",
) -> CityIngestionResult:
    """Retrieve stock details via client and ingest into database.

    Args:
        db: SQLAlchemy session.
        city: City to query ("Delhi" or "Lucknow").
        client: ERaktKoshClient instance (or creates default).
        component: Blood component (default "Whole Blood").
        apply: True to commit to DB, False for dry run.
        reconcile_scope: 'facilities_in_payload' (fail-safe facility-level reconciliation).
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
                print(f"  Distinct facilities parsed: {res.facilities_parsed}")
                print(f"    - Stock reported:         {res.facilities_with_available_stock}")
                print(f"    - No stock / zero:        {res.facilities_with_unavailable_stock}")
                print(f"  Stock observations parsed:{res.stock_observations_parsed:>6}")
                print(f"  Reconciliation scope:     {res.reconcile_scope}")
                print(f"  Facilities created:       {res.facilities_created}")
                print(f"  Facilities updated:       {res.facilities_updated}")
                print(f"  Facilities unchanged:     {res.facilities_unchanged}")
                print(f"  Stock reports created:    {res.reports_created}")
                print(f"  Stock reports updated:    {res.reports_updated}")
                print(f"  Stock reports unchanged:  {res.reports_unchanged}")
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
