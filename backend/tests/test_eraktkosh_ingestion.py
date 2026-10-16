from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.database import Base
from backend.app.models.blood_bank import BloodBank, StockReport
from backend.app.seed_demo import seed_demo_data
from backend.app.services.eraktkosh.client import (
    CITY_QUERY_CONFIG,
    ERAKTKOSH_STOCK_URL,
    ERaktKoshClient,
    ERaktKoshRetrievalError,
)
from backend.app.services.eraktkosh.identity import generate_facility_source_id
from backend.app.services.eraktkosh.ingestion import (
    CityIngestionResult,
    ERaktKoshIngestionError,
    ingest_city_from_source,
    ingest_eraktkosh_city_payload,
    run_ingestion_cli,
)
from backend.app.services.eraktkosh.types import (
    DEFAULT_ERAKTKOSH_SOURCE,
    STATUS_REPORTED_UNVERIFIED,
)

FIXTURES_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "synthetic_eraktkosh_response.json"
)


@pytest.fixture
def synthetic_payload() -> dict[str, Any]:
    with open(FIXTURES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def db_session():
    """In-memory SQLite database session isolated for ingestion testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session_with_demo(db_session: Session) -> Session:
    """Database session pre-seeded with the 8 demo blood banks and 64 stock reports."""
    seed_demo_data(db_session)
    return db_session


class TestERaktKoshClient:
    """Verify HTTP client parameter construction, timeouts, and error handling."""

    def test_client_constructs_verified_public_query_parameters(self) -> None:
        client = ERaktKoshClient()
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"draw": 1, "data": []}

        # Test Delhi query
        with patch("httpx.Client.get", return_value=mock_resp) as mock_get:
            client.fetch_stock_details("Delhi")
            mock_get.assert_called_once()
            args, kwargs = mock_get.call_args
            assert args[0] == ERAKTKOSH_STOCK_URL
            params = kwargs["params"]
            assert params["hmode"] == "GETNEARBYSTOCKDETAILS"
            assert params["stateCode"] == "97"
            assert params["districtCode"] == "-1"
            assert params["bloodGroup"] == "all"
            assert params["bloodComponent"] == "11"

        # Test Lucknow query
        with patch("httpx.Client.get", return_value=mock_resp) as mock_get:
            client.fetch_stock_details("Lucknow")
            mock_get.assert_called_once()
            _, kwargs = mock_get.call_args
            params = kwargs["params"]
            assert params["stateCode"] == "99"
            assert params["districtCode"] == "157"
            assert params["bloodComponent"] == "11"

    def test_client_handles_timeout_error(self) -> None:
        client = ERaktKoshClient(timeout=5.0)
        with patch(
            "httpx.Client.get",
            side_effect=httpx.TimeoutException("Timed out connecting"),
        ):
            with pytest.raises(ERaktKoshRetrievalError) as exc_info:
                client.fetch_stock_details("Delhi")
            assert "timeout" in str(exc_info.value).lower()

    def test_client_handles_non_200_http_response(self) -> None:
        client = ERaktKoshClient()
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 503
        with patch("httpx.Client.get", return_value=mock_resp):
            with pytest.raises(ERaktKoshRetrievalError) as exc_info:
                client.fetch_stock_details("Delhi")
            assert "503" in str(exc_info.value)

    def test_client_handles_malformed_json_envelope(self) -> None:
        client = ERaktKoshClient()
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        # Missing "data" key
        mock_resp.json.return_value = {"error": "unexpected format"}

        with patch("httpx.Client.get", return_value=mock_resp):
            with pytest.raises(ERaktKoshRetrievalError) as exc_info:
                client.fetch_stock_details("Delhi")
            assert "missing or invalid 'data'" in str(exc_info.value)

    def test_client_rejects_unsupported_city(self) -> None:
        client = ERaktKoshClient()
        with pytest.raises(ValueError) as exc_info:
            client.fetch_stock_details("Bengaluru")
        assert "unsupported city" in str(exc_info.value).lower()

    def test_client_rejects_unsupported_component(self) -> None:
        client = ERaktKoshClient()
        with pytest.raises(ValueError) as exc_info:
            client.fetch_stock_details("Delhi", component="Cryoprecipitate")
        assert "unsupported component" in str(exc_info.value).lower()


class TestFacilityIdentityGeneration:
    """Verify deterministic fallback identity slug creation and bounds."""

    def test_deterministic_facility_id(self) -> None:
        id1 = generate_facility_source_id("Delhi", "AIIMS Blood Bank", "Ansari Nagar")
        id2 = generate_facility_source_id("Delhi", "AIIMS Blood Bank", "Ansari Nagar")
        assert id1 == id2
        assert id1 == "eraktkosh:delhi:aiims-blood-bank:ansari-nagar"

    def test_length_constraint_under_100_characters(self) -> None:
        # Create an extremely long name and locality
        long_name = "Super Speciality Regional Blood Transfusion Center and Research Foundation " * 3
        long_loc = "Outer Ring Road Extension Commercial Complex Sector 128 " * 3
        slug = generate_facility_source_id("Delhi", long_name, long_loc)

        assert len(slug) <= 100
        assert slug.startswith("eraktkosh:delhi:")
        # Deterministic SHA suffix appended
        assert "-" in slug

        # Ensure repeated calls with same long input produce identical slug
        slug2 = generate_facility_source_id("Delhi", long_name, long_loc)
        assert slug == slug2

    def test_distinct_localities_produce_distinct_ids(self) -> None:
        id_saket = generate_facility_source_id("Delhi", "Apollo Depot", "Saket")
        id_rohini = generate_facility_source_id("Delhi", "Apollo Depot", "Rohini")
        assert id_saket != id_rohini


class TestIngestionDatabaseIntegration:
    """Verify parsing-to-database ingestion, idempotence, reconciliation, and demo separation."""

    def test_parsing_to_database_integration(
        self, db_session: Session, synthetic_payload: dict[str, Any]
    ) -> None:
        delhi_payload = synthetic_payload["synthetic_delhi_response"]
        fixed_retrieval_time = datetime(2026, 10, 16, 6, 0, 0, tzinfo=timezone.utc)

        result = ingest_eraktkosh_city_payload(
            db=db_session,
            city="Delhi",
            payload=delhi_payload,
            component="Whole Blood",
            apply=True,
            retrieval_timestamp=fixed_retrieval_time,
        )

        assert not result.is_dry_run
        assert result.city == "Delhi"
        assert result.source_rows_count == 5
        assert result.successful_rows_count == 5
        assert result.failed_rows_count == 0
        assert result.facilities_created == 5
        assert result.reports_upserted == 6

        # Check BloodBank records in database
        banks = db_session.scalars(
            select(BloodBank).where(BloodBank.city == "Delhi").order_by(BloodBank.id.asc())
        ).all()
        assert len(banks) == 5

        for bank in banks:
            assert bank.source_type == "external_source"
            assert bank.source_name == DEFAULT_ERAKTKOSH_SOURCE
            assert bank.source_facility_id is not None
            assert bank.source_facility_id.startswith("eraktkosh:delhi:")
            # Invariant: Contact info strictly redacted from raw_address and locality
            if bank.raw_address:
                assert "@" not in bank.raw_address
                assert "phone" not in bank.raw_address.lower()
                assert "fax" not in bank.raw_address.lower()

        # Check StockReport records in database
        reports = db_session.scalars(
            select(StockReport).order_by(StockReport.id.asc())
        ).all()
        assert len(reports) == 6

        for r in reports:
            assert r.blood_component == "Whole Blood"
            assert r.source_name == DEFAULT_ERAKTKOSH_SOURCE
            assert r.verification_status == STATUS_REPORTED_UNVERIFIED
            assert r.retrieval_timestamp == fixed_retrieval_time
            assert r.units_reported > 0

        # Row 1 (AIIMS): Available, B+: 5, O+: 8 with source timestamp
        aiims_bank = db_session.scalar(
            select(BloodBank).where(BloodBank.name.like("%AIIMS%"))
        )
        assert aiims_bank is not None
        aiims_reports = {r.blood_group: r for r in aiims_bank.stock_reports}
        assert set(aiims_reports.keys()) == {"B+", "O+"}
        assert aiims_reports["B+"].units_reported == 5
        assert aiims_reports["O+"].units_reported == 8
        assert aiims_reports["B+"].source_reported_timestamp is not None

        # Row 2 (Safdarjung): Whole Blood Not Available -> 0 stock reports created
        safdarjung_bank = db_session.scalar(
            select(BloodBank).where(BloodBank.name.like("%SAFDARJUNG%"))
        )
        assert safdarjung_bank is not None
        assert len(safdarjung_bank.stock_reports) == 0

    def test_dry_run_leaves_database_untouched(
        self, db_session: Session, synthetic_payload: dict[str, Any]
    ) -> None:
        delhi_payload = synthetic_payload["synthetic_delhi_response"]

        result = ingest_eraktkosh_city_payload(
            db=db_session,
            city="Delhi",
            payload=delhi_payload,
            component="Whole Blood",
            apply=False,  # Dry run
        )

        assert result.is_dry_run
        assert result.source_rows_count == 5
        assert result.facilities_created == 5
        assert result.reports_upserted == 6

        # Database must remain completely empty
        bank_count = db_session.scalar(select(func.count(BloodBank.id)))
        report_count = db_session.scalar(select(func.count(StockReport.id)))
        assert bank_count == 0
        assert report_count == 0

    def test_repeated_ingestion_is_idempotent(
        self, db_session: Session, synthetic_payload: dict[str, Any]
    ) -> None:
        delhi_payload = synthetic_payload["synthetic_delhi_response"]

        # First ingestion
        res1 = ingest_eraktkosh_city_payload(
            db=db_session,
            city="Delhi",
            payload=delhi_payload,
            component="Whole Blood",
            apply=True,
        )
        assert res1.facilities_created == 5
        assert res1.reports_upserted == 6

        bank_count_1 = db_session.scalar(select(func.count(BloodBank.id)))
        report_count_1 = db_session.scalar(select(func.count(StockReport.id)))
        assert bank_count_1 == 5
        assert report_count_1 == 6

        # Second ingestion with exact same payload
        res2 = ingest_eraktkosh_city_payload(
            db=db_session,
            city="Delhi",
            payload=delhi_payload,
            component="Whole Blood",
            apply=True,
        )
        assert res2.facilities_created == 0
        assert res2.facilities_updated == 0
        assert res2.facilities_unchanged == 5
        assert res2.reports_created == 0
        assert res2.reports_updated == 0
        assert res2.reports_unchanged == 6
        assert res2.reports_upserted == 6
        assert res2.reports_withdrawn == 0

        bank_count_2 = db_session.scalar(select(func.count(BloodBank.id)))
        report_count_2 = db_session.scalar(select(func.count(StockReport.id)))
        assert bank_count_2 == bank_count_1
        assert report_count_2 == report_count_1

    def test_intra_payload_duplicate_facilities_deduplicated(
        self, db_session: Session
    ) -> None:
        # Construct payload with two rows for the exact same facility
        duplicate_payload = {
            "draw": 1,
            "data": [
                [
                    "1",
                    "SYNTHETIC AIIMS BLOOD BANK<br/>Ansari Nagar, New Delhi 110029",
                    "Govt.",
                    "<p>Available, B+Ve:2</p>",
                    "2026-10-16 02:00:00",
                    "Blood Bank",
                ],
                [
                    "2",
                    "SYNTHETIC AIIMS BLOOD BANK<br/>Ansari Nagar, New Delhi 110029",
                    "Govt.",
                    "<p>Available, B+Ve:5, O+Ve:3</p>",
                    "2026-10-16 04:00:00",
                    "Blood Bank",
                ],
            ],
        }

        result = ingest_eraktkosh_city_payload(
            db=db_session,
            city="Delhi",
            payload=duplicate_payload,
            component="Whole Blood",
            apply=True,
        )

        assert result.facilities_created == 1
        bank = db_session.scalar(select(BloodBank))
        assert bank is not None
        assert len(bank.stock_reports) == 2
        groups = {r.blood_group: r.units_reported for r in bank.stock_reports}
        # Newer / higher units preserved
        assert groups["B+"] == 5
        assert groups["O+"] == 3

    def test_invalid_rows_partial_rejection(self, db_session: Session) -> None:
        mixed_payload = {
            "draw": 1,
            "data": [
                [
                    "1",
                    "SYNTHETIC VALID BLOOD BANK<br/>Connaught Place, New Delhi 110001",
                    "Govt.",
                    "<p>Available, A+Ve:10</p>",
                    "2026-10-16 05:00:00",
                    "Blood Bank",
                ],
                # Malformed row: missing required HTML elements
                [
                    "2",
                    "Phone: 9999999999",  # Only phone, no facility name
                    "Govt.",
                    "<p>Available, B+Ve:5</p>",
                    "2026-10-16 05:00:00",
                    "Blood Bank",
                ],
            ],
        }

        result = ingest_eraktkosh_city_payload(
            db=db_session,
            city="Delhi",
            payload=mixed_payload,
            component="Whole Blood",
            apply=True,
        )

        assert result.source_rows_count == 2
        assert result.successful_rows_count == 1
        assert result.failed_rows_count == 1
        assert result.facilities_created == 1
        assert len(result.warnings) > 0

        bank = db_session.scalar(select(BloodBank))
        assert bank is not None
        assert bank.name == "SYNTHETIC VALID BLOOD BANK"

    def test_unavailable_stock_reconciliation(self, db_session: Session) -> None:
        # Snapshot 1: Facility reports B+: 5 and O+: 8
        snapshot_1 = {
            "draw": 1,
            "data": [
                [
                    "1",
                    "SYNTHETIC AIIMS BLOOD BANK<br/>Ansari Nagar, New Delhi 110029",
                    "Govt.",
                    "<p>Available, B+Ve:5, O+Ve:8</p>",
                    "2026-10-16 02:00:00",
                    "Blood Bank",
                ]
            ],
        }
        ingest_eraktkosh_city_payload(
            db=db_session,
            city="Delhi",
            payload=snapshot_1,
            component="Whole Blood",
            apply=True,
        )
        bank = db_session.scalar(select(BloodBank))
        assert bank is not None
        assert len(bank.stock_reports) == 2

        # Snapshot 2: Same facility reports "Whole Blood Not Available"
        snapshot_2 = {
            "draw": 2,
            "data": [
                [
                    "1",
                    "SYNTHETIC AIIMS BLOOD BANK<br/>Ansari Nagar, New Delhi 110029",
                    "Govt.",
                    "<p><b>Whole Blood</b>Not Available Search for another Component</p>",
                    "2026-10-16 06:00:00",
                    "Blood Bank",
                ]
            ],
        }
        res2 = ingest_eraktkosh_city_payload(
            db=db_session,
            city="Delhi",
            payload=snapshot_2,
            component="Whole Blood",
            apply=True,
        )
        assert res2.reports_withdrawn == 2

        # Facility survives, but stock reports are withdrawn
        db_session.refresh(bank)
        assert len(bank.stock_reports) == 0

    def test_withdrawn_blood_group_reconciliation(self, db_session: Session) -> None:
        # Snapshot 1: Reports B+: 5, O+: 8
        snapshot_1 = {
            "draw": 1,
            "data": [
                [
                    "1",
                    "SYNTHETIC RED CROSS<br/>Central Delhi, Delhi 110001",
                    "Charitable",
                    "<p>Available, B+Ve:5, O+Ve:8</p>",
                    "2026-10-16 02:00:00",
                    "Blood Bank",
                ]
            ],
        }
        ingest_eraktkosh_city_payload(
            db=db_session,
            city="Delhi",
            payload=snapshot_1,
            component="Whole Blood",
            apply=True,
        )

        # Snapshot 2: Reports only B+: 9 (O+ is no longer reported)
        snapshot_2 = {
            "draw": 2,
            "data": [
                [
                    "1",
                    "SYNTHETIC RED CROSS<br/>Central Delhi, Delhi 110001",
                    "Charitable",
                    "<p>Available, B+Ve:9</p>",
                    "2026-10-16 07:00:00",
                    "Blood Bank",
                ]
            ],
        }
        res2 = ingest_eraktkosh_city_payload(
            db=db_session,
            city="Delhi",
            payload=snapshot_2,
            component="Whole Blood",
            apply=True,
        )
        assert res2.reports_upserted == 1
        assert res2.reports_withdrawn == 1

        bank = db_session.scalar(select(BloodBank))
        assert bank is not None
        assert len(bank.stock_reports) == 1
        assert bank.stock_reports[0].blood_group == "B+"
        assert bank.stock_reports[0].units_reported == 9

    def test_unreported_group_never_converted_to_zero_stock(
        self, db_session: Session
    ) -> None:
        payload = {
            "draw": 1,
            "data": [
                [
                    "1",
                    "SYNTHETIC DEPOT<br/>Saket, New Delhi 110017",
                    "Govt.",
                    "<p>Available, A+Ve:4</p>",
                    "2026-10-16 05:00:00",
                    "Blood Bank",
                ]
            ],
        }
        ingest_eraktkosh_city_payload(
            db=db_session,
            city="Delhi",
            payload=payload,
            component="Whole Blood",
            apply=True,
        )

        bank = db_session.scalar(select(BloodBank))
        assert bank is not None
        # Only A+ was reported
        assert len(bank.stock_reports) == 1
        assert bank.stock_reports[0].blood_group == "A+"
        # Invariant: No zero-stock rows created for unreported groups
        zero_stock_reports = db_session.scalars(
            select(StockReport).where(StockReport.units_reported == 0)
        ).all()
        assert len(zero_stock_reports) == 0

    def test_transactional_rollback_on_failure(self, db_session: Session) -> None:
        payload = {
            "draw": 1,
            "data": [
                [
                    "1",
                    "SYNTHETIC DEPOT<br/>Saket, New Delhi 110017",
                    "Govt.",
                    "<p>Available, A+Ve:4</p>",
                    "2026-10-16 05:00:00",
                    "Blood Bank",
                ]
            ],
        }

        # Mock an exception during commit to verify rollback
        with patch.object(db_session, "commit", side_effect=RuntimeError("Simulated DB Disk Failure")):
            with pytest.raises(ERaktKoshIngestionError) as exc_info:
                ingest_eraktkosh_city_payload(
                    db=db_session,
                    city="Delhi",
                    payload=payload,
                    component="Whole Blood",
                    apply=True,
                )
            assert "Transactional database update failed" in str(exc_info.value)

        # Database must have rolled back cleanly
        bank_count = db_session.scalar(select(func.count(BloodBank.id)))
        assert bank_count == 0

    def test_demo_and_external_strict_separation(
        self, db_session_with_demo: Session, synthetic_payload: dict[str, Any]
    ) -> None:
        # Check initial demo baseline
        demo_bank_count = db_session_with_demo.scalar(
            select(func.count(BloodBank.id)).where(BloodBank.source_type == "demo")
        )
        demo_report_count = db_session_with_demo.scalar(
            select(func.count(StockReport.id)).where(StockReport.verification_status == "demo")
        )
        assert demo_bank_count == 8
        assert demo_report_count == 64

        # Create an external facility that shares the exact name of Demo Central Transfusion Facility
        demo_bank = db_session_with_demo.scalar(
            select(BloodBank).where(BloodBank.id == 1)
        )
        assert demo_bank is not None
        shared_name = demo_bank.name

        collision_payload = {
            "draw": 1,
            "data": [
                [
                    "1",
                    f"{shared_name}<br/>Connaught Place, New Delhi 110001",
                    "Govt.",
                    "<p>Available, AB+Ve:7</p>",
                    "2026-10-16 05:00:00",
                    "Blood Bank",
                ]
            ],
        }

        # Ingest external facility
        res = ingest_eraktkosh_city_payload(
            db=db_session_with_demo,
            city="Delhi",
            payload=collision_payload,
            component="Whole Blood",
            apply=True,
        )
        assert res.facilities_created == 1

        # Confirm both facilities coexist independently with separate IDs and source_type
        banks_with_shared_name = db_session_with_demo.scalars(
            select(BloodBank).where(BloodBank.name == shared_name)
        ).all()
        assert len(banks_with_shared_name) == 2

        types = {b.source_type for b in banks_with_shared_name}
        assert types == {"demo", "external_source"}

        # Demo stock reports remain untouched
        after_demo_bank_count = db_session_with_demo.scalar(
            select(func.count(BloodBank.id)).where(BloodBank.source_type == "demo")
        )
        after_demo_report_count = db_session_with_demo.scalar(
            select(func.count(StockReport.id)).where(StockReport.verification_status == "demo")
        )
        assert after_demo_bank_count == 8
        assert after_demo_report_count == 64

    def test_lucknow_ingestion(
        self, db_session: Session, synthetic_payload: dict[str, Any]
    ) -> None:
        lucknow_payload = synthetic_payload["synthetic_lucknow_response"]

        res = ingest_eraktkosh_city_payload(
            db=db_session,
            city="Lucknow",
            payload=lucknow_payload,
            component="Whole Blood",
            apply=True,
        )

        assert res.city == "Lucknow"
        assert res.source_rows_count == 3
        assert res.successful_rows_count == 3
        # Row 1: KGMU (A+:10, B+:14, O+:6) = 3
        # Row 2: SGPGI (AB+:3) = 1
        # Row 3: CHARITABLE LUCKNOW TRUST (Not Available) = 0
        assert res.reports_upserted == 4

        lucknow_banks = db_session.scalars(
            select(BloodBank).where(BloodBank.city == "Lucknow")
        ).all()
        assert len(lucknow_banks) == 3


class TestIngestionCLI:
    """Verify CLI dry run, apply mode, and error handling."""

    @pytest.fixture
    def isolated_session_factory(self):
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        yield factory
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

    def test_cli_dry_run_with_fixture(self, capsys, isolated_session_factory) -> None:
        exit_code = run_ingestion_cli(
            ["--city", "Delhi", "--fixture", str(FIXTURES_PATH)],
            session_factory=isolated_session_factory,
        )
        assert exit_code == 0
        captured = capsys.readouterr().out
        assert "DRY RUN" in captured
        assert "Source rows retrieved:    5" in captured
        assert "Database was NOT modified" in captured

    def test_cli_apply_with_fixture(self, capsys, isolated_session_factory) -> None:
        exit_code = run_ingestion_cli(
            ["--city", "Delhi", "--fixture", str(FIXTURES_PATH), "--apply"],
            session_factory=isolated_session_factory,
        )
        assert exit_code == 0
        captured = capsys.readouterr().out
        assert "LIVE APPLY" in captured
        assert "Database updated transactionally" in captured

        with isolated_session_factory() as s:
            banks = s.scalars(select(BloodBank)).all()
            assert len(banks) == 5

    def test_cli_missing_fixture(self, capsys, isolated_session_factory) -> None:
        exit_code = run_ingestion_cli(
            ["--city", "Delhi", "--fixture", "nonexistent_file.json"],
            session_factory=isolated_session_factory,
        )
        assert exit_code == 1
        captured = capsys.readouterr().out
        assert "Fixture file not found" in captured


class TestAmbiguityAndPlaceholderIdentityIntegration:
    """Verify identity fallback, collision detection, and safe reconciliation for placeholder rows."""

    def test_identity_fallback_uses_address_when_name_missing_or_placeholder(self) -> None:
        id_redcross = generate_facility_source_id(
            city="Delhi",
            facility_name="-",
            locality="Sansad Marg Area",
            raw_address="1, Red Cross Road, Sansad Marg Area, New Delhi",
        )
        assert "1-red-cross-road" in id_redcross
        assert "facility:unspecified" not in id_redcross

        id_plot = generate_facility_source_id(
            city="Delhi",
            facility_name="--",
            locality="Delhi NCR",
            raw_address="Plot No. 1, Sector 10, New Delhi",
        )
        assert "plot-no-1-sector-10" in id_plot
        assert "facility:unspecified" not in id_plot

        # Critical invariant: distinct rows with placeholder names NEVER share the same fallback identity
        assert id_redcross != id_plot

    def test_observed_delhi_placeholder_cases_generate_distinct_ids(self) -> None:
        id_lady = generate_facility_source_id(
            city="Delhi",
            facility_name="Lady Hardinge Medical College",
            locality="Connaught Place",
            raw_address="Shaheed Bhagat Singh Marg, Connaught Place, New Delhi",
        )
        id_aiims = generate_facility_source_id(
            city="Delhi",
            facility_name="Blood Centre main Hospital, AIIMS Campus",
            locality="Ansari Nagar East",
            raw_address="Ansari Nagar East, New Delhi",
        )
        id_redcross = generate_facility_source_id(
            city="Delhi",
            facility_name="1, Red Cross Road, Sansad Marg Area, New Delhi",
            locality="Sansad Marg Area",
            raw_address="1, Red Cross Road, Sansad Marg Area, New Delhi",
        )

        assert id_lady.startswith("eraktkosh:delhi:")
        assert id_aiims.startswith("eraktkosh:delhi:")
        assert id_redcross.startswith("eraktkosh:delhi:")

        # All 3 observed cases must be mutually distinct
        assert len({id_lady, id_aiims, id_redcross}) == 3
        for fid in [id_lady, id_aiims, id_redcross]:
            assert len(fid) <= 100

    def test_ambiguous_facility_collision_flagged_and_rejected(
        self, db_session: Session
    ) -> None:
        # Construct payload where two rows map to the same slug but have conflicting addresses
        ambiguous_payload = {
            "draw": 1,
            "data": [
                [
                    "1",
                    "APEX BLOOD CENTRE<br/>10 Ring Road, Lajpat Nagar, New Delhi",
                    "Private",
                    "<p>Available, A+Ve:5</p>",
                    "2026-10-16 02:00:00",
                    "Blood Bank",
                ],
                [
                    "2",
                    "APEX BLOOD CENTRE<br/>50 Outer Ring Road, Lajpat Nagar, New Delhi",
                    "Private",
                    "<p>Available, B+Ve:3</p>",
                    "2026-10-16 04:00:00",
                    "Blood Bank",
                ],
            ],
        }

        # Mock generate_facility_source_id to simulate an unforeseen collision
        with patch(
            "backend.app.services.eraktkosh.ingestion.generate_facility_source_id",
            return_value="eraktkosh:delhi:apex-blood-centre:lajpat-nagar",
        ):
            res = ingest_eraktkosh_city_payload(
                db=db_session,
                city="Delhi",
                payload=ambiguous_payload,
                component="Whole Blood",
                apply=True,
            )

        # Invariant: Colliding rows must be flagged as ambiguous and rejected, not silently merged
        assert res.facilities_created == 0
        assert any("Ambiguous facility identity collision" in w for w in res.warnings)

        # Database must have zero external banks created
        banks = db_session.scalars(select(BloodBank)).all()
        assert len(banks) == 0

    def test_unavailable_stock_reconciliation_scoped_strictly_without_cross_facility_withdrawal(
        self, db_session: Session
    ) -> None:
        # Snapshot containing two distinct facilities:
        # Facility A reports Available O+: 8
        # Facility B reports Whole Blood Not Available
        payload = {
            "draw": 1,
            "data": [
                [
                    "1",
                    "-<br/>1, Red Cross Road, Sansad Marg Area, New Delhi<br/>-",
                    "Charitable",
                    "<p>Available, O+Ve:8</p>",
                    "2026-10-16 03:00:00",
                    "Blood Bank",
                ],
                [
                    "2",
                    "-<br/>Plot No. 1, Sector 10, New Delhi<br/>-",
                    "Govt.",
                    "<p><b>Whole Blood</b>Not Available Search for another Component</p>",
                    "2026-10-16 03:00:00",
                    "Blood Bank",
                ],
            ],
        }

        res = ingest_eraktkosh_city_payload(
            db=db_session,
            city="Delhi",
            payload=payload,
            component="Whole Blood",
            apply=True,
        )

        assert res.facilities_created == 2
        assert res.reports_upserted == 1

        # Check Facility A
        fac_a = db_session.scalar(
            select(BloodBank).where(BloodBank.name.like("%Red Cross Road%"))
        )
        assert fac_a is not None
        assert len(fac_a.stock_reports) == 1
        assert fac_a.stock_reports[0].blood_group == "O+"
        assert fac_a.stock_reports[0].units_reported == 8

        # Check Facility B
        fac_b = db_session.scalar(
            select(BloodBank).where(BloodBank.name.like("%Plot No. 1%"))
        )
        assert fac_b is not None
        # Invariant: Facility B reports no stock, but Facility A's stock is untouched!
        assert len(fac_b.stock_reports) == 0


class TestHardenIngestionReconciliation:
    """Regression tests for Step 3L fail-safe reconciliation invariants."""

    def test_omitted_facility_in_partial_snapshot_never_withdrawn(
        self, db_session: Session
    ) -> None:
        """A facility missing from a source response must not automatically have its
        existing stock reports deleted or marked unavailable.
        """
        # Step 1: Snapshot with Facility Alpha (2 reports) and Facility Beta (1 report)
        snapshot_1 = {
            "draw": 1,
            "data": [
                [
                    "1",
                    "FACILITY ALPHA<br/>Connaught Place, New Delhi 110001",
                    "Govt.",
                    "<p>Available, B+Ve:5, O+Ve:10</p>",
                    "2026-10-16 02:00:00",
                    "Blood Bank",
                ],
                [
                    "2",
                    "FACILITY BETA<br/>Saket, New Delhi 110017",
                    "Private",
                    "<p>Available, A+Ve:8</p>",
                    "2026-10-16 02:00:00",
                    "Blood Bank",
                ],
            ],
        }

        res1 = ingest_eraktkosh_city_payload(
            db=db_session,
            city="Delhi",
            payload=snapshot_1,
            component="Whole Blood",
            apply=True,
        )
        assert res1.facilities_created == 2
        assert res1.reports_upserted == 3

        # Step 2: Ingest partial snapshot where Facility Beta is completely OMITTED
        # Facility Alpha updates B+ to 7 and drops O+
        snapshot_2 = {
            "draw": 2,
            "data": [
                [
                    "1",
                    "FACILITY ALPHA<br/>Connaught Place, New Delhi 110001",
                    "Govt.",
                    "<p>Available, B+Ve:7</p>",
                    "2026-10-16 06:00:00",
                    "Blood Bank",
                ]
            ],
        }

        res2 = ingest_eraktkosh_city_payload(
            db=db_session,
            city="Delhi",
            payload=snapshot_2,
            component="Whole Blood",
            apply=True,
        )

        # Invariant 1: Only 1 report was withdrawn (Facility Alpha's O+)
        assert res2.reports_withdrawn == 1
        assert res2.reports_updated == 1

        # Invariant 2: Facility Beta is still in DB with its stock intact!
        beta = db_session.scalar(
            select(BloodBank).where(BloodBank.name == "FACILITY BETA")
        )
        assert beta is not None
        assert len(beta.stock_reports) == 1
        assert beta.stock_reports[0].blood_group == "A+"
        assert beta.stock_reports[0].units_reported == 8

        # Invariant 3: Facility Alpha has only B+ at 7 units
        alpha = db_session.scalar(
            select(BloodBank).where(BloodBank.name == "FACILITY ALPHA")
        )
        assert alpha is not None
        assert len(alpha.stock_reports) == 1
        assert alpha.stock_reports[0].blood_group == "B+"
        assert alpha.stock_reports[0].units_reported == 7

    def test_reconcile_scope_city_permanently_rejected(
        self, db_session: Session
    ) -> None:
        """City-wide reconciliation must be prevented unless completeness can be independently proved."""
        empty_payload = {"draw": 1, "data": []}

        with pytest.raises(ValueError) as exc_info:
            ingest_eraktkosh_city_payload(
                db=db_session,
                city="Delhi",
                payload=empty_payload,
                reconcile_scope="city",
            )
        assert "City-wide reconciliation is disabled for e-RaktKosh" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info2:
            ingest_eraktkosh_city_payload(
                db=db_session,
                city="Delhi",
                payload=empty_payload,
                reconcile_scope="unknown_scope",
            )
        assert "Unsupported reconcile_scope" in str(exc_info2.value)

    def test_explicit_unavailable_scoped_strictly_to_facility_group_and_component(
        self, db_session: Session
    ) -> None:
        """Explicit unavailable stock affects only the matching facility and component."""
        # 1. Facility A has Whole Blood and PRBC
        # 2. Facility B has Whole Blood
        fac_a = BloodBank(
            name="FACILITY A",
            city="Delhi",
            locality="Karol Bagh",
            source_type="external_source",
            source_name=DEFAULT_ERAKTKOSH_SOURCE,
            source_facility_id="eraktkosh:delhi:facility-a:karol-bagh",
            raw_address="Karol Bagh, New Delhi",
        )
        fac_b = BloodBank(
            name="FACILITY B",
            city="Delhi",
            locality="Dwarka",
            source_type="external_source",
            source_name=DEFAULT_ERAKTKOSH_SOURCE,
            source_facility_id="eraktkosh:delhi:facility-b:dwarka",
            raw_address="Dwarka, New Delhi",
        )
        db_session.add_all([fac_a, fac_b])
        db_session.flush()

        now_utc = datetime.now(timezone.utc)
        rep_a_wb = StockReport(
            blood_bank_id=fac_a.id,
            blood_group="B+",
            blood_component="Whole Blood",
            units_reported=5,
            source_name=DEFAULT_ERAKTKOSH_SOURCE,
            data_timestamp=now_utc,
            verification_status=STATUS_REPORTED_UNVERIFIED,
        )
        rep_a_prbc = StockReport(
            blood_bank_id=fac_a.id,
            blood_group="B+",
            blood_component="Packed Red Blood Cells",
            units_reported=12,
            source_name=DEFAULT_ERAKTKOSH_SOURCE,
            data_timestamp=now_utc,
            verification_status=STATUS_REPORTED_UNVERIFIED,
        )
        rep_b_wb = StockReport(
            blood_bank_id=fac_b.id,
            blood_group="B+",
            blood_component="Whole Blood",
            units_reported=8,
            source_name=DEFAULT_ERAKTKOSH_SOURCE,
            data_timestamp=now_utc,
            verification_status=STATUS_REPORTED_UNVERIFIED,
        )
        db_session.add_all([rep_a_wb, rep_a_prbc, rep_b_wb])
        db_session.commit()

        # Ingest payload where Facility A explicitly reports Whole Blood Not Available
        payload = {
            "draw": 1,
            "data": [
                [
                    "1",
                    "FACILITY A<br/>Karol Bagh, New Delhi",
                    "Govt.",
                    "<p class='text-danger'><b>Whole Blood</b>Not Available Search for another Component</p>",
                    "2026-10-16 05:00:00",
                    "Blood Bank",
                ]
            ],
        }

        res = ingest_eraktkosh_city_payload(
            db=db_session,
            city="Delhi",
            payload=payload,
            component="Whole Blood",
            apply=True,
        )

        assert res.reports_withdrawn == 1

        # Check Facility A: Whole Blood report withdrawn, but PRBC report remains intact!
        db_session.refresh(fac_a)
        reports_a = {r.blood_component: r.units_reported for r in fac_a.stock_reports}
        assert "Whole Blood" not in reports_a
        assert reports_a["Packed Red Blood Cells"] == 12

        # Check Facility B: Whole Blood report remains completely intact!
        db_session.refresh(fac_b)
        reports_b = {r.blood_component: r.units_reported for r in fac_b.stock_reports}
        assert reports_b["Whole Blood"] == 8

    def test_malformed_rows_never_cause_zero_stock_interpretation_or_stock_withdrawal(
        self, db_session: Session
    ) -> None:
        """Malformed or incomplete rows must never be interpreted as zero stock or cause withdrawal."""
        # Setup: Facility exists with stock
        fac = BloodBank(
            name="FACILITY STABLE",
            city="Delhi",
            locality="Rohini",
            source_type="external_source",
            source_name=DEFAULT_ERAKTKOSH_SOURCE,
            source_facility_id="eraktkosh:delhi:facility-stable:rohini",
            raw_address="Rohini, New Delhi",
        )
        db_session.add(fac)
        db_session.flush()

        rep = StockReport(
            blood_bank_id=fac.id,
            blood_group="O+",
            blood_component="Whole Blood",
            units_reported=15,
            source_name=DEFAULT_ERAKTKOSH_SOURCE,
            data_timestamp=datetime.now(timezone.utc),
            verification_status=STATUS_REPORTED_UNVERIFIED,
        )
        db_session.add(rep)
        db_session.commit()

        # Incoming snapshot contains a malformed row for this facility
        # (e.g. invalid availability HTML with no quantities and not explicit "Not Available")
        malformed_payload = {
            "draw": 1,
            "data": [
                [
                    "1",
                    "FACILITY STABLE<br/>Rohini, New Delhi",
                    "Govt.",
                    "<p>Corrupted Availability Data Without Format</p>",
                    "2026-10-16 06:00:00",
                    "Blood Bank",
                ]
            ],
        }

        res = ingest_eraktkosh_city_payload(
            db=db_session,
            city="Delhi",
            payload=malformed_payload,
            component="Whole Blood",
            apply=True,
        )

        assert res.failed_rows_count == 1
        assert res.reports_withdrawn == 0

        # Existing stock must remain intact in DB
        db_session.refresh(fac)
        assert len(fac.stock_reports) == 1
        assert fac.stock_reports[0].units_reported == 15

    def test_dry_run_simulation_granular_metrics(
        self, db_session: Session
    ) -> None:
        """Dry-run accurately simulates created, updated, unchanged, and withdrawn counts without DB writes."""
        # Seed 1 existing facility with 1 stock report
        fac = BloodBank(
            name="FACILITY EXISTING",
            city="Delhi",
            locality="Lajpat Nagar",
            category="Govt.",
            facility_type="Blood Bank",
            source_type="external_source",
            source_name=DEFAULT_ERAKTKOSH_SOURCE,
            source_facility_id="eraktkosh:delhi:facility-existing:lajpat-nagar",
            raw_address="Lajpat Nagar, New Delhi",
        )
        db_session.add(fac)
        db_session.flush()
        db_session.add(
            StockReport(
                blood_bank_id=fac.id,
                blood_group="A+",
                blood_component="Whole Blood",
                units_reported=10,
                source_name=DEFAULT_ERAKTKOSH_SOURCE,
                data_timestamp=datetime.now(timezone.utc),
                verification_status=STATUS_REPORTED_UNVERIFIED,
            )
        )
        db_session.commit()

        # Payload has:
        # 1. Existing facility with same metadata and same stock -> unchanged
        # 2. Brand new facility with B+: 5 -> created facility, created report
        # 3. Brand new facility with Whole Blood Not Available -> created facility, 0 reports
        payload = {
            "draw": 1,
            "data": [
                [
                    "1",
                    "FACILITY EXISTING<br/>Lajpat Nagar, New Delhi",
                    "Govt.",
                    "<p>Available, A+Ve:10</p>",
                    "2026-10-16 02:00:00",
                    "Blood Bank",
                ],
                [
                    "2",
                    "FACILITY NEW ONE<br/>Okhla, New Delhi",
                    "Private",
                    "<p>Available, B+Ve:5</p>",
                    "2026-10-16 02:00:00",
                    "Blood Bank",
                ],
                [
                    "3",
                    "FACILITY NEW ZERO<br/>Jasola, New Delhi",
                    "Charitable",
                    "<p class='text-danger'><b>Whole Blood</b>Not Available</p>",
                    "2026-10-16 02:00:00",
                    "Blood Bank",
                ],
            ],
        }

        res = ingest_eraktkosh_city_payload(
            db=db_session,
            city="Delhi",
            payload=payload,
            component="Whole Blood",
            apply=False,
        )

        assert res.is_dry_run is True
        assert res.facilities_parsed == 3
        assert res.facilities_with_available_stock == 2
        assert res.facilities_with_unavailable_stock == 1
        assert res.stock_observations_parsed == 2
        assert res.facilities_created == 2
        assert res.facilities_updated == 0
        assert res.facilities_unchanged == 1
        assert res.reports_created == 1
        assert res.reports_updated == 0
        assert res.reports_unchanged == 1
        assert res.reports_withdrawn == 0

        # Assert database was NOT modified at all
        assert db_session.scalar(select(func.count(BloodBank.id))) == 1
        assert db_session.scalar(select(func.count(StockReport.id))) == 1

    def test_facility_metadata_change_tracked_in_metrics(
        self, db_session: Session
    ) -> None:
        """Verify facilities_updated increments when facility attributes change."""
        payload_v1 = {
            "draw": 1,
            "data": [
                [
                    "1",
                    "FACILITY MOD<br/>10 Barakhamba Road, Connaught Place, New Delhi",
                    "Govt.",
                    "<p>Available, A+Ve:5</p>",
                    "2026-10-16 02:00:00",
                    "Blood Bank",
                ]
            ],
        }
        res1 = ingest_eraktkosh_city_payload(
            db=db_session,
            city="Delhi",
            payload=payload_v1,
            apply=True,
        )
        assert res1.facilities_created == 1
        assert res1.facilities_updated == 0
        assert res1.facilities_unchanged == 0

        # Now ingest with updated address line and changed units (locality unchanged)
        payload_v2 = {
            "draw": 2,
            "data": [
                [
                    "1",
                    "FACILITY MOD<br/>20 Barakhamba Road, Connaught Place, New Delhi",
                    "Govt.",
                    "<p>Available, A+Ve:12</p>",
                    "2026-10-16 04:00:00",
                    "Blood Bank",
                ]
            ],
        }
        # In dry run:
        dry_res = ingest_eraktkosh_city_payload(
            db=db_session,
            city="Delhi",
            payload=payload_v2,
            apply=False,
        )
        assert dry_res.facilities_created == 0
        assert dry_res.facilities_updated == 1
        assert dry_res.facilities_unchanged == 0
        assert dry_res.reports_created == 0
        assert dry_res.reports_updated == 1
        assert dry_res.reports_unchanged == 0

        # In apply mode:
        apply_res = ingest_eraktkosh_city_payload(
            db=db_session,
            city="Delhi",
            payload=payload_v2,
            apply=True,
        )
        assert apply_res.facilities_created == 0
        assert apply_res.facilities_updated == 1
        assert apply_res.facilities_unchanged == 0
        assert apply_res.reports_created == 0
        assert apply_res.reports_updated == 1
        assert apply_res.reports_unchanged == 0
