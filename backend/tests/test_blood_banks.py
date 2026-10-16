from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.models.blood_bank import BloodBank, StockReport
from backend.app.schemas.blood_bank import (
    DEFAULT_DATA_NOTICE,
    EXTERNAL_ONLY_DATA_NOTICE,
    MIXED_DATA_NOTICE,
    build_data_notice,
)
from backend.app.seed_demo import seed_demo_data

# Use SQLite in-memory database with StaticPool for isolated, reproducible testing
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Create all tables and seed synthetic demo data fresh for each test."""
    Base.metadata.create_all(bind=test_engine)
    with TestSessionLocal() as session:
        seed_demo_data(session)
    yield
    Base.metadata.drop_all(bind=test_engine)


def test_discovery_endpoint_all_banks() -> None:
    """Verify GET /api/blood-banks returns items, count, and data notice envelope."""
    response = client.get("/api/blood-banks")
    assert response.status_code == 200
    data = response.json()

    # Verify top-level envelope contract
    assert "items" in data
    assert "count" in data
    assert "data_notice" in data
    assert data["count"] == 8
    assert len(data["items"]) == 8
    assert "synthetic demonstration data" in data["data_notice"]
    assert data["data_notice"] == DEFAULT_DATA_NOTICE

    # Verify count measures blood banks, not stock rows (which would be 64)
    total_stock_reports = sum(len(b["stock_reports"]) for b in data["items"])
    assert total_stock_reports == 64
    assert data["count"] == 8

    # Verify bank fields
    first = data["items"][0]
    assert "id" in first
    assert "name" in first
    assert "city" in first
    assert "locality" in first
    assert "stock_reports" in first
    assert len(first["stock_reports"]) == 8

    # Verify provenance metadata on stock reports
    stock = first["stock_reports"][0]
    assert stock["source_name"] == "Synthetic demo dataset"
    assert stock["verification_status"] == "demo"
    assert stock["verification_status"] != "verified"
    assert "data_timestamp" in stock
    assert stock["data_timestamp"] == "2026-10-15T12:00:00Z"
    assert "units_reported" in stock
    assert isinstance(stock["units_reported"], int)


def test_discovery_timestamp_utc_serialization() -> None:
    """Verify stock report data_timestamp serializes with an unambiguous UTC ISO 8601 'Z' suffix."""
    response = client.get("/api/blood-banks")
    assert response.status_code == 200
    data = response.json()

    for bank in data["items"]:
        for report in bank["stock_reports"]:
            ts_str = report["data_timestamp"]
            assert ts_str == "2026-10-15T12:00:00Z"
            assert ts_str.endswith("Z")

            parsed = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            assert parsed.tzinfo is not None
            assert parsed.utcoffset() == timezone.utc.utcoffset(parsed)



def test_discovery_filter_by_city_delhi() -> None:
    """Verify city filter returns only Delhi blood banks and accurate bank count."""
    response = client.get("/api/blood-banks?city=Delhi")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 4
    assert len(data["items"]) == 4
    for bank in data["items"]:
        assert bank["city"] == "Delhi"


def test_discovery_filter_by_city_lucknow() -> None:
    """Verify city filter returns only Lucknow blood banks and accurate bank count."""
    response = client.get("/api/blood-banks?city=Lucknow")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 4
    assert len(data["items"]) == 4
    for bank in data["items"]:
        assert bank["city"] == "Lucknow"


def test_discovery_filter_city_case_insensitive() -> None:
    """Verify city filter accepts lowercase inputs gracefully."""
    response_lower = client.get("/api/blood-banks?city=delhi")
    assert response_lower.status_code == 200
    data_lower = response_lower.json()
    assert data_lower["count"] == 4
    assert len(data_lower["items"]) == 4

    response_mixed = client.get("/api/blood-banks?city=luCKnow")
    assert response_mixed.status_code == 200
    data_mixed = response_mixed.json()
    assert data_mixed["count"] == 4
    assert len(data_mixed["items"]) == 4


def test_discovery_filter_invalid_city() -> None:
    """Verify invalid city query parameter returns 422 Unprocessable Entity."""
    response = client.get("/api/blood-banks?city=Mumbai")
    assert response.status_code == 422
    data = response.json()
    assert "Invalid city 'Mumbai'" in data["detail"]


def test_discovery_filter_by_blood_group() -> None:
    """Verify filtering by blood group returns matching stock reports and accurate bank count."""
    # Test encoded '+' (%2B)
    response = client.get("/api/blood-banks?blood_group=A%2B")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 8
    assert len(data["items"]) == 8
    for bank in data["items"]:
        assert len(bank["stock_reports"]) == 1
        assert bank["stock_reports"][0]["blood_group"] == "A+"

    # Test negative group '-'
    response_neg = client.get("/api/blood-banks?blood_group=O-")
    assert response_neg.status_code == 200
    data_neg = response_neg.json()
    assert data_neg["count"] == 8
    assert len(data_neg["items"]) == 8
    for bank in data_neg["items"]:
        assert len(bank["stock_reports"]) == 1
        assert bank["stock_reports"][0]["blood_group"] == "O-"


def test_discovery_filter_blood_group_space_normalization() -> None:
    """Verify raw '+' passed in URL string (which decodes to space) is normalized."""
    response = client.get("/api/blood-banks?blood_group=B ")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 8
    assert len(data["items"]) == 8
    for bank in data["items"]:
        assert bank["stock_reports"][0]["blood_group"] == "B+"


def test_discovery_filter_invalid_blood_group() -> None:
    """Verify invalid blood group query parameter returns 422 Unprocessable Entity."""
    response = client.get("/api/blood-banks?blood_group=X+")
    assert response.status_code == 422
    data = response.json()
    assert "Invalid blood group 'X+'" in data["detail"]


def test_discovery_combined_city_and_blood_group() -> None:
    """Verify combining city and blood group filters returns precise matching results."""
    response = client.get("/api/blood-banks?city=Delhi&blood_group=AB-")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 4
    assert len(data["items"]) == 4
    for bank in data["items"]:
        assert bank["city"] == "Delhi"
        assert len(bank["stock_reports"]) == 1
        assert bank["stock_reports"][0]["blood_group"] == "AB-"


def test_empty_database_returns_valid_contract() -> None:
    """Verify GET /api/blood-banks returns items: [], count: 0, and data_notice when database is empty."""
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    response = client.get("/api/blood-banks")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["count"] == 0
    assert "data_notice" in data
    assert data["data_notice"] == DEFAULT_DATA_NOTICE


def test_seed_demo_idempotency() -> None:
    """Verify running seed_demo_data on a non-empty database performs no duplicate operations."""
    with TestSessionLocal() as session:
        # Initial fixture already seeded 8 banks
        banks_count, stock_count = seed_demo_data(session)
        assert banks_count == 0
        assert stock_count == 0

        # Confirm count remains exactly 8 banks and 64 stock reports
        all_banks = session.query(BloodBank).all()
        assert len(all_banks) == 8
        all_reports = session.query(StockReport).all()
        assert len(all_reports) == 64


def test_duplicate_blood_group_constraint() -> None:
    """Verify unique constraint prevents duplicate blood groups for the same bank."""
    with TestSessionLocal() as session:
        bank = session.query(BloodBank).first()
        assert bank is not None

        duplicate_report = StockReport(
            blood_bank_id=bank.id,
            blood_group="A+",
            units_reported=5,
            source_name="Synthetic demo dataset",
            data_timestamp=datetime.now(timezone.utc),
            verification_status="demo",
        )
        session.add(duplicate_report)
        with pytest.raises(IntegrityError):
            session.commit()


def test_invalid_city_db_constraint() -> None:
    """Verify database check constraint prevents saving unauthorized cities."""
    with TestSessionLocal() as session:
        invalid_bank = BloodBank(
            name="Unauthorized City Bank",
            city="Bengaluru",
            locality="Indiranagar",
        )
        session.add(invalid_bank)
        with pytest.raises(IntegrityError):
            session.commit()


def test_invalid_blood_group_db_constraint() -> None:
    """Verify database check constraint prevents saving unauthorized blood groups."""
    with TestSessionLocal() as session:
        bank = session.query(BloodBank).first()
        assert bank is not None
        invalid_report = StockReport(
            blood_bank_id=bank.id,
            blood_group="C+",
            units_reported=10,
            source_name="Synthetic demo dataset",
            data_timestamp=datetime.now(timezone.utc),
            verification_status="demo",
        )
        session.add(invalid_report)
        with pytest.raises(IntegrityError):
            session.commit()


def test_openapi_schema_contains_blood_banks_endpoint() -> None:
    """Verify /api/blood-banks is registered in OpenAPI schema."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "/api/blood-banks" in schema["paths"]
    assert "get" in schema["paths"]["/api/blood-banks"]


