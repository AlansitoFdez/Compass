"""GET /tenders — list tenders with basic filters and pagination."""

from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from compass.core.db import get_db
from compass.tenders.enums import TenderStatus
from compass.tenders.repository import list_tenders
from compass.tenders.schemas import TenderListResponse, TenderSchema

router = APIRouter(prefix="/tenders", tags=["tenders"])

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


@router.get("")
async def get_tenders(
    cpv: str | None = None,
    status: TenderStatus | None = None,
    min_budget: Decimal | None = None,
    max_budget: Decimal | None = None,
    location: str | None = None,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> TenderListResponse:
    """Lists tenders matching every given filter, paginated.

    All filter query params are optional and AND together, mirroring
    `repository.list_tenders`. `limit` is capped at `MAX_LIMIT` so a client
    can't request the whole table in one call.

    Returns:
        The matching page, plus `total` across all pages.
    """
    items, total = await list_tenders(
        session,
        cpv=cpv,
        status=status,
        min_budget=min_budget,
        max_budget=max_budget,
        location=location,
        limit=limit,
        offset=offset,
    )
    return TenderListResponse(
        items=[TenderSchema.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )
