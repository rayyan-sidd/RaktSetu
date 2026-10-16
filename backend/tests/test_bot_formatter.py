"""Tests for clinical and provenance text formatter."""

from datetime import datetime, timezone, timedelta

from backend.app.bot.formatter import (
    format_api_error_message,
    format_discovery_results,
    format_empty_results,
    format_facility_card,
    format_help_message,
    format_start_message,
)
from backend.app.schemas.blood_bank import BloodBankRead, StockReportRead


def test_start_message_contains_mandatory_disclaimers() -> None:
    """format_start_message must contain explicit medical disclaimer and scope."""
    msg = format_start_message(web_url="https://raktsetu.example.org")
    assert "IMPORTANT MEDICAL &amp; SAFETY DISCLAIMER" in msg
    assert "Delhi &amp; Lucknow" in msg
    assert "e-RaktKosh" in msg
    assert "https://raktsetu.example.org" in msg
    assert "/find" in msg


def test_start_message_omits_web_url_when_none() -> None:
    """format_start_message should not include web URL section if web_url is None."""
    msg = format_start_message(web_url=None)
    assert "Web Console" not in msg


def test_help_message_contains_instructions_and_helplines() -> None:
    """format_help_message must detail supported values and emergency guidance without 104/1075."""
    msg = format_help_message()
    assert "104" not in msg  # Hardcoded blood helpline removed
    assert "1075" not in msg  # Health helpline removed
    assert "112" in msg  # General emergency number retained
    assert "general emergency" in msg
    assert "not a blood bank helpline" in msg
    assert "verify current stock before traveling" in msg
    assert "A+, A-, B+, B-, AB+, AB-, O+, O-" in msg
    assert "Delhi, Lucknow" in msg


def test_facility_card_positive_reported_stock_unverified() -> None:
    """Positive stock must be labeled as reported units and unverified snapshot."""
    now = datetime(2026, 10, 16, 6, 0, 0, tzinfo=timezone.utc)
    bank = BloodBankRead(
        id=10,
        name="AIIMS Main Blood Centre",
        city="Delhi",
        locality="Ansari Nagar",
        category="Government",
        source_name="e-RaktKosh (MoHFW)",
        source_type="external_source",
        stock_reports=[
            StockReportRead(
                id=1,
                blood_bank_id=10,
                blood_group="O+",
                blood_component="Whole Blood",
                units_reported=15,
                source_name="e-RaktKosh (MoHFW)",
                verification_status="reported_unverified",
                source_reported_timestamp=now - timedelta(hours=2),
                retrieval_timestamp=now,
                data_timestamp=now,
            )
        ],
    )
    card = format_facility_card(bank, blood_group="O+", now=now)
    assert "AIIMS Main Blood Centre" in card
    assert "Ansari Nagar, Delhi" in card
    assert "Reported:</b> 15 units (O+ • Whole Blood)" in card
    assert "Unverified snapshot • Availability not guaranteed" in card
    assert "Hospital Reported:</b> 2026-10-16 04:00 UTC" in card
    # Fresh report must not have stale warning
    assert "Stale Report" not in card


def test_facility_card_flags_stale_source_report() -> None:
    """Reports with source timestamps older than 24 hours must display Stale warning."""
    now = datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone.utc)
    stale_time = now - timedelta(hours=36)
    bank = BloodBankRead(
        id=11,
        name="Safdarjung Hospital",
        city="Delhi",
        locality="Ring Road",
        category="Government",
        source_name="e-RaktKosh (MoHFW)",
        source_type="external_source",
        stock_reports=[
            StockReportRead(
                id=2,
                blood_bank_id=11,
                blood_group="A+",
                blood_component="Whole Blood",
                units_reported=5,
                source_name="e-RaktKosh (MoHFW)",
                verification_status="reported_unverified",
                source_reported_timestamp=stale_time,
                retrieval_timestamp=now,
                data_timestamp=now,
            )
        ],
    )
    card = format_facility_card(bank, blood_group="A+", now=now)
    assert "Stale Report (&gt;24h old)" in card
    assert "Inventory may not reflect current physical stock" in card


