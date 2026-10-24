import json
from pathlib import Path
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.database import Base
from backend.app.models.blood_bank import BloodBank, StockReport
from backend.app.services.seeder import (
    DEFAULT_SNAPSHOT_FILE,
    is_database_completely_empty,
    seed_deployment_snapshot,
)


@pytest.fixture
def memory_db_session():
    """Create an isolated, in-memory SQLite database session for seeder testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_snapshot_fixture_file_exists_and_has_expected_counts() -> None:
    """Verify that data/deployment_snapshot.json exists and contains 163 facilities and 110 stock reports."""
    assert DEFAULT_SNAPSHOT_FILE.exists()
    with open(DEFAULT_SNAPSHOT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) == 163
    total_stock_reports = sum(len(bank["stock_reports"]) for bank in data)
    assert total_stock_reports == 110

    # Ensure no raw addresses exist in the exported snapshot
    for bank in data:
        assert bank["raw_address"] is None
        # Ensure phone numbers are sanitized from localities
        locality = bank["locality"]
        assert "011-4225-1870" not in locality
        assert "98992 0703" not in locality


def test_seed_deployment_snapshot_on_empty_db(memory_db_session) -> None:
    """Verify that a completely empty database is successfully initialized with 163 facilities and 110 reports."""
    assert is_database_completely_empty(memory_db_session) is True

    banks_seeded, reports_seeded = seed_deployment_snapshot(memory_db_session)
    assert banks_seeded == 163
    assert reports_seeded == 110

    # Query counts directly
    db_banks = memory_db_session.scalar(select(func.count(BloodBank.id)))
    db_reports = memory_db_session.scalar(select(func.count(StockReport.id)))
    assert db_banks == 163
    assert db_reports == 110

    # Verify breakdown
    demo_banks = memory_db_session.scalars(
        select(BloodBank).where(BloodBank.source_type == "demo")
    ).all()
    external_banks = memory_db_session.scalars(
        select(BloodBank).where(BloodBank.source_type == "external_source")
    ).all()
    assert len(demo_banks) == 8
    assert len(external_banks) == 155

    # Verify all raw addresses are None
    addresses = memory_db_session.scalars(
        select(BloodBank.raw_address).where(BloodBank.raw_address.is_not(None))
    ).all()
    assert len(addresses) == 0

    # Verify timestamps are preserved and timezone-aware
    sample_report = memory_db_session.scalar(select(StockReport).where(StockReport.id == 65))
    assert sample_report is not None
    assert sample_report.data_timestamp.tzinfo is not None
    assert sample_report.verification_status == "reported_unverified"
    assert sample_report.blood_component == "Whole Blood"


def test_seed_deployment_snapshot_idempotency(memory_db_session) -> None:
    """Verify calling seed_deployment_snapshot on an already populated database performs no insertions."""
    # First seed
    banks_seeded, reports_seeded = seed_deployment_snapshot(memory_db_session)
    assert banks_seeded == 163
    assert reports_seeded == 110

    # Second seed attempt must safely skip
    second_banks, second_reports = seed_deployment_snapshot(memory_db_session)
    assert second_banks == 0
    assert second_reports == 0

    # Ensure counts have not changed
    assert memory_db_session.scalar(select(func.count(BloodBank.id))) == 163
    assert memory_db_session.scalar(select(func.count(StockReport.id))) == 110


def test_seed_deployment_snapshot_refuses_partially_initialized_db(memory_db_session) -> None:
    """Verify seeding refuses to overwrite or run on partially populated datasets."""
    # Pre-populate a single facility (partial state)
    partial_bank = BloodBank(
        id=999,
        name="Pre-existing Facility",
        city="Delhi",
        locality="Test Locality",
        source_type="demo",
        source_name="Test Source",
    )
    memory_db_session.add(partial_bank)
    memory_db_session.commit()

    assert is_database_completely_empty(memory_db_session) is False

    # Attempt to seed
    banks_seeded, reports_seeded = seed_deployment_snapshot(memory_db_session)
    assert banks_seeded == 0
    assert reports_seeded == 0

    # Only the pre-existing facility remains
    assert memory_db_session.scalar(select(func.count(BloodBank.id))) == 1
    assert memory_db_session.scalar(select(func.count(StockReport.id))) == 0


def test_seed_deployment_snapshot_missing_file_handling(memory_db_session) -> None:
    """Verify seeder gracefully handles missing fixture path."""
    non_existent = Path("data") / "non_existent_fixture.json"
    banks_seeded, reports_seeded = seed_deployment_snapshot(
        memory_db_session, snapshot_path=non_existent
    )
    assert banks_seeded == 0
    assert reports_seeded == 0
