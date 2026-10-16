"""Async Discovery API Client for RaktSetu Telegram Bot."""

from typing import Optional
import httpx

from backend.app.schemas.blood_bank import BloodBankListResponse, BloodBankRead


RECOGNIZED_EXTERNAL_SOURCE_TYPE: str = "external_source"
RECOGNIZED_EXTERNAL_VERIFICATION_STATUS: str = "reported_unverified"


class DiscoveryApiError(Exception):
    """Exception raised when discovery API communication or parsing fails."""

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class DiscoveryApiClient:
    """Async HTTP client to query RaktSetu's FastAPI discovery endpoint."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        timeout: float = 10.0,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    async def get_blood_banks(
        self,
        city: Optional[str] = None,
        blood_group: Optional[str] = None,
    ) -> BloodBankListResponse:
        """Fetch blood banks from the discovery API endpoint.

        Args:
            city: Optional city filter ('Delhi', 'Lucknow', or None/All).
            blood_group: Optional ABO/Rh group filter (e.g. 'O+', 'A-', etc.).

        Returns:
            Validated BloodBankListResponse envelope.

        Raises:
            DiscoveryApiError: On network errors, timeouts, or non-200 responses.
        """
        params: dict[str, str] = {}
        if city and city != "All":
            params["city"] = city
        if blood_group and blood_group != "All":
            params["blood_group"] = blood_group

        url = f"{self.base_url}/api/blood-banks"

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                return BloodBankListResponse.model_validate(data)
        except httpx.TimeoutException as exc:
            raise DiscoveryApiError(
                "Discovery service request timed out. Please try again shortly."
            ) from exc
        except httpx.ConnectError as exc:
            raise DiscoveryApiError(
                "Unable to connect to discovery service. Please ensure the server is running."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise DiscoveryApiError(
                f"Discovery service returned error ({exc.response.status_code}).",
                status_code=exc.response.status_code,
            ) from exc
        except Exception as exc:
            raise DiscoveryApiError(
                f"Failed to retrieve blood bank records: {str(exc)}"
            ) from exc

    @staticmethod
    def filter_and_rank_facilities(
        response: BloodBankListResponse,
        blood_group: Optional[str] = None,
        max_facilities: int = 5,
    ) -> tuple[list[BloodBankRead], int]:
        """Filter out demo/unknown records and rank facilities prioritizing positive reported stock.

        Invariants:
        1. Fails closed: includes ONLY records where source_type == 'external_source'.
        2. Strictly excludes demo records, missing-source records, and unknown/unrecognized source types.
        3. Only stock reports with verification_status == 'reported_unverified' contribute to positive scoring.
        4. Facilities reporting positive stock units (units > 0) are ranked first.
        5. Within positive facilities, higher reported unit counts are ranked first.
        6. Returns at most `max_facilities` items and the total recognized external count.

        Returns:
            Tuple of (displayed_facilities, total_recognized_external_count).
        """
        # Fail closed: Include ONLY explicitly recognized external-source records
        real_banks: list[BloodBankRead] = [
            b
            for b in response.items
            if getattr(b, "source_type", None) == RECOGNIZED_EXTERNAL_SOURCE_TYPE
        ]

        def _calculate_score(bank: BloodBankRead) -> tuple[int, int, int]:
            # Filter to relevant reports: must be recognized unverified external reports
            reports = [
                r
                for r in bank.stock_reports
                if r.verification_status == RECOGNIZED_EXTERNAL_VERIFICATION_STATUS
                and (blood_group is None or blood_group == "All" or r.blood_group == blood_group)
            ]
            total_positive_units = sum(r.units_reported for r in reports if r.units_reported > 0)
            has_positive = 1 if total_positive_units > 0 else 0
            # Higher positive first, then higher units, then stable id
            return (has_positive, total_positive_units, -bank.id)

        ranked = sorted(real_banks, key=_calculate_score, reverse=True)
        return (ranked[:max_facilities], len(real_banks))