def test_facility_card_handles_live_stock_badge() -> None:
    """Live badge indicator must be clearly disclaimed without false guarantees."""
    now = datetime(2026, 10, 16, 6, 0, 0, tzinfo=timezone.utc)
    bank = BloodBankRead(
        id=12,
        name="KGMU Lucknow",
        city="Lucknow",
        locality="Chowk",
        source_name="e-RaktKosh (MoHFW)",
        source_type="external_source",
        stock_reports=[
            StockReportRead(
                id=3,
                blood_bank_id=12,
                blood_group="B+",
                blood_component="Whole Blood",
                units_reported=10,
                source_name="e-RaktKosh (MoHFW)",
                verification_status="reported_unverified",
                freshness_indicator="live_stock_badge",
                source_reported_timestamp=None,
                retrieval_timestamp=now,
                data_timestamp=now,
            )
        ],
    )
    card = format_facility_card(bank, blood_group="B+", now=now)
    assert "Portal Indicator:</b> Live Stock Badge" in card
    assert "not a physical stock guarantee" in card


def test_facility_card_handles_unstocked_feed() -> None:
    """Facilities with no positive stock must not be claimed as out of stock."""
    bank = BloodBankRead(
        id=14,
        name="Community Transfusion Center",
        city="Delhi",
        locality="Narela",
        source_name="e-RaktKosh (MoHFW)",
        source_type="external_source",
        stock_reports=[],
    )
    card = format_facility_card(bank, blood_group="O+")
    assert "No stock reported in feed" in card
    assert "Not confirmed out of stock" in card
    assert "Source feed did not report positive units" in card


def test_discovery_results_summary_and_counts() -> None:
    """format_discovery_results must format header counts, cards, and emergency advice."""
    now = datetime(2026, 10, 16, 6, 0, 0, tzinfo=timezone.utc)
    bank = BloodBankRead(
        id=10,
        name="AIIMS Blood Centre",
        city="Delhi",
        locality="Ansari Nagar",
        source_name="e-RaktKosh (MoHFW)",
        source_type="external_source",
        stock_reports=[],
    )
    results = format_discovery_results(
        facilities=[bank],
        total_count=42,
        blood_group="O+",
        city="Delhi",
        web_url="https://raktsetu.example.org",
        now=now,
    )
    assert "Found 42 (showing top 1)" in results
    assert "Showing top 1 facilities prioritizing reported stock" in results
    assert "Explore all 42 facilities:</b> https://raktsetu.example.org" in results
    assert "Always verify directly with the blood bank" in results


def test_empty_results_recommends_helplines() -> None:
    """format_empty_results must clarify feed absence, exclude 104, and identify 112 as general emergency."""
    empty_msg = format_empty_results(blood_group="AB-", city="Lucknow")
    assert "No Reported Facilities Found" in empty_msg
    assert "AB-" in empty_msg
    assert "Lucknow" in empty_msg
    assert "104" not in empty_msg
    assert "1075" not in empty_msg
    assert "112" in empty_msg
    assert "general emergency" in empty_msg
    assert "not a blood bank helpline" in empty_msg
    assert "confirm availability" in empty_msg
    assert "<b>NOT</b> guarantee that blood is physically absent across all hospitals" in empty_msg


def test_api_error_message() -> None:
    """format_api_error_message must provide graceful error guidance with 112 as general emergency."""
    msg = format_api_error_message()
    assert "Discovery Service Temporarily Unavailable" in msg
    assert "104" not in msg
    assert "1075" not in msg
    assert "112" in msg
    assert "general emergency" in msg
    assert "not a blood bank helpline" in msg
    assert "check physical blood availability" in msg
