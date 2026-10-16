from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect

from backend.app.core.database import DATABASE_URL, engine as default_engine

BASELINE_REVISION = "0001_baseline_schema"
HEAD_REVISION = "head"

# Expected schema columns for the baseline create_all() schema
EXPECTED_BASELINE_BLOOD_BANKS_COLUMNS = {"id", "name", "city", "locality"}
EXPECTED_BASELINE_STOCK_REPORTS_COLUMNS = {
    "id",
    "blood_bank_id",
    "blood_group",
    "units_reported",
    "source_name",
    "data_timestamp",
    "verification_status",
}


def get_alembic_config(
    engine: Optional[Engine] = None,
    alembic_ini_path: Optional[Path] = None,
) -> Config:
    """Construct an Alembic Config object configured with project locations and engine connection."""
    root_dir = Path(__file__).resolve().parent.parent.parent.parent
    ini_file = alembic_ini_path or (root_dir / "alembic.ini")
    if not ini_file.exists():
        raise FileNotFoundError(f"Alembic configuration file not found at: {ini_file}")

    alembic_cfg = Config(str(ini_file))
    # Ensure script location is resolved as an absolute path
    script_loc = root_dir / "backend" / "migrations"
    alembic_cfg.set_main_option("script_location", str(script_loc))

    # Bind connection if engine is provided
    if engine is not None:
        alembic_cfg.attributes["connection"] = engine.connect()

    return alembic_cfg


def verify_baseline_schema(inspector) -> tuple[bool, str]:
    """Verify that an unversioned database matches the exact expected 0001 baseline schema."""
    tables = set(inspector.get_table_names())
    if "blood_banks" not in tables or "stock_reports" not in tables:
        return False, f"Expected tables 'blood_banks' and 'stock_reports' not found in database. Found: {tables}"

    # Reject unrecognized tables
    unknown_tables = tables - {"blood_banks", "stock_reports", "sqlite_sequence"}
    if unknown_tables:
        return (
            False,
            f"Unrecognized tables found in unversioned database: {unknown_tables}",
        )

    # 1. Verify column sets
    bank_cols = {c["name"] for c in inspector.get_columns("blood_banks")}
    if bank_cols != EXPECTED_BASELINE_BLOOD_BANKS_COLUMNS:
        return (
            False,
            f"Table 'blood_banks' columns {bank_cols} do not match baseline {EXPECTED_BASELINE_BLOOD_BANKS_COLUMNS}",
        )

    report_cols = {c["name"] for c in inspector.get_columns("stock_reports")}
    if report_cols != EXPECTED_BASELINE_STOCK_REPORTS_COLUMNS:
        return (
            False,
            f"Table 'stock_reports' columns {report_cols} do not match baseline {EXPECTED_BASELINE_STOCK_REPORTS_COLUMNS}",
        )

    # 2. Verify no unexpected unique constraints on blood_banks
    bank_uqs = inspector.get_unique_constraints("blood_banks")
    if bank_uqs:
        return (
            False,
            f"Table 'blood_banks' contains unexpected unique constraints: {bank_uqs}",
        )

    # 3. Verify baseline unique constraint on (blood_bank_id, blood_group) and reject incompatible unique constraints
    unique_constraints = inspector.get_unique_constraints("stock_reports")
    for uq in unique_constraints:
        cols = set(uq.get("column_names") or [])
        if cols and cols != {"blood_bank_id", "blood_group"}:
            return (
                False,
                f"Table 'stock_reports' contains incompatible unique constraint on {cols}",
            )

    has_baseline_uq = any(
        set(uq.get("column_names") or []) == {"blood_bank_id", "blood_group"}
        for uq in unique_constraints
    )
    if not has_baseline_uq:
        # Check unique indexes as SQLite often maps unique constraints to unique indexes
        unique_indexes = [
            idx for idx in inspector.get_indexes("stock_reports") if idx.get("unique")
        ]
        for idx in unique_indexes:
            cols = set(idx.get("column_names") or [])
            if cols and cols != {"blood_bank_id", "blood_group"}:
                return (
                    False,
                    f"Table 'stock_reports' contains incompatible unique index on {cols}",
                )
        has_baseline_uq = any(
            set(idx.get("column_names") or []) == {"blood_bank_id", "blood_group"}
            for idx in unique_indexes
        )
    if not has_baseline_uq:
        return (
            False,
            "Table 'stock_reports' is missing expected baseline unique constraint on (blood_bank_id, blood_group)",
        )

    # 4. Verify foreign key from stock_reports to blood_banks
    fks = inspector.get_foreign_keys("stock_reports")
    has_valid_fk = any(
        fk.get("referred_table") == "blood_banks"
        and (fk.get("constrained_columns") or []) == ["blood_bank_id"]
        for fk in fks
    )
    if not has_valid_fk:
        return (
            False,
            "Table 'stock_reports' is missing expected foreign key referencing blood_banks(id)",
        )

    # 5. Verify indexes on stock_reports do not include incompatible unexpected indexes
    all_indexes = inspector.get_indexes("stock_reports")
    allowed_index_cols = [{"blood_bank_id"}, {"blood_group"}, {"blood_bank_id", "blood_group"}]
    for idx in all_indexes:
        cols = set(idx.get("column_names") or [])
        if cols and cols not in allowed_index_cols:
            return (
                False,
                f"Table 'stock_reports' contains unexpected index on columns {cols}",
            )

    return True, "Baseline schema matches expected structure."


def run_database_migrations(
    engine: Optional[Engine] = None,
    alembic_ini_path: Optional[Path] = None,
) -> str:
    """Guarded database migration and bootstrap runner.

    Safely handles:
    1. Already versioned databases: runs 'upgrade head'.
    2. Fresh empty databases: runs 'upgrade head' from revision None.
    3. Existing unversioned databases: verifies schema strictly matches the 0001 baseline
       before stamping, then upgrades to head. Refuses to stamp arbitrary/incompatible schemas.

    Returns:
        str: Status message describing the migration action taken.
    """
    target_engine = engine or default_engine
    inspector = inspect(target_engine)
    tables = set(inspector.get_table_names())

    alembic_cfg = get_alembic_config(engine=target_engine, alembic_ini_path=alembic_ini_path)
    conn = alembic_cfg.attributes.get("connection")

    try:
        # Case 1: Database is already managed by Alembic
        if "alembic_version" in tables:
            command.upgrade(alembic_cfg, HEAD_REVISION)
            return "Upgraded existing versioned database to head."

        # Case 2: Fresh database (no tables yet)
        if "blood_banks" not in tables and "stock_reports" not in tables:
            command.upgrade(alembic_cfg, HEAD_REVISION)
            return "Initialized fresh database and migrated to head."

        # Case 3: Existing unversioned database — Guarded baseline verification
        is_valid_baseline, detail = verify_baseline_schema(inspector)
        if not is_valid_baseline:
            raise ValueError(
                f"Cannot migrate unversioned database: schema does not match baseline. {detail}"
            )

        # Baseline verified: stamp 0001 then upgrade to 0002 head
        command.stamp(alembic_cfg, BASELINE_REVISION)
        command.upgrade(alembic_cfg, HEAD_REVISION)
        return "Verified baseline schema on unversioned database, stamped baseline, and migrated to head."

    finally:
        if conn is not None and not conn.closed:
            conn.close()


if __name__ == "__main__":
    print("[RaktSetu Migration] Running guarded database migration...")
    result = run_database_migrations()
    print(f"[RaktSetu Migration] Success: {result}")
