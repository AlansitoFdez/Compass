"""GET /tenders — list tenders with basic filters and pagination, and read one by expediente."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from compass.core.db import get_db
from compass.tenders.enums import TenderStatus
from compass.tenders.models import Tender
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


# Declared after the list route, and with a literal prefix that can't swallow it: FastAPI
# matches in declaration order, so a path param this broad registered first would capture
# every later `/tenders/...` path too.
@router.get("/{expediente:path}")
async def get_tender(expediente: str, session: AsyncSession = Depends(get_db)) -> TenderSchema:
    """One tender by its expediente.

    Exists for the dashboard's tender page (5.1), which has to work on a reload or a
    shared link -- not only when arrived at from the list, carrying the data along.

    `:path` in the route, unlike every other param in this API: real PLACSP expedientes
    carry slashes (`SER/2026/0000006435`, `300/2026/01246`), and the default converter
    stops at the first one, so those tenders would 404 on their own detail page.

    Raises:
        HTTPException: 404 if no tender has this expediente.

    Returns:
        The tender, in the same shape the list endpoint serializes.
    """
    tender = await session.get(Tender, expediente)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found")
    return TenderSchema.model_validate(tender)
