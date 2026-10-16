"""Tests for DiscoveryApiClient and response filtering."""

from datetime import datetime, timezone
import httpx
import pytest

from backend.app.bot.client import DiscoveryApiClient, DiscoveryApiError
from backend.app.schemas.blood_bank import BloodBankListResponse, BloodBankRead, StockReportRead


@pytest.fixture
def mock_discovery_response() -> BloodBankListResponse:
    """Fixture providing mixed synthetic and real-structured facilities."""
    now = datetime(2026, 10, 16, 6, 0, 0, tzinfo=timezone.utc)
    return BloodBankListResponse(
        items=[
            BloodBankRead(
                id=1,
                name="Demo Central Transfusion Facility",
                city="Delhi",
                locality="Central Delhi",
                source_type="demo",
                source_name="Synthetic demo dataset",
                stock_reports=[
                    StockReportRead(
                        id=101,
                        blood_bank_id=1,
                        blood_group="O+",
                        blood_component="Unspecified",
                        units_reported=20,
                        source_name="Synthetic demo dataset",
                        verification_status="demo",
                        data_timestamp=now,
                    )
                ],
            ),
            BloodBankRead(
                id=10,
                name="AIIMS Blood Centre",
                city="Delhi",
                locality="Ansari Nagar",
                source_type="external_source",
                source_name="e-RaktKosh (MoHFW)",
                stock_reports=[
                    StockReportRead(
                        id=201,
                        blood_bank_id=10,
                        blood_group="O+",
                        blood_component="Whole Blood",
                        units_reported=18,
                        source_name="e-RaktKosh (MoHFW)",
                        verification_status="reported_unverified",
                        source_reported_timestamp=now,
                        retrieval_timestamp=now,
                        data_timestamp=now,
                    )
                ],
            ),
            BloodBankRead(
                id=11,
                name="Safdarjung Hospital Blood Bank",
                city="Delhi",
                locality="Ring Road",
                source_type="external_source",
                source_name="e-RaktKosh (MoHFW)",
                stock_reports=[
                    StockReportRead(
                        id=202,
                        blood_bank_id=11,
                        blood_group="O+",
                        blood_component="Whole Blood",
                        units_reported=45,
                        source_name="e-RaktKosh (MoHFW)",
                        verification_status="reported_unverified",
                        source_reported_timestamp=now,
                        retrieval_timestamp=now,
                        data_timestamp=now,
                    )
                ],
            ),
            BloodBankRead(
                id=12,
                name="Unstocked Community Facility",
                city="Delhi",
                locality="Karol Bagh",
                source_type="external_source",
                source_name="e-RaktKosh (MoHFW)",
                stock_reports=[],
            ),
            BloodBankRead(
                id=13,
                name="Zero Units Clinical Center",
                city="Delhi",
                locality="Rohini",
                source_type="external_source",
                source_name="e-RaktKosh (MoHFW)",
                stock_reports=[
                    StockReportRead(
                        id=203,
                        blood_bank_id=13,
                        blood_group="O+",
                        blood_component="Whole Blood",
                        units_reported=0,
                        source_name="e-RaktKosh (MoHFW)",
                        verification_status="reported_unverified",
                        source_reported_timestamp=now,
                        retrieval_timestamp=now,
                        data_timestamp=now,
                    )
                ],
            ),
            BloodBankRead(
                id=14,
                name="KGMU Blood Bank",
                city="Lucknow",
                locality="Chowk",
                source_type="external_source",
                source_name="e-RaktKosh (MoHFW)",
                stock_reports=[
                    StockReportRead(
                        id=204,
                        blood_bank_id=14,
                        blood_group="O+",
                        blood_component="Whole Blood",
                        units_reported=5,
                        source_name="e-RaktKosh (MoHFW)",
                        verification_status="reported_unverified",
                        source_reported_timestamp=now,
                        retrieval_timestamp=now,
                        data_timestamp=now,
                    )
                ],
            ),
            BloodBankRead(
                id=15,
                name="RML Hospital Blood Bank",
                city="Delhi",
                locality="Connaught Place",
                source_type="external_source",
                source_name="e-RaktKosh (MoHFW)",
                stock_reports=[
                    StockReportRead(
                        id=205,
                        blood_bank_id=15,
                        blood_group="O+",
                        blood_component="Whole Blood",
                        units_reported=12,
                        source_name="e-RaktKosh (MoHFW)",
                        verification_status="reported_unverified",
                        source_reported_timestamp=now,
                        retrieval_timestamp=now,
                        data_timestamp=now,
                    )
                ],
            ),
        ],
        count=7,
        data_notice="Sample notice",
        data_timestamp=now,
    )


