from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.migration import (
    BASELINE_REVISION,
    HEAD_REVISION,
    get_alembic_config,
    run_database_migrations,
    verify_baseline_schema,
)
from backend.app.models.blood_bank import BloodBank, StockReport
from backend.app.schemas.blood_bank import BloodBankListResponse, BloodBankRead, StockReportRead
from backend.app.seed_demo import seed_demo_data

DEMO_SEED_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "demo" / "blood_banks.json"


def create_unversioned_baseline_db(db_path: Path) -> None:
    """Helper to create an unversioned SQLite database matching the 0001 baseline schema and seeded with demo data."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE blood_banks (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(255) NOT NULL,
            city VARCHAR(50) NOT NULL,
            locality VARCHAR(255) NOT NULL,
            CONSTRAINT ck_blood_bank_city CHECK (city IN ('Delhi', 'Lucknow'))
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE stock_reports (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            blood_bank_id INTEGER NOT NULL,
            blood_group VARCHAR(10) NOT NULL,
            units_reported INTEGER NOT NULL,
            source_name VARCHAR(255) NOT NULL,
            data_timestamp DATETIME NOT NULL,
            verification_status VARCHAR(50) NOT NULL,
            CONSTRAINT uq_blood_bank_blood_group UNIQUE (blood_bank_id, blood_group),
            CONSTRAINT ck_stock_report_blood_group CHECK (blood_group IN ('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-')),
            FOREIGN KEY(blood_bank_id) REFERENCES blood_banks (id) ON DELETE CASCADE
        )
        """
    )

    cursor.execute("CREATE INDEX ix_stock_reports_blood_bank_id ON stock_reports (blood_bank_id)")
    cursor.execute("CREATE INDEX ix_stock_reports_blood_group ON stock_reports (blood_group)")

    # Seed demo data into the raw unversioned baseline database
    with open(DEMO_SEED_PATH, "r", encoding="utf-8") as f:
        demo_banks = json.load(f)

    for bank_item in demo_banks:
        cursor.execute(
            "INSERT INTO blood_banks (name, city, locality) VALUES (?, ?, ?)",
            (bank_item["name"], bank_item["city"], bank_item["locality"]),
        )
        bank_id = cursor.lastrowid
        for report in bank_item["stock_reports"]:
            cursor.execute(
                """
                INSERT INTO stock_reports (blood_bank_id, blood_group, units_reported, source_name, data_timestamp, verification_status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    bank_id,
                    report["blood_group"],
                    report["units_reported"],
                    report["source_name"],
                    report["data_timestamp"].replace("Z", "+00:00"),
                    report["verification_status"],
                ),
            )

    conn.commit()
    conn.close()


class TestGuardedDatabaseMigration:
    """Verify versioned migration execution, baseline stamping, and data retention."""

    def test_migration_preserves_existing_demo_records_and_ids(self, tmp_path: Path) -> None:
        db_file = tmp_path / "legacy.db"
        create_unversioned_baseline_db(db_file)

        engine = create_engine(f"sqlite:///{db_file.as_posix()}", connect_args={"check_same_thread": False})

        # Run guarded migration
        status = run_database_migrations(engine=engine)
        assert "Verified baseline schema" in status or "stamped baseline" in status

        with Session(engine) as session:
            # 1. Exactly 8 banks and 64 stock reports survive
            banks = session.scalars(select(BloodBank).order_by(BloodBank.id.asc())).all()
            assert len(banks) == 8
            reports = session.scalars(select(StockReport).order_by(StockReport.id.asc())).all()
            assert len(reports) == 64

            # 2. Check provenance backfills on facilities
            for bank in banks:
                assert bank.source_type == "demo"
                assert bank.source_name == "Synthetic demo dataset"
                assert bank.source_facility_id == f"demo:{bank.id}"
                assert bank.raw_address is None
                assert bank.category is None
                assert bank.facility_type is None

            # 3. Check component and timestamp invariants on legacy demo stock reports
            for report in reports:
                assert report.blood_component == "Unspecified"
                assert report.verification_status == "demo"
                # Legacy source_reported_timestamp MUST remain null
                assert report.source_reported_timestamp is None
                # retrieval_timestamp must be populated with documented migration time
                assert report.retrieval_timestamp is not None
                assert report.freshness_indicator is None
                # Legacy data_timestamp preserved exactly
                assert report.data_timestamp is not None
                assert report.data_timestamp.tzinfo is not None

    def test_fresh_database_migration_succeeds(self, tmp_path: Path) -> None:
        fresh_db = tmp_path / "fresh.db"
        engine = create_engine(f"sqlite:///{fresh_db.as_posix()}", connect_args={"check_same_thread": False})

        status = run_database_migrations(engine=engine)
        assert "fresh database" in status.lower()

        # Seed demo data into the fresh migrated database
        with Session(engine) as session:
            banks_seeded, reports_seeded = seed_demo_data(session)
            assert banks_seeded == 8
            assert reports_seeded == 64

            bank = session.scalar(select(BloodBank).where(BloodBank.id == 1))
            assert bank is not None
            assert bank.source_type == "demo"
            assert bank.source_facility_id == "demo:1"

    def test_incompatible_unversioned_schema_rejected(self, tmp_path: Path) -> None:
        bad_db = tmp_path / "corrupted.db"
        conn = sqlite3.connect(str(bad_db))
        cursor = conn.cursor()
        # Create arbitrary tables not matching baseline columns
        cursor.execute("CREATE TABLE blood_banks (id INTEGER PRIMARY KEY, random_column TEXT)")
        cursor.execute("CREATE TABLE stock_reports (id INTEGER PRIMARY KEY, other_column TEXT)")
        conn.commit()
        conn.close()

        engine = create_engine(f"sqlite:///{bad_db.as_posix()}", connect_args={"check_same_thread": False})

        with pytest.raises(ValueError) as exc_info:
            run_database_migrations(engine=engine)

        assert "Cannot migrate unversioned database" in str(exc_info.value)
        assert "does not match baseline" in str(exc_info.value)

    def test_unversioned_db_with_incompatible_unique_constraint_rejected(self, tmp_path: Path) -> None:
        bad_db = tmp_path / "bad_constraint.db"
        conn = sqlite3.connect(str(bad_db))
        cursor = conn.cursor()
        # Create baseline tables with correct columns but without the baseline unique constraint
        cursor.execute(
            """
            CREATE TABLE blood_banks (
                id INTEGER PRIMARY KEY, name VARCHAR(255), city VARCHAR(50), locality VARCHAR(255)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE stock_reports (
                id INTEGER PRIMARY KEY, blood_bank_id INTEGER, blood_group VARCHAR(10),
                units_reported INTEGER, source_name VARCHAR(255), data_timestamp DATETIME,
                verification_status VARCHAR(50),
                FOREIGN KEY(blood_bank_id) REFERENCES blood_banks (id)
            )
            """
        )
        conn.commit()
        conn.close()

        engine = create_engine(f"sqlite:///{bad_db.as_posix()}", connect_args={"check_same_thread": False})

        with pytest.raises(ValueError) as exc_info:
            run_database_migrations(engine=engine)

        assert "missing expected baseline unique constraint" in str(exc_info.value)

    def test_unversioned_db_with_unexpected_extra_table_rejected(self, tmp_path: Path) -> None:
        bad_db = tmp_path / "extra_table.db"
        create_unversioned_baseline_db(bad_db)

        # Add an unexpected extra table
        conn = sqlite3.connect(str(bad_db))
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE unexpected_patients (id INTEGER PRIMARY KEY, name TEXT)")
        conn.commit()
        conn.close()

        engine = create_engine(f"sqlite:///{bad_db.as_posix()}", connect_args={"check_same_thread": False})
        with pytest.raises(ValueError) as exc_info:
            run_database_migrations(engine=engine)

        assert "Unrecognized tables found in unversioned database" in str(exc_info.value)

    def test_unversioned_db_with_conflicting_unique_constraint_rejected(self, tmp_path: Path) -> None:
        bad_db = tmp_path / "conflicting_uq.db"
        conn = sqlite3.connect(str(bad_db))
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE blood_banks (
                id INTEGER PRIMARY KEY, name VARCHAR(255), city VARCHAR(50), locality VARCHAR(255)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE stock_reports (
                id INTEGER PRIMARY KEY, blood_bank_id INTEGER, blood_group VARCHAR(10),
                units_reported INTEGER, source_name VARCHAR(255), data_timestamp DATETIME,
                verification_status VARCHAR(50),
                CONSTRAINT uq_blood_bank_blood_group UNIQUE (blood_bank_id, blood_group),
                CONSTRAINT uq_bad_group UNIQUE (blood_group),
                FOREIGN KEY(blood_bank_id) REFERENCES blood_banks (id)
            )
            """
        )
        conn.commit()
        conn.close()

        engine = create_engine(f"sqlite:///{bad_db.as_posix()}", connect_args={"check_same_thread": False})
        with pytest.raises(ValueError) as exc_info:
            run_database_migrations(engine=engine)

        assert "incompatible unique" in str(exc_info.value).lower()

    def test_actual_pre_migration_backup_preserves_records_safely(self, tmp_path: Path) -> None:
        backup_src = Path("data") / "raktsetu.pre_migration.db"
        assert backup_src.exists(), "Pre-migration backup file must exist locally"

        # Record SHA256 of original backup to ensure it remains untouched
        with open(backup_src, "rb") as f:
            original_sha = hashlib.sha256(f.read()).hexdigest()

        # Copy to a disposable temporary file for testing
        disposable_db = tmp_path / "disposable_backup.db"
        shutil.copy2(backup_src, disposable_db)

        engine = create_engine(f"sqlite:///{disposable_db.as_posix()}", connect_args={"check_same_thread": False})
        status = run_database_migrations(engine=engine)
        assert "Verified baseline schema" in status or "stamped baseline" in status

        with Session(engine) as session:
            banks = session.scalars(select(BloodBank).order_by(BloodBank.id.asc())).all()
            assert len(banks) == 8
            reports = session.scalars(select(StockReport).order_by(StockReport.id.asc())).all()
            assert len(reports) == 64

            for bank in banks:
                assert bank.source_type == "demo"
                assert bank.source_facility_id == f"demo:{bank.id}"

            for report in reports:
                assert report.blood_component == "Unspecified"
                assert report.source_reported_timestamp is None
                assert report.retrieval_timestamp is not None
                assert report.data_timestamp is not None

        engine.dispose()

        # Verify the original pre-migration backup is completely unchanged
        with open(backup_src, "rb") as f:
            after_sha = hashlib.sha256(f.read()).hexdigest()
        assert original_sha == after_sha, "Original pre-migration backup was modified!"


class TestComponentAwareConstraintsAndIsolation:
    """Verify component-level uniqueness, multi-component coexistence, and demo isolation."""

    @pytest.fixture
    def migrated_db(self, tmp_path: Path):
        db_file = tmp_path / "test_constraints.db"
        engine = create_engine(f"sqlite:///{db_file.as_posix()}", connect_args={"check_same_thread": False})
        run_database_migrations(engine=engine)
        with Session(engine) as session:
            seed_demo_data(session)
        return engine

    def test_component_defaults_to_unspecified_without_redundant_key(self, migrated_db) -> None:
        # Invariant: There is NO separate component_key attribute/column to prevent redundant desynchronized state
        assert not hasattr(StockReport, "component_key")
        assert not hasattr(StockReportRead, "component_key")

        with Session(migrated_db) as session:
            test_bank = BloodBank(
                name="Test General Hospital",
                city="Delhi",
                locality="Rohini",
                source_type="demo",
                source_name="Synthetic demo dataset",
            )
            session.add(test_bank)
            session.flush()

            # Creating without blood_component defaults to 'Unspecified'
            default_report = StockReport(
                blood_bank_id=test_bank.id,
                blood_group="AB-",
                units_reported=7,
                source_name="Synthetic demo dataset",
                data_timestamp=datetime.now(timezone.utc),
                retrieval_timestamp=datetime.now(timezone.utc),
                verification_status="demo",
            )
            session.add(default_report)
            session.commit()
            assert default_report.blood_component == "Unspecified"

            # Creating with explicit PRBC sets canonical blood_component directly
            prbc_report = StockReport(
                blood_bank_id=test_bank.id,
                blood_group="AB-",
                blood_component="Packed Red Blood Cells",
                units_reported=14,
                source_name="e-RaktKosh (MoHFW)",
                data_timestamp=datetime.now(timezone.utc),
                retrieval_timestamp=datetime.now(timezone.utc),
                verification_status="reported_unverified",
            )
            session.add(prbc_report)
            session.commit()
            assert prbc_report.blood_component == "Packed Red Blood Cells"

    def test_distinct_components_cannot_silently_collide(self, migrated_db) -> None:
        with Session(migrated_db) as session:
            bank = session.scalar(select(BloodBank).where(BloodBank.id == 2))
            assert bank is not None

            # Distinct components for the same group A-
            components_to_insert = [
                "Whole Blood",
                "Packed Red Blood Cells",
                "Platelet Rich Plasma",
                "Fresh Frozen Plasma",
            ]
            for comp in components_to_insert:
                session.add(
                    StockReport(
                        blood_bank_id=bank.id,
                        blood_group="A-",
                        blood_component=comp,
                        units_reported=5,
                        source_name="e-RaktKosh (MoHFW)",
                        data_timestamp=datetime.now(timezone.utc),
                        retrieval_timestamp=datetime.now(timezone.utc),
                        verification_status="reported_unverified",
                    )
                )
            session.commit()

            # Confirm all distinct components coexist without collisions
            reports = session.scalars(
                select(StockReport).where(
                    StockReport.blood_bank_id == bank.id,
                    StockReport.blood_group == "A-",
                )
            ).all()
            # 1 Unspecified (demo) + 4 distinct external components = 5
            assert len(reports) == 5
            found_components = {r.blood_component for r in reports}
            assert found_components == {"Unspecified", *components_to_insert}

    def test_multiple_components_for_same_group_can_coexist(self, migrated_db) -> None:
        with Session(migrated_db) as session:
            bank = session.scalar(select(BloodBank).where(BloodBank.id == 1))
            assert bank is not None

            # Add 'Whole Blood' and 'Packed Red Blood Cells' for the same bank and blood group
            wb_report = StockReport(
                blood_bank_id=bank.id,
                blood_group="A+",
                blood_component="Whole Blood",
                units_reported=10,
                source_name="e-RaktKosh (MoHFW)",
                data_timestamp=datetime.now(timezone.utc),
                retrieval_timestamp=datetime.now(timezone.utc),
                verification_status="reported_unverified",
            )
            prbc_report = StockReport(
                blood_bank_id=bank.id,
                blood_group="A+",
                blood_component="Packed Red Blood Cells",
                units_reported=25,
                source_name="e-RaktKosh (MoHFW)",
                data_timestamp=datetime.now(timezone.utc),
                retrieval_timestamp=datetime.now(timezone.utc),
                verification_status="reported_unverified",
            )
            session.add_all([wb_report, prbc_report])
            session.commit()

            # Verify both coexist for group A+ on bank 1
            reports = session.scalars(
                select(StockReport).where(
                    StockReport.blood_bank_id == bank.id,
                    StockReport.blood_group == "A+",
                )
            ).all()
            # 1 Unspecified (legacy demo) + 1 Whole Blood + 1 Packed Red Blood Cells = 3
            assert len(reports) == 3
            components = {r.blood_component for r in reports}
            assert components == {"Unspecified", "Whole Blood", "Packed Red Blood Cells"}

    def test_duplicate_reports_for_same_component_rejected(self, migrated_db) -> None:
        with Session(migrated_db) as session:
            bank = session.scalar(select(BloodBank).where(BloodBank.id == 1))
            assert bank is not None

            report_1 = StockReport(
                blood_bank_id=bank.id,
                blood_group="B+",
                blood_component="Whole Blood",
                units_reported=15,
                source_name="e-RaktKosh (MoHFW)",
                data_timestamp=datetime.now(timezone.utc),
                retrieval_timestamp=datetime.now(timezone.utc),
                verification_status="reported_unverified",
            )
            session.add(report_1)
            session.commit()

            # Attempt duplicate for the same bank, group, and component
            duplicate = StockReport(
                blood_bank_id=bank.id,
                blood_group="B+",
                blood_component="Whole Blood",
                units_reported=18,
                source_name="e-RaktKosh (MoHFW)",
                data_timestamp=datetime.now(timezone.utc),
                retrieval_timestamp=datetime.now(timezone.utc),
                verification_status="reported_unverified",
            )
            session.add(duplicate)
            with pytest.raises(IntegrityError):
                session.commit()

    def test_unspecified_demo_component_cannot_be_duplicated(self, migrated_db) -> None:
        with Session(migrated_db) as session:
            bank = session.scalar(select(BloodBank).where(BloodBank.id == 1))
            assert bank is not None

            # Legacy demo record already has (bank.id, 'O+', 'Unspecified')
            dup_unspecified = StockReport(
                blood_bank_id=bank.id,
                blood_group="O+",
                blood_component="Unspecified",
                units_reported=99,
                source_name="Synthetic demo dataset",
                data_timestamp=datetime.now(timezone.utc),
                retrieval_timestamp=datetime.now(timezone.utc),
                verification_status="demo",
            )
            session.add(dup_unspecified)
            with pytest.raises(IntegrityError):
                session.commit()

    def test_external_facilities_remain_distinct_from_similarly_named_demo_facilities(
        self, migrated_db
    ) -> None:
        with Session(migrated_db) as session:
            demo_bank = session.scalar(select(BloodBank).where(BloodBank.id == 1))
            assert demo_bank is not None
            demo_name = demo_bank.name

            # Create an external facility with the exact same name
            external_bank = BloodBank(
                name=demo_name,
                city="Delhi",
                locality="Connaught Place",
                source_type="external_source",
                source_name="e-RaktKosh (MoHFW)",
                source_facility_id="eraktkosh:delhi:connaught-place-facility",
                raw_address="Connaught Place, New Delhi",
                category="Govt.",
                facility_type="Blood Bank",
            )
            session.add(external_bank)
            session.commit()

            # Confirm both coexist as distinct entities
            matching_banks = session.scalars(
                select(BloodBank).where(BloodBank.name == demo_name)
            ).all()
            assert len(matching_banks) == 2

            types = {b.source_type for b in matching_banks}
            assert types == {"demo", "external_source"}

    def test_repeated_ingestion_identity_enforced(self, migrated_db) -> None:
        with Session(migrated_db) as session:
            ext_1 = BloodBank(
                name="AIIMS Blood Depot",
                city="Delhi",
                locality="Ansari Nagar",
                source_type="external_source",
                source_name="e-RaktKosh (MoHFW)",
                source_facility_id="eraktkosh:delhi:aiims-ansari-nagar",
            )
            session.add(ext_1)
            session.commit()

            # Duplicate with same source_name and source_facility_id must be rejected
            ext_dup = BloodBank(
                name="AIIMS Blood Depot Duplicate",
                city="Delhi",
                locality="Ansari Nagar",
                source_type="external_source",
                source_name="e-RaktKosh (MoHFW)",
                source_facility_id="eraktkosh:delhi:aiims-ansari-nagar",
            )
            session.add(ext_dup)
            with pytest.raises(IntegrityError):
                session.commit()

    def test_live_badge_freshness_works_without_source_timestamp(self, migrated_db) -> None:
        with Session(migrated_db) as session:
            bank = session.scalar(select(BloodBank).where(BloodBank.id == 1))
            assert bank is not None

            badge_report = StockReport(
                blood_bank_id=bank.id,
                blood_group="AB+",
                blood_component="Platelets",
                units_reported=5,
                source_name="e-RaktKosh (MoHFW)",
                source_reported_timestamp=None,  # Live badge provides no exact timestamp
                retrieval_timestamp=datetime.now(timezone.utc),
                freshness_indicator="live_stock_badge",
                data_timestamp=datetime.now(timezone.utc),
                verification_status="reported_unverified",
            )
            session.add(badge_report)
            session.commit()

            saved = session.scalar(
                select(StockReport).where(
                    StockReport.blood_bank_id == bank.id,
                    StockReport.blood_component == "Platelets",
                )
            )
            assert saved is not None
            assert saved.source_reported_timestamp is None
            assert saved.freshness_indicator == "live_stock_badge"
            assert saved.verification_status == "reported_unverified"


class TestApiBackwardCompatibility:
    """Verify that migrated records serialize properly into existing Pydantic API response models."""

    def test_migrated_db_serializes_cleanly_into_api_schemas(self, tmp_path: Path) -> None:
        db_file = tmp_path / "api_compat.db"
        create_unversioned_baseline_db(db_file)
        engine = create_engine(f"sqlite:///{db_file.as_posix()}", connect_args={"check_same_thread": False})
        run_database_migrations(engine=engine)

        with Session(engine) as session:
            banks = session.scalars(select(BloodBank).order_by(BloodBank.id.asc())).all()
            assert len(banks) == 8

            items: list[BloodBankRead] = []
            for bank in banks:
                items.append(
                    BloodBankRead(
                        id=bank.id,
                        name=bank.name,
                        city=bank.city,
                        locality=bank.locality,
                        source_type=bank.source_type,
                        source_name=bank.source_name,
                        source_facility_id=bank.source_facility_id,
                        stock_reports=[StockReportRead.model_validate(r) for r in bank.stock_reports],
                    )
                )

            envelope = BloodBankListResponse(items=items, count=len(items))

            # Verify JSON serialization matches contract
            json_dict = envelope.model_dump(mode="json")
            assert json_dict["count"] == 8
            assert len(json_dict["items"]) == 8
            assert "data_notice" in json_dict

            first_bank = json_dict["items"][0]
            assert first_bank["id"] == 1
            assert first_bank["name"] == "Demo Central Transfusion Facility"
            assert first_bank["source_type"] == "demo"
            assert first_bank["source_facility_id"] == "demo:1"

            first_report = first_bank["stock_reports"][0]
            assert first_report["blood_group"] == "A+"
            assert first_report["blood_component"] == "Unspecified"
            assert first_report["units_reported"] == 12
            assert first_report["data_timestamp"].endswith("Z")
            assert first_report["source_reported_timestamp"] is None
            assert first_report["verification_status"] == "demo"
