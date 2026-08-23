"""Persistence for tenders: upsert by expediente (never a plain insert) and filtered listing."""

from decimal import Decimal

from sqlalchemy import ColumnElement, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from compass.tenders.enums import TenderStatus
from compass.tenders.models import Tender
from compass.tenders.schemas import TenderSchema
from compass.tenders.vertical import normalize_cpv_code

# CPV codes are always exactly 8 digits (EU classification: division + group
# + class + category + subcategory) once the check digit is stripped.
FULL_CPV_CODE_LENGTH = 8


async def upsert_tender(session: AsyncSession, tender: TenderSchema) -> None:
    """Insert a tender, or update it in place if its expediente already exists.

    PLACSP republishes the same expediente every time it changes, so this is
    always an upsert keyed on `expediente` (see `Tender.__doc__`), never a
    plain insert -- a withdrawal arrives here as a `status` change, not a
    delete.

    Args:
        session: The active database session; the caller commits.
        tender: The parsed, validated tender to persist.
    """
    values = tender.model_dump()

    stmt = pg_insert(Tender).values(**values)
    update_values = {key: getattr(stmt.excluded, key) for key in values if key != "expediente"}
    # clock_timestamp(), not now(): now() is frozen at transaction start and
    # would give the same value for every upsert in the same transaction.
    update_values["updated_at"] = func.clock_timestamp()

    stmt = stmt.on_conflict_do_update(index_elements=[Tender.expediente], set_=update_values)
    await session.execute(stmt)


async def list_tenders(
    session: AsyncSession,
    *,
    cpv: str | None = None,
    status: TenderStatus | None = None,
    min_budget: Decimal | None = None,
    max_budget: Decimal | None = None,
    location: str | None = None,
    limit: int,
    offset: int,
) -> tuple[list[Tender], int]:
    """List tenders matching every given filter, plus the total match count.

    All filters are optional and AND together; `limit`/`offset` are always
    required so a caller can't accidentally page through the whole table.

    Args:
        session: The active database session.
        cpv: A CPV code or prefix (e.g. "72" for the whole IT-services
            division). Normalized the same way as `vertical.py` does at
            ingestion, so the filter stays consistent with what was actually
            stored.
        status: Restrict to tenders in this lifecycle status.
        min_budget: Lower bound (inclusive) on `budget_with_vat`.
        max_budget: Upper bound (inclusive) on `budget_with_vat`.
        location: Exact match on `location`.
        limit: Maximum number of rows to return.
        offset: Number of matching rows to skip, for pagination.

    Returns:
        The page of matching tenders, and the total count across all pages
        (before `limit`/`offset` are applied).
    """
    filters: list[ColumnElement[bool]] = []
    if cpv is not None:
        # Prefix match, not exact: 1.10 used `@>` (exact match) to avoid an
        # unnest(), but that broke the real use case -- filtering by CPV
        # division (e.g. "72", the whole IT-services vertical) always
        # returned zero results, because no stored code is literally "72".
        # `vertical.py` already filters by prefix at ingestion; the API must
        # stay consistent with that (bug 7 of 1.11).
        normalized = normalize_cpv_code(cpv)
        if len(normalized) == FULL_CPV_CODE_LENGTH:
            # Full code: still an exact match -- no CPV code shares an
            # 8-digit prefix with another -- and `@>` can use the GIN index
            # (see phase1.11.md, step 7), unlike the unnest()+LIKE branch below.
            filters.append(Tender.cpv_codes.contains([normalized]))
        else:
            escaped = normalized.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            unnested = func.unnest(Tender.cpv_codes).table_valued("code").render_derived()
            filters.append(
                select(1).select_from(unnested).where(unnested.c.code.like(f"{escaped}%")).exists()
            )
    if status is not None:
        filters.append(Tender.status == status)
    if min_budget is not None:
        filters.append(Tender.budget_with_vat >= min_budget)
    if max_budget is not None:
        filters.append(Tender.budget_with_vat <= max_budget)
    if location is not None:
        filters.append(Tender.location == location)

    total = await session.scalar(select(func.count()).select_from(Tender).where(*filters))

    # published_at desc: explicit, stable ordering, required for limit/offset
    # to return consistent pages across calls.
    items_stmt = (
        select(Tender)
        .where(*filters)
        .order_by(Tender.published_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = (await session.scalars(items_stmt)).all()

    return list(items), total or 0