def test_filter_and_rank_facilities_excludes_demo_records(
    mock_discovery_response: BloodBankListResponse,
) -> None:
    """filter_and_rank_facilities must completely exclude facilities with source_type == 'demo'."""
    displayed, total_count = DiscoveryApiClient.filter_and_rank_facilities(
        mock_discovery_response,
        blood_group="O+",
        max_facilities=10,
    )
    # Total external facilities is 6 (out of 7 total items, 1 demo excluded)
    assert total_count == 6
    assert all(b.source_type != "demo" for b in displayed)
    assert all(b.id != 1 for b in displayed)


def test_filter_and_rank_facilities_ranks_positive_units_first(
    mock_discovery_response: BloodBankListResponse,
) -> None:
    """Facilities reporting positive units must be ranked ahead of unstocked or zero facilities."""
    displayed, total_count = DiscoveryApiClient.filter_and_rank_facilities(
        mock_discovery_response,
        blood_group="O+",
        max_facilities=10,
    )
    # Positive reported facilities are: Safdarjung (45), AIIMS (18), RML (12), KGMU (5)
    # Followed by unstocked: Zero Units (id 13) and Unstocked (id 12)
    ids = [b.id for b in displayed]
    assert ids[:4] == [11, 10, 15, 14]
    # Trailing facilities are unstocked
    assert set(ids[4:]) == {12, 13}


def test_filter_and_rank_facilities_enforces_limit_while_reporting_total_count(
    mock_discovery_response: BloodBankListResponse,
) -> None:
    """Returned facilities list must be capped at max_facilities, but total count accurately reported."""
    displayed, total_count = DiscoveryApiClient.filter_and_rank_facilities(
        mock_discovery_response,
        blood_group="O+",
        max_facilities=3,
    )
    assert len(displayed) == 3
    assert total_count == 6
    assert [b.id for b in displayed] == [11, 10, 15]


def test_filter_and_rank_facilities_fails_closed_on_missing_and_unknown_sources() -> None:
    """filter_and_rank_facilities must fail closed: include ONLY 'external_source' records."""
    now = datetime(2026, 10, 16, 6, 0, 0, tzinfo=timezone.utc)
    response = BloodBankListResponse(
        items=[
            BloodBankRead(
                id=1,
                name="Valid External Facility",
                city="Delhi",
                locality="Locality 1",
                source_type="external_source",
                source_name="e-RaktKosh (MoHFW)",
                stock_reports=[],
            ),
            BloodBankRead(
                id=2,
                name="Demo Facility",
                city="Delhi",
                locality="Locality 2",
                source_type="demo",
                source_name="Synthetic demo dataset",
                stock_reports=[],
            ),
            BloodBankRead(
                id=3,
                name="Unknown Source Facility",
                city="Delhi",
                locality="Locality 3",
                source_type="unknown_portal",
                source_name="Unknown",
                stock_reports=[],
            ),
            BloodBankRead(
                id=4,
                name="Empty Source Facility",
                city="Delhi",
                locality="Locality 4",
                source_type="",
                source_name="",
                stock_reports=[],
            ),
            BloodBankRead(
                id=5,
                name="Third Party Scraping Facility",
                city="Delhi",
                locality="Locality 5",
                source_type="third_party_scraper",
                source_name="Unapproved Crawler",
                stock_reports=[],
            ),
        ],
        count=5,
        data_notice="Notice",
        data_timestamp=now,
    )

    displayed, total_count = DiscoveryApiClient.filter_and_rank_facilities(
        response,
        blood_group="O+",
        max_facilities=10,
    )

    # Only facility 1 (source_type == 'external_source') must be admitted
    assert total_count == 1
    assert len(displayed) == 1
    assert displayed[0].id == 1
    assert displayed[0].name == "Valid External Facility"


