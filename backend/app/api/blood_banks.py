from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.core.database import get_db
from backend.app.models.blood_bank import SUPPORTED_BLOOD_GROUPS, SUPPORTED_CITIES, BloodBank, StockReport
from backend.app.schemas.blood_bank import BloodBankListResponse, BloodBankRead, StockReportRead

router = APIRouter(prefix="/api", tags=["blood-banks"])


def _validate_city(city: Optional[str]) -> Optional[str]:
    """Validate and normalize optional city query parameter."""
    if city is None:
        return None

    cleaned_city = city.strip().title()
    if cleaned_city not in SUPPORTED_CITIES:
        valid_cities_str = ", ".join(sorted(SUPPORTED_CITIES))
        raise HTTPException(
            status_code=422,
            detail=f"Invalid city '{city}'. Supported cities: {valid_cities_str}.",
        )
    return cleaned_city


def _validate_blood_group(blood_group: Optional[str]) -> Optional[str]:
    """Validate and normalize optional blood group query parameter.

    Handles URL decoding where '+' can be parsed as a space (e.g. 'A ' -> 'A+').
    """
    if blood_group is None:
        return None

    normalized = blood_group.strip().upper()
    if blood_group.endswith(" "):
        normalized = blood_group.rstrip().upper() + "+"

    if normalized not in SUPPORTED_BLOOD_GROUPS:
        valid_groups_str = ", ".join(sorted(SUPPORTED_BLOOD_GROUPS))
        raise HTTPException(
            status_code=422,
            detail=f"Invalid blood group '{normalized}'. Supported blood groups: {valid_groups_str}.",
        )
    return normalized


@router.get(
    "/blood-banks",
    response_model=BloodBankListResponse,
    status_code=status.HTTP_200_OK,
    summary="Discover Blood Banks",
    description=(
        "Query reported blood banks and their stock reports across Delhi and Lucknow. "
        "Allows optional filtering by city and blood group. "
        "Returns items, bank count, and an explicit synthetic data disclaimer notice."
    ),
)
def get_blood_banks(
    city: Optional[str] = Query(
        None,
        description="Filter by city: 'Delhi' or 'Lucknow'",
        examples=["Delhi"],
    ),
    blood_group: Optional[str] = Query(
        None,
        description="Filter by blood group: 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'",
        examples=["O+"],
    ),
    db: Session = Depends(get_db),
) -> BloodBankListResponse:
    """Return matching blood banks, total bank count, and a synthetic data notice."""
    city_filter = _validate_city(city)
    blood_group_filter = _validate_blood_group(blood_group)

    stmt = select(BloodBank).options(selectinload(BloodBank.stock_reports))

    if city_filter:
        stmt = stmt.where(BloodBank.city == city_filter)

    if blood_group_filter:
        stmt = stmt.where(
            BloodBank.stock_reports.any(StockReport.blood_group == blood_group_filter)
        )

    banks = db.scalars(stmt.order_by(BloodBank.id.asc())).all()

    items: list[BloodBankRead] = []
    for bank in banks:
        if blood_group_filter:
            filtered_reports = [r for r in bank.stock_reports if r.blood_group == blood_group_filter]
        else:
            filtered_reports = bank.stock_reports

        items.append(
            BloodBankRead(
                id=bank.id,
                name=bank.name,
                city=bank.city,
                locality=bank.locality,
                stock_reports=[StockReportRead.model_validate(r) for r in filtered_reports],
            )
        )

    return BloodBankListResponse(
        items=items,
        count=len(items),
    )
