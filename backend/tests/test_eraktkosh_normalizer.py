from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from backend.app.services.eraktkosh import (
    DEFAULT_ERAKTKOSH_SOURCE,
    STATUS_REPORTED_UNVERIFIED,
    normalize_blood_group,
    normalize_city_and_locality,
    normalize_eraktkosh_batch,
    normalize_eraktkosh_record,
    parse_source_timestamp,
    parse_units,
)

FIXTURES_PATH = Path(__file__).resolve().parent / "fixtures" / "synthetic_eraktkosh_samples.json"


@pytest.fixture
def synthetic_fixtures() -> dict:
    """Load synthetic test fixtures for e-RaktKosh normalization tests."""
    with open(FIXTURES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class TestBloodGroupNormalization:
    """Verify blood group parsing and normalization across variants."""

    @pytest.mark.parametrize(
        "raw_input, expected_group",
        [
            ("A+", "A+"),
            ("A-", "A-"),
            ("B+", "B+"),
            ("B-", "B-"),
            ("AB+", "AB+"),
            ("AB-", "AB-"),
            ("O+", "O+"),
            ("O-", "O-"),
            # e-Raktkosh 'Ve' variants
            ("A+Ve", "A+"),
            ("A-ve", "A-"),
            ("B+VE", "B+"),
            ("b-ve", "B-"),
            ("AB+Ve", "AB+"),
            ("ab-ve", "AB-"),
            ("O+VE", "O+"),
            ("O-ve", "O-"),
            # Textual descriptors
            ("A Positive", "A+"),
            ("A Negative", "A-"),
            ("B POSITIVE", "B+"),
            ("B NEGATIVE", "B-"),
            ("AB POSITIVE", "AB+"),
            ("AB NEGATIVE", "AB-"),
            ("O POSITIVE", "O+"),
            ("O NEGATIVE", "O-"),
            ("A Pos", "A+"),
            ("O Neg", "O-"),
            # Spacing & URL decoding variants
            ("A +", "A+"),
            ("O -", "O-"),
            ("A + Ve", "A+"),
            ("A ", "A+"),  # Trailing space from URL decoding '+'
        ],
    )
    def test_valid_blood_groups(self, raw_input: str, expected_group: str) -> None:
        group, err = normalize_blood_group(raw_input)
        assert err is None
        assert group == expected_group

    @pytest.mark.parametrize(
        "invalid_input",
        [
            "Oh+Ve",    # Bombay blood group (unsupported in standard ABO/Rh)
            "Oh-Ve",
            "RhNull",
            "XYZ",
            "C+",
            "",
            "   ",
            None,
        ],
    )
    def test_unsupported_blood_groups(self, invalid_input: str) -> None:
        group, err = normalize_blood_group(invalid_input)
        assert group is None
        assert err is not None
        assert "Unsupported" in err or "required" in err


class TestCityLocalityNormalization:
    """Verify city mapping to Delhi and Lucknow and locality preservation."""

    @pytest.mark.parametrize(
        "city_raw, district_raw, expected_city",
        [
            ("Delhi", None, "Delhi"),
            ("DELHI", None, "Delhi"),
            ("New Delhi", None, "Delhi"),
            ("Central Delhi", None, "Delhi"),
            ("South Delhi", None, "Delhi"),
            ("East Delhi", None, "Delhi"),
            ("Shahdara", None, "Delhi"),
            ("Delhi", "North West Delhi", "Delhi"),
            ("Lucknow", None, "Lucknow"),
            ("LUCKNOW", "Lucknow District", "Lucknow"),
        ],
    )
    def test_supported_cities(self, city_raw: str, district_raw: str, expected_city: str) -> None:
        city, locality, err = normalize_city_and_locality(city_raw, raw_district=district_raw)
        assert err is None
        assert city == expected_city
        assert len(locality) > 0

    def test_preserves_explicit_locality(self) -> None:
        city, locality, err = normalize_city_and_locality(
            "Delhi", raw_locality="Connaught Place", raw_district="Central Delhi"
        )
        assert err is None
        assert city == "Delhi"
        assert locality == "Connaught Place"

    @pytest.mark.parametrize(
        "unsupported_city",
        [
            "Mumbai",
            "Bangalore",
            "Kanpur",
            "Chennai",
            "",
            None,
        ],
    )
    def test_unsupported_cities(self, unsupported_city: str) -> None:
        city, locality, err = normalize_city_and_locality(unsupported_city)
        assert city is None
        assert locality is None
        assert err is not None


class TestUnitsParsing:
    """Verify units_reported parsing and non-negative constraints."""

    @pytest.mark.parametrize(
        "raw_units, expected_units",
        [
            (15, 15),
            (0, 0),
            ("12", 12),
            ("0", 0),
            ("18 Units", 18),
            ("Available: 25", 25),
            ("Available, 8 Units", 8),
        ],
    )
    def test_valid_units(self, raw_units, expected_units: int) -> None:
        units, err = parse_units(raw_units)
        assert err is None
        assert units == expected_units

    @pytest.mark.parametrize(
        "invalid_units",
        [
            -5,
            "-5",
            "In Stock",
            "Available",
            "N/A",
            "",
            None,
        ],
    )
    def test_invalid_units(self, invalid_units) -> None:
        units, err = parse_units(invalid_units)
        assert units is None
        assert err is not None


class TestTimestampConversion:
    """Verify source timestamp parsing and conversion from IST to UTC."""

    def test_parses_ist_string_to_utc(self) -> None:
        # 14:30 IST is 09:00 UTC
        ts_str = "15-Oct-2026 14:30:00"
        utc_dt, err = parse_source_timestamp(ts_str)
        assert err is None
        assert utc_dt is not None
        assert utc_dt.tzinfo == timezone.utc
        assert utc_dt.year == 2026
        assert utc_dt.month == 10
        assert utc_dt.day == 15
        assert utc_dt.hour == 9
        assert utc_dt.minute == 0

    def test_parses_timezone_aware_iso_string(self) -> None:
        # 16:00+05:30 is 10:30 UTC
        iso_str = "2026-10-15T16:00:00+05:30"
        utc_dt, err = parse_source_timestamp(iso_str)
        assert err is None
        assert utc_dt is not None
        assert utc_dt.tzinfo == timezone.utc
        assert utc_dt.hour == 10
        assert utc_dt.minute == 30

    def test_parses_utc_iso_string(self) -> None:
        utc_str = "2026-10-15T12:00:00Z"
        utc_dt, err = parse_source_timestamp(utc_str)
        assert err is None
        assert utc_dt is not None
        assert utc_dt.tzinfo == timezone.utc
        assert utc_dt.hour == 12

    def test_absent_timestamp_returns_none_without_inventing(self) -> None:
        utc_dt, err = parse_source_timestamp(None)
        assert err is None
        assert utc_dt is None

        utc_dt, err = parse_source_timestamp("")
        assert err is None
        assert utc_dt is None

    def test_malformed_timestamp_reports_error(self) -> None:
        utc_dt, err = parse_source_timestamp("yesterday afternoon")
        assert utc_dt is None
        assert err is not None
        assert "Malformed" in err


class TestRecordNormalizationWithSyntheticFixtures:
    """Verify single and batch normalization using synthetic test fixtures."""

    def test_valid_synthetic_fixtures(self, synthetic_fixtures: dict) -> None:
        retrieval_time = datetime(2026, 10, 16, 4, 0, 0, tzinfo=timezone.utc)
        for fixture in synthetic_fixtures["valid_records"]:
            result = normalize_eraktkosh_record(fixture, retrieval_timestamp=retrieval_time)
            assert result.is_valid, f"Failed for {fixture.get('test_case_id')}: {result.errors}"
            assert result.record is not None

            rec = result.record
            assert rec.facility_name == fixture["facility_name"]
            assert rec.city in ("Delhi", "Lucknow")
            assert rec.blood_group in ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")
            assert rec.units_reported >= 0
            assert rec.retrieval_timestamp == retrieval_time
            assert rec.source_name == DEFAULT_ERAKTKOSH_SOURCE
            # Must strictly be 'reported_unverified', never 'demo' or 'confirmed'
            assert rec.verification_status == STATUS_REPORTED_UNVERIFIED
            assert rec.verification_status != "demo"
            assert rec.verification_status != "confirmed"

    def test_malformed_synthetic_fixtures_rejected(self, synthetic_fixtures: dict) -> None:
        for fixture in synthetic_fixtures["malformed_records"]:
            result = normalize_eraktkosh_record(fixture)
            assert not result.is_valid, f"Expected rejection for {fixture.get('test_case_id')}"
            assert result.record is None
            assert len(result.errors) > 0

    def test_batch_normalization_and_deduplication(self, synthetic_fixtures: dict) -> None:
        retrieval_time = datetime(2026, 10, 16, 4, 30, 0, tzinfo=timezone.utc)
        dup_fixtures = synthetic_fixtures["duplicate_records"]

        batch_result = normalize_eraktkosh_batch(dup_fixtures, retrieval_timestamp=retrieval_time)
        assert len(batch_result.valid_records) == 1
        assert batch_result.duplicate_count == 1
        assert len(batch_result.invalid_records) == 0

        # Newer timestamp (16:00 IST) should win over older (10:00 IST)
        survivor = batch_result.valid_records[0]
        assert survivor.units_reported == 15
        assert survivor.source_reported_timestamp is not None
        # 16:00 IST -> 10:30 UTC
        assert survivor.source_reported_timestamp.hour == 10
        assert survivor.source_reported_timestamp.minute == 30

    def test_mixed_batch_processes_cleanly(self, synthetic_fixtures: dict) -> None:
        all_records = (
            synthetic_fixtures["valid_records"]
            + synthetic_fixtures["malformed_records"]
            + synthetic_fixtures["duplicate_records"]
        )

        batch_result = normalize_eraktkosh_batch(all_records)
        # Valid records: 4 unique valid + 1 deduped from 2 duplicate records = 5 valid
        assert len(batch_result.valid_records) == 5
        # Malformed records: 6 invalid
        assert len(batch_result.invalid_records) == len(synthetic_fixtures["malformed_records"])
        assert batch_result.duplicate_count == 1


class TestProvenanceAndSafetyInvariants:
    """Verify safety boundaries and provenance guarantees."""

    def test_source_reported_time_distinct_from_retrieval_time(self) -> None:
        source_ts_str = "15-Oct-2026 14:30:00"
        retrieval_ts = datetime(2026, 10, 16, 2, 0, 0, tzinfo=timezone.utc)

        raw = {
            "facility_name": "Synthetic Test Facility",
            "city": "Delhi",
            "locality": "Saket",
            "blood_group": "O+",
            "units_reported": 10,
            "source_reported_timestamp": source_ts_str,
        }

        result = normalize_eraktkosh_record(raw, retrieval_timestamp=retrieval_ts)
        assert result.is_valid and result.record is not None

        # Source timestamp was 15-Oct-2026 (09:00 UTC)
        assert result.record.source_reported_timestamp == datetime(2026, 10, 15, 9, 0, tzinfo=timezone.utc)
        # Retrieval timestamp is 16-Oct-2026 (02:00 UTC)
        assert result.record.retrieval_timestamp == retrieval_ts
        assert result.record.source_reported_timestamp != result.record.retrieval_timestamp

    def test_missing_fields_never_invented(self) -> None:
        raw_without_component_or_ts = {
            "facility_name": "Synthetic Bare Facility",
            "city": "Lucknow",
            "blood_group": "B+",
            "units_reported": 4,
        }

        result = normalize_eraktkosh_record(raw_without_component_or_ts)
        assert result.is_valid and result.record is not None
        assert result.record.blood_component is None
        assert result.record.source_reported_timestamp is None