def test_synthetic_dataset_integrity() -> None:
    """Verify data/demo/blood_banks.json satisfies all synthetic demonstration guidelines."""
    import json
    from pathlib import Path

    json_path = Path("data") / "demo" / "blood_banks.json"
    assert json_path.exists()

    with open(json_path, "r", encoding="utf-8") as f:
        banks = json.load(f)

    assert len(banks) >= 4
    cities = {b["city"] for b in banks}
    assert cities == {"Delhi", "Lucknow"}

    all_groups = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}
    for bank in banks:
        assert any(keyword in bank["name"] for keyword in ["Synthetic", "Demo", "Fictional"])
        bank_groups = {r["blood_group"] for r in bank["stock_reports"]}
        assert bank_groups == all_groups

        for report in bank["stock_reports"]:
            assert report["source_name"] == "Synthetic demo dataset"
            assert report["verification_status"] == "demo"
            assert report["verification_status"] != "verified"
            assert report["data_timestamp"] == "2026-10-15T12:00:00Z"
            assert isinstance(report["units_reported"], int)
            assert report["units_reported"] >= 0


class TestMixedSourceDiscoveryAndDisclaimers:
    """Tests verifying discovery API behavior with mixed synthetic demo and external data."""

    def test_build_data_notice_contract(self) -> None:
        """Verify build_data_notice returns appropriate disclaimer for each data source combination."""
        # Demo only
        assert build_data_notice(has_demo=True, has_external=False) == DEFAULT_DATA_NOTICE
        # Mixed
        assert build_data_notice(has_demo=True, has_external=True) == MIXED_DATA_NOTICE
        # External only
        assert build_data_notice(has_demo=False, has_external=True) == EXTERNAL_ONLY_DATA_NOTICE
        # Neither (defaults to DEFAULT_DATA_NOTICE)
        assert build_data_notice(has_demo=False, has_external=False) == DEFAULT_DATA_NOTICE

    def test_legacy_demo_records_preserve_unspecified_component_never_relabeled(self) -> None:
        """Verify that all seeded demo records retain blood_component='Unspecified' and are never relabeled."""
        response = client.get("/api/blood-banks")
        assert response.status_code == 200
        data = response.json()

        for bank in data["items"]:
            assert bank["source_type"] == "demo"
            for report in bank["stock_reports"]:
                assert report["blood_component"] == "Unspecified"
                assert report["blood_component"] != "Whole Blood"
                assert report["verification_status"] == "demo"

    def test_mixed_sources_notice_and_timestamp_handling(self) -> None:
        """Verify that when external facilities are present alongside demo facilities:
        1. data_notice accurately describes mixed sources.
        2. data_timestamp reflects the freshest retrieval timestamp.
        3. External stock reports maintain source provenance and unverified status.
        4. Retrieval timestamp is distinct from hospital reported timestamp.
        """
        source_ts = datetime(2026, 10, 16, 5, 30, tzinfo=timezone.utc)
        retrieval_ts = datetime(2026, 10, 16, 6, 0, tzinfo=timezone.utc)

        with TestSessionLocal() as session:
            external_bank = BloodBank(
                name="AIIMS Blood Centre",
                city="Delhi",
                locality="Ansari Nagar",
                source_type="external_source",
                source_name="e-RaktKosh",
                source_facility_id="eraktkosh:delhi:aiims_blood_centre",
                category="Government",
                facility_type="Hospital",
            )
            session.add(external_bank)
            session.flush()

            external_report = StockReport(
                blood_bank_id=external_bank.id,
                blood_group="O+",
                blood_component="Packed Red Blood Cells",
                units_reported=24,
                source_name="e-RaktKosh",
                verification_status="reported_unverified",
                source_reported_timestamp=source_ts,
                retrieval_timestamp=retrieval_ts,
                data_timestamp=retrieval_ts,
            )
            session.add(external_report)
            session.commit()

        response = client.get("/api/blood-banks?city=Delhi")
        assert response.status_code == 200
        data = response.json()

        # Envelope check
        assert data["data_notice"] == MIXED_DATA_NOTICE
        assert "e-RaktKosh" in data["data_notice"]
        assert "does not guarantee real-time physical blood availability" in data["data_notice"]
        assert data["data_timestamp"] == "2026-10-16T06:00:00Z"

        # Check external item
        aiims = next(b for b in data["items"] if b["name"] == "AIIMS Blood Centre")
        assert aiims["source_type"] == "external_source"
        assert aiims["source_facility_id"] == "eraktkosh:delhi:aiims_blood_centre"
        assert aiims["category"] == "Government"

        assert len(aiims["stock_reports"]) == 1
        rep = aiims["stock_reports"][0]
        assert rep["blood_group"] == "O+"
        assert rep["blood_component"] == "Packed Red Blood Cells"
        assert rep["verification_status"] == "reported_unverified"
        assert rep["source_reported_timestamp"] == "2026-10-16T05:30:00Z"
        assert rep["retrieval_timestamp"] == "2026-10-16T06:00:00Z"
        # Source reported is distinct from retrieval
        assert rep["source_reported_timestamp"] != rep["retrieval_timestamp"]

    def test_external_only_notice_when_no_demo_data_matches(self) -> None:
        """Verify EXTERNAL_ONLY_DATA_NOTICE is used when all returned records are external sources."""
        retrieval_ts = datetime(2026, 10, 16, 6, 15, tzinfo=timezone.utc)

        with TestSessionLocal() as session:
            # Remove all demo records for this test
            session.query(StockReport).delete()
            session.query(BloodBank).delete()

            external_bank = BloodBank(
                name="SGPGI Blood Bank",
                city="Lucknow",
                locality="Raebareli Road",
                source_type="external_source",
                source_name="e-RaktKosh",
                source_facility_id="eraktkosh:lucknow:sgpgi",
            )
            session.add(external_bank)
            session.flush()

            report = StockReport(
                blood_bank_id=external_bank.id,
                blood_group="AB+",
                blood_component="Whole Blood",
                units_reported=10,
                source_name="e-RaktKosh",
                verification_status="reported_unverified",
                retrieval_timestamp=retrieval_ts,
                data_timestamp=retrieval_ts,
            )
            session.add(report)
            session.commit()

        response = client.get("/api/blood-banks")
        assert response.status_code == 200
        data = response.json()

        assert data["count"] == 1
        assert data["data_notice"] == EXTERNAL_ONLY_DATA_NOTICE
        assert "synthetic" not in data["data_notice"].lower()
        assert "e-RaktKosh" in data["data_notice"]
        assert data["data_timestamp"] == "2026-10-16T06:15:00Z"

    def test_live_badge_freshness_in_api(self) -> None:
        """Verify portal live stock badge freshness indicator is serialized without inventing timestamps."""
        retrieval_ts = datetime(2026, 10, 16, 6, 20, tzinfo=timezone.utc)

        with TestSessionLocal() as session:
            external_bank = BloodBank(
                name="Ram Manohar Lohia Hospital Blood Centre",
                city="Delhi",
                locality="Connaught Place",
                source_type="external_source",
                source_name="e-RaktKosh",
                source_facility_id="eraktkosh:delhi:rml_hospital",
            )
            session.add(external_bank)
            session.flush()

            report = StockReport(
                blood_bank_id=external_bank.id,
                blood_group="B+",
                blood_component="Whole Blood",
                units_reported=15,
                source_name="e-RaktKosh",
                verification_status="reported_unverified",
                freshness_indicator="live_stock_badge",
                source_reported_timestamp=None,  # Portal provides live stock badge, not exact datetime
                retrieval_timestamp=retrieval_ts,
                data_timestamp=retrieval_ts,
            )
            session.add(report)
            session.commit()

        response = client.get("/api/blood-banks?blood_group=B%2B")
        assert response.status_code == 200
        data = response.json()

        rml = next(b for b in data["items"] if b["name"] == "Ram Manohar Lohia Hospital Blood Centre")
        report = rml["stock_reports"][0]
        assert report["freshness_indicator"] == "live_stock_badge"
        assert report["source_reported_timestamp"] is None
        assert report["retrieval_timestamp"] == "2026-10-16T06:20:00Z"