def test_filter_and_rank_facilities_ignores_unrecognized_report_verification_status() -> None:
    """Only stock reports with verification_status == 'reported_unverified' contribute to ranking."""
    now = datetime(2026, 10, 16, 6, 0, 0, tzinfo=timezone.utc)
    response = BloodBankListResponse(
        items=[
            BloodBankRead(
                id=10,
                name="Facility with Unrecognized Report Status",
                city="Delhi",
                locality="Locality A",
                source_type="external_source",
                source_name="e-RaktKosh (MoHFW)",
                stock_reports=[
                    StockReportRead(
                        id=101,
                        blood_bank_id=10,
                        blood_group="O+",
                        blood_component="Whole Blood",
                        units_reported=100,
                        source_name="e-RaktKosh (MoHFW)",
                        verification_status="unrecognized_or_demo_status",
                        data_timestamp=now,
                    )
                ],
            ),
            BloodBankRead(
                id=11,
                name="Facility with Legitimate Reported Unverified Status",
                city="Delhi",
                locality="Locality B",
                source_type="external_source",
                source_name="e-RaktKosh (MoHFW)",
                stock_reports=[
                    StockReportRead(
                        id=102,
                        blood_bank_id=11,
                        blood_group="O+",
                        blood_component="Whole Blood",
                        units_reported=5,
                        source_name="e-RaktKosh (MoHFW)",
                        verification_status="reported_unverified",
                        data_timestamp=now,
                    )
                ],
            ),
        ],
        count=2,
        data_notice="Notice",
        data_timestamp=now,
    )

    displayed, total_count = DiscoveryApiClient.filter_and_rank_facilities(
        response,
        blood_group="O+",
        max_facilities=10,
    )

    assert total_count == 2
    # Facility 11 has legitimate positive reported units (5), while facility 10's unrecognized status
    # is ignored so it has 0 scored positive units. Facility 11 must be ranked first.
    assert [b.id for b in displayed] == [11, 10]


import asyncio


def test_get_blood_banks_successful_query(mock_discovery_response: BloodBankListResponse) -> None:
    """DiscoveryApiClient should send proper parameters and parse response envelope."""
    async def _test() -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/blood-banks"
            assert request.url.params["city"] == "Delhi"
            assert request.url.params["blood_group"] == "O+"
            return httpx.Response(200, json=mock_discovery_response.model_dump(mode="json"))

        transport = httpx.MockTransport(mock_handler)
        client = DiscoveryApiClient(base_url="http://testserver", transport=transport)
        result = await client.get_blood_banks(city="Delhi", blood_group="O+")

        assert result.count == 7
        assert len(result.items) == 7
        assert result.items[1].name == "AIIMS Blood Centre"

    asyncio.run(_test())


def test_get_blood_banks_handles_connection_error() -> None:
    """DiscoveryApiClient should raise DiscoveryApiError on connection failure."""
    async def _test() -> None:
        def error_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused", request=request)

        transport = httpx.MockTransport(error_handler)
        client = DiscoveryApiClient(base_url="http://offline-server", transport=transport)

        with pytest.raises(DiscoveryApiError, match="Unable to connect to discovery service"):
            await client.get_blood_banks(city="Delhi", blood_group="O+")

    asyncio.run(_test())


def test_get_blood_banks_handles_timeout_error() -> None:
    """DiscoveryApiClient should raise DiscoveryApiError on request timeout."""
    async def _test() -> None:
        def timeout_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("Timed out", request=request)

        transport = httpx.MockTransport(timeout_handler)
        client = DiscoveryApiClient(base_url="http://timeout-server", transport=transport)

        with pytest.raises(DiscoveryApiError, match="Discovery service request timed out"):
            await client.get_blood_banks(city="Delhi", blood_group="O+")

    asyncio.run(_test())


def test_get_blood_banks_handles_http_status_error() -> None:
    """DiscoveryApiClient should raise DiscoveryApiError on non-200 HTTP response."""
    async def _test() -> None:
        async def status_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(422, json={"detail": "Invalid blood group"})

        transport = httpx.MockTransport(status_handler)
        client = DiscoveryApiClient(base_url="http://testserver", transport=transport)

        with pytest.raises(DiscoveryApiError) as exc_info:
            await client.get_blood_banks(city="Delhi", blood_group="InvalidGroup")
        assert exc_info.value.status_code == 422

    asyncio.run(_test())
