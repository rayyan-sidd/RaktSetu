from typing import Any, Final, Optional

import httpx

from backend.app.services.eraktkosh.types import SUPPORTED_CITIES

DEFAULT_TIMEOUT_SECONDS: Final[float] = 15.0
ERAKTKOSH_STOCK_URL: Final[str] = "https://eraktkosh.mohfw.gov.in/BLDAHIMS/bloodbank/nearbyBB.cnt"

# Official state and district query codes verified from e-RaktKosh search portal
CITY_QUERY_CONFIG: Final[dict[str, dict[str, int]]] = {
    "Delhi": {"state_code": 97, "district_code": -1},
    "Lucknow": {"state_code": 99, "district_code": 157},
}

# Component code map mapping standard component names to e-RaktKosh query values
COMPONENT_CODE_MAP: Final[dict[str, str]] = {
    "Whole Blood": "11",
    "Packed Red Blood Cells": "12",
    "Platelets": "14",
    "Fresh Frozen Plasma": "13",
}

DEFAULT_HEADERS: Final[dict[str, str]] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Referer": "https://eraktkosh.mohfw.gov.in/BLDAHIMS/bloodbank/stockAvailability.cnt",
    "X-Requested-With": "XMLHttpRequest",
}


class ERaktKoshRetrievalError(Exception):
    """Raised when an error occurs during retrieval from the e-RaktKosh public stock portal."""

    pass


class ERaktKoshClient:
    """Retrieval client for querying official public blood-stock availability from e-RaktKosh.

    Safety & Invariants:
    - Uses standard timeouts (default 15.0s) and does not perform aggressive or repeated polling.
    - Queries only the verified public endpoint and parameters used by the public search interface.
    - Does not bypass authentication, challenge checks, WAF protections, or access controls.
    - Does not use TinyFish or any third-party paid proxies.
    """

    def __init__(
        self,
        base_url: str = ERAKTKOSH_STOCK_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self.headers = headers or DEFAULT_HEADERS.copy()

    def fetch_stock_details(
        self,
        city: str,
        component: str = "Whole Blood",
    ) -> dict[str, Any]:
        """Retrieve public blood-stock availability data for a target city and component.

        Args:
            city: Supported city name ("Delhi" or "Lucknow").
            component: Blood component label (defaults to "Whole Blood").

        Returns:
            dict[str, Any]: Parsed JSON response payload from e-RaktKosh.

        Raises:
            ValueError: If city or component is not supported.
            ERaktKoshRetrievalError: If a connection error, timeout, HTTP error,
                                     or malformed response envelope occurs.
        """
        if city not in CITY_QUERY_CONFIG:
            raise ValueError(
                f"Unsupported city '{city}'. Supported cities: {list(CITY_QUERY_CONFIG.keys())}."
            )

        component_code = COMPONENT_CODE_MAP.get(component)
        if not component_code:
            raise ValueError(
                f"Unsupported component '{component}'. Supported components: {list(COMPONENT_CODE_MAP.keys())}."
            )

        config = CITY_QUERY_CONFIG[city]
        params: dict[str, str] = {
            "hmode": "GETNEARBYSTOCKDETAILS",
            "stateCode": str(config["state_code"]),
            "districtCode": str(config["district_code"]),
            "bloodGroup": "all",
            "bloodComponent": component_code,
            "lang": "0",
        }

        try:
            with httpx.Client(timeout=self.timeout, headers=self.headers) as client:
                response = client.get(self.base_url, params=params)
        except httpx.TimeoutException as exc:
            raise ERaktKoshRetrievalError(
                f"Connection timeout ({self.timeout}s) while querying e-RaktKosh for {city}."
            ) from exc
        except httpx.RequestError as exc:
            raise ERaktKoshRetrievalError(
                f"Network connection failed while querying e-RaktKosh for {city}: {exc}"
            ) from exc

        if response.status_code != 200:
            raise ERaktKoshRetrievalError(
                f"e-RaktKosh returned non-200 HTTP status code {response.status_code} for {city}."
            )

        try:
            payload = response.json()
        except Exception as exc:
            raise ERaktKoshRetrievalError(
                f"Failed to decode JSON response from e-RaktKosh for {city}: {exc}"
            ) from exc

        if not isinstance(payload, dict):
            raise ERaktKoshRetrievalError(
                f"Invalid e-RaktKosh response envelope: expected JSON object, got {type(payload).__name__}."
            )

        if "data" not in payload or not isinstance(payload["data"], list):
            raise ERaktKoshRetrievalError(
                f"Invalid e-RaktKosh response envelope: missing or invalid 'data' row array for {city}."
            )

        return payload
