from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from backend.app.services.eraktkosh import (
    DEFAULT_ERAKTKOSH_SOURCE,
    FRESHNESS_LIVE_BADGE,
    FRESHNESS_SOURCE_TIMESTAMP,
    STATUS_REPORTED_UNVERIFIED,
    clean_html_tags,
    parse_availability_html,
    parse_eraktkosh_response,
    parse_eraktkosh_row,
    parse_facility_html,
    parse_timestamp_field,
)

FIXTURES_PATH = Path(__file__).resolve().parent / "fixtures" / "synthetic_eraktkosh_response.json"


@pytest.fixture
def response_fixtures() -> dict:
    """Load redacted synthetic response fixtures for parser testing."""
    with open(FIXTURES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class TestFacilityHtmlParsing:
    """Verify HTML cleaning, locality extraction, and strict contact redaction."""

    def test_parses_facility_name_and_locality(self) -> None:
        html_input = (
            "ALL INDIA INSTITUTE OF MEDICAL SCIENCES<br/>"
            "Sri Aurobindo Marg, Ansari Nagar East, New Delhi, Delhi 110029<br/>"
            "Phone: 011-26594438, Fax: 011-26588663, Email: aiims@example.com"
        )
        info, err = parse_facility_html(html_input, default_city="Delhi")

        assert err is None
        assert info is not None
        assert info.facility_name == "ALL INDIA INSTITUTE OF MEDICAL SCIENCES"
        assert info.city == "Delhi"
        assert "Ansari Nagar" in info.locality
        # Ensure contact details are NEVER retained in parsed fields
        assert "011-26594438" not in info.raw_address
        assert "aiims@example.com" not in info.raw_address
        assert "011-26594438" not in info.facility_name
        assert "011-26594438" not in info.locality

    def test_strict_contact_redaction_across_formats(self) -> None:
        html_input = (
            "LADY HARDINGE MEDICAL COLLEGE<br/>"
            "Connaught Place, New Delhi<br/>"
            "Mobile: 9876543210<br/>"
            "Contact: 011-23363362<br/>"
            "Email: bloodbank@lhmc.edu"
        )
        info, err = parse_facility_html(html_input, default_city="Delhi")

        assert err is None
        assert info is not None
        assert info.facility_name == "LADY HARDINGE MEDICAL COLLEGE"
        assert info.locality == "Connaught Place"

        # Verify no sensitive contact information is retained
        combined_text = f"{info.facility_name} {info.raw_address} {info.locality}"
        assert "9876543210" not in combined_text
        assert "011-23363362" not in combined_text
        assert "bloodbank@lhmc.edu" not in combined_text
        assert "Mobile" not in combined_text
        assert "Email" not in combined_text

    def test_lucknow_facility_parsing(self) -> None:
        html_input = (
            "KGMU TRANSFUSION MEDICINE<br/>"
            "Chowk, Lucknow, Uttar Pradesh 226003<br/>"
            "Tel: 0522-2257450"
        )
        info, err = parse_facility_html(html_input, default_city="Lucknow")

        assert err is None
        assert info is not None
        assert info.facility_name == "KGMU TRANSFUSION MEDICINE"
        assert info.city == "Lucknow"
        assert info.locality == "Chowk"
        assert "0522-2257450" not in info.raw_address

    def test_missing_or_empty_html_rejected(self) -> None:
        info, err = parse_facility_html(None, default_city="Delhi")
        assert info is None
        assert err is not None

        info, err = parse_facility_html("   ", default_city="Delhi")
        assert info is None
        assert err is not None

    def test_html_with_only_contact_info_rejected(self) -> None:
        html_only_contact = "Phone: 011-12345678<br/>Email: test@example.com"
        info, err = parse_facility_html(html_only_contact, default_city="Delhi")
        assert info is None
        assert err is not None
        assert "no parseable facility name" in err


class TestAvailabilityParsing:
    """Verify parsing of stock availability strings and unavailable-stock handling."""

    def test_parses_multi_group_quantities(self) -> None:
        raw_html = "<p class='text-success'>Available, B+Ve:5, O+Ve:8</p>"
        is_avail, comp, items, errs = parse_availability_html(raw_html)

        assert is_avail is True
        assert len(errs) == 0
        assert len(items) == 2

        # Sorted or indexed check
        item_b = next(it for it in items if it.blood_group == "B+")
        item_o = next(it for it in items if it.blood_group == "O+")

        assert item_b.blood_group == "B+"
        assert item_b.raw_group == "B+Ve"
        assert item_b.units == 5

        assert item_o.blood_group == "O+"
        assert item_o.raw_group == "O+Ve"
        assert item_o.units == 8

    def test_parses_single_group_with_irregular_spacing(self) -> None:
        raw_html = "<p class='text-success'>Available,  A+Ve :  14 </p>"
        is_avail, comp, items, errs = parse_availability_html(raw_html)

        assert is_avail is True
        assert len(errs) == 0
        assert len(items) == 1
        assert items[0].blood_group == "A+"
        assert items[0].units == 14

    def test_unavailable_stock_does_not_invent_zero_quantities(self) -> None:
        # Crucial safety rule: do not convert unavailable message into 0-stock claims for unreported groups
        raw_html = "<p class='text-danger'><b>Whole Blood</b>Not Available Search for another Component"
        is_avail, comp, items, errs = parse_availability_html(raw_html)

        assert is_avail is False
        assert comp == "Whole Blood"
        assert len(items) == 0  # Must be empty!
        assert len(errs) == 0

    def test_unavailable_generic_message(self) -> None:
        raw_html = "<p class='text-danger'>Stock Not Available</p>"
        is_avail, comp, items, errs = parse_availability_html(raw_html)

        assert is_avail is False
        assert len(items) == 0
        assert len(errs) == 0

    def test_malformed_group_ignored_without_dropping_valid_groups(self) -> None:
        raw_html = "<p class='text-success'>Available, Bombay+Ve:5, O+Ve:7</p>"
        is_avail, comp, items, errs = parse_availability_html(raw_html)

        assert is_avail is True
        assert len(items) == 1
        assert items[0].blood_group == "O+"
        assert items[0].units == 7
        assert any("Bombay+Ve" in err for err in errs)

    def test_unparseable_or_negative_units_skipped(self) -> None:
        raw_html = "<p class='text-success'>Available, A+Ve:-3, B+Ve:abc, O+Ve:4</p>"
        is_avail, comp, items, errs = parse_availability_html(raw_html)

        assert is_avail is True
        assert len(items) == 1
        assert items[0].blood_group == "O+"
        assert items[0].units == 4

    def test_available_text_without_quantities_reports_error(self) -> None:
        raw_html = "<p class='text-success'>Available on request only</p>"
        is_avail, comp, items, errs = parse_availability_html(raw_html)

        assert is_avail is True
        assert len(items) == 0
        assert len(errs) > 0
        assert "no valid blood group quantities" in errs[0]

    def test_empty_or_null_availability_rejected(self) -> None:
        is_avail, comp, items, errs = parse_availability_html(None)
        assert is_avail is False
        assert len(errs) > 0

        is_avail, comp, items, errs = parse_availability_html("")
        assert is_avail is False
        assert len(errs) > 0


class TestTimestampAndFreshness:
    """Verify timezone-aware UTC conversion, live stock badge handling, and distinction from retrieval time."""

    def test_parses_ist_portal_timestamp_to_utc(self) -> None:
        # 04:31:04 IST on 2026-10-16 is 23:01:04 UTC on 2026-10-15
        field_val = "2026-10-16 04:31:04"
        utc_dt, has_live, freshness, raw_text, err = parse_timestamp_field(field_val)

        assert err is None
        assert utc_dt is not None
        assert utc_dt.tzinfo == timezone.utc
        assert utc_dt.year == 2026
        assert utc_dt.month == 10
        assert utc_dt.day == 15
        assert utc_dt.hour == 23
        assert utc_dt.minute == 1
        assert utc_dt.second == 4
        assert has_live is False
        assert freshness == FRESHNESS_SOURCE_TIMESTAMP
        assert raw_text == "2026-10-16 04:31:04"

    def test_live_badge_does_not_invent_timestamp(self) -> None:
        # Crucial invariant: live stock badge indicates freshness without an exact datetime
        badge_html = "<img src='../hisglobal/bbpublic/images/transparent/live_stock.png'>"
        utc_dt, has_live, freshness, raw_text, err = parse_timestamp_field(badge_html)

        assert err is None
        assert utc_dt is None  # MUST NOT invent a timestamp!
        assert has_live is True
        assert freshness == FRESHNESS_LIVE_BADGE
        assert raw_text == "live_stock_badge"

    def test_null_or_empty_timestamp_returns_none(self) -> None:
        utc_dt, has_live, freshness, raw_text, err = parse_timestamp_field(None)
        assert err is None
        assert utc_dt is None
        assert has_live is False
        assert freshness is None

        utc_dt, has_live, freshness, raw_text, err = parse_timestamp_field("")
        assert err is None
        assert utc_dt is None

    def test_malformed_timestamp_reports_error_without_raising(self) -> None:
        field_val = "Updated 2 hours ago"
        utc_dt, has_live, freshness, raw_text, err = parse_timestamp_field(field_val)

        assert utc_dt is None
        assert has_live is False
        assert err is not None
        assert "Malformed" in err


class TestRowParsing:
    """Verify single row parsing across fields and edge cases."""

    def test_valid_row_parsing(self, response_fixtures: dict) -> None:
        delhi_data = response_fixtures["synthetic_delhi_response"]["data"]
        row_0 = delhi_data[0]

        result = parse_eraktkosh_row(
            row=row_0,
            default_city="Delhi",
            default_component="Whole Blood",
        )

        assert result.is_valid is True
        assert result.serial_number == "1"
        assert result.facility_info is not None
        assert result.facility_info.facility_name == "SYNTHETIC AIIMS BLOOD BANK"
        assert result.facility_info.city == "Delhi"
        assert result.category == "Govt."
        assert result.facility_type == "Blood Bank"
        assert result.is_available is True
        assert len(result.availability_items) == 2
        assert result.source_reported_timestamp is not None
        assert result.has_live_badge is False

    def test_row_with_live_badge(self, response_fixtures: dict) -> None:
        delhi_data = response_fixtures["synthetic_delhi_response"]["data"]
        row_1 = delhi_data[1]

        result = parse_eraktkosh_row(
            row=row_1,
            default_city="Delhi",
        )

        assert result.is_valid is True
        assert result.is_available is False  # "Whole Blood Not Available"
        assert result.blood_component == "Whole Blood"
        assert result.has_live_badge is True
        assert result.source_reported_timestamp is None
        assert result.freshness_indicator == FRESHNESS_LIVE_BADGE

    def test_row_with_null_category_and_type(self, response_fixtures: dict) -> None:
        lucknow_data = response_fixtures["synthetic_lucknow_response"]["data"]
        row_2 = lucknow_data[2]

        result = parse_eraktkosh_row(
            row=row_2,
            default_city="Lucknow",
        )

        assert result.is_valid is True
        assert result.category is None  # "null" was converted to None
        assert result.facility_type is None
        assert result.is_available is False
        assert result.blood_component == "Packed Red Blood Cells"

    def test_non_list_row_handled_safely(self) -> None:
        result = parse_eraktkosh_row("not a list row", default_city="Delhi")
        assert result.is_valid is False
        assert "Expected row to be list" in result.errors[0]


class TestResponseParsingAndBatchNormalization:
    """Verify full payload parsing, batch normalization, and deduplication."""

    def test_delhi_response_parsing(self, response_fixtures: dict) -> None:
        retrieval_ts = datetime(2026, 10, 16, 5, 0, 0, tzinfo=timezone.utc)
        payload = response_fixtures["synthetic_delhi_response"]

        parsed = parse_eraktkosh_response(
            payload=payload,
            default_city="Delhi",
            default_component="Whole Blood",
            retrieval_timestamp=retrieval_ts,
        )

        assert parsed.total_records_reported == 5
        assert parsed.rows_parsed == 5
        assert len(parsed.failed_rows) == 0
        assert len(parsed.successful_rows) == 5

        # Row 1 (AIIMS): B+:5, O+:8 -> 2 records
        # Row 2 (Safdarjung): Whole Blood Not Available -> 0 records (safe!)
        # Row 3 (Red Cross): A+:12, AB-:2 -> 2 records
        # Row 4 (Apollo): O-:4 -> 1 record
        # Row 5 (Max): B-:1 -> 1 record
        # Total normalized records = 2 + 0 + 2 + 1 + 1 = 6 records
        assert len(parsed.normalized_records) == 6

        # Invariant checks on generated records
        for rec in parsed.normalized_records:
            assert rec.city == "Delhi"
            assert rec.retrieval_timestamp == retrieval_ts
            assert rec.verification_status == STATUS_REPORTED_UNVERIFIED
            assert rec.source_name == DEFAULT_ERAKTKOSH_SOURCE
            assert rec.units_reported >= 0

    def test_lucknow_response_parsing(self, response_fixtures: dict) -> None:
        payload = response_fixtures["synthetic_lucknow_response"]

        parsed = parse_eraktkosh_response(
            payload=payload,
            default_city="Lucknow",
            default_component="Whole Blood",
        )

        assert parsed.rows_parsed == 3
        assert len(parsed.successful_rows) == 3

        # Row 1 (KGMU): A+:10, B+:14, O+:6 -> 3 records
        # Row 2 (SGPGI): AB+:3 -> 1 record (with None timestamp because it had live badge)
        # Row 3 (Trust): Not Available -> 0 records
        assert len(parsed.normalized_records) == 4

        # Verify SGPGI record has None source timestamp (from live badge)
        sgpgi_rec = next(r for r in parsed.normalized_records if "SGPGI" in r.facility_name)
        assert sgpgi_rec.source_reported_timestamp is None
        assert sgpgi_rec.blood_group == "AB+"
        assert sgpgi_rec.units_reported == 3

    def test_deduplication_prefers_newer_source_timestamp(self, response_fixtures: dict) -> None:
        edge_cases = response_fixtures["edge_case_rows"]
        row_earlier = edge_cases["duplicate_facility_earlier"]
        row_later = edge_cases["duplicate_facility_later_newer_ts"]

        payload = {"data": [row_earlier, row_later]}

        parsed = parse_eraktkosh_response(payload, default_city="Lucknow")
        assert parsed.rows_parsed == 2
        assert parsed.duplicate_count == 1
        assert len(parsed.normalized_records) == 1

        survivor = parsed.normalized_records[0]
        # Newer timestamp was 2026-10-16 08:00:00 IST with 9 units
        assert survivor.units_reported == 9
        assert survivor.source_reported_timestamp is not None
        # 08:00 IST -> 02:30 UTC
        assert survivor.source_reported_timestamp.hour == 2
        assert survivor.source_reported_timestamp.minute == 30

    def test_malformed_rows_in_payload_do_not_halt_batch(self, response_fixtures: dict) -> None:
        edge_cases = response_fixtures["edge_case_rows"]
        bad_row = edge_cases["missing_facility_name"]
        good_row = response_fixtures["synthetic_delhi_response"]["data"][0]

        payload = {"data": [bad_row, good_row]}

        parsed = parse_eraktkosh_response(payload, default_city="Delhi")
        assert parsed.rows_parsed == 2
        assert len(parsed.failed_rows) == 1
        assert len(parsed.successful_rows) == 1
        assert len(parsed.normalized_records) == 2
