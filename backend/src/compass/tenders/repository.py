"""Persistence for tenders: upsert by expediente (never a plain insert) and filtered listing."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from compass.tenders.enums import TenderStatus
from compass.tenders.models import Tender
from compass.tenders.schemas import TenderSchema


async def upsert_tender(session: AsyncSession, tender: TenderSchema) -> None:
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
    filters = []
    if cpv is not None:
        # @> nativo de Postgres sobre el array, sin subconsultas (ver phase1.10.md).
        filters.append(Tender.cpv_codes.contains([cpv]))
    if status is not None:
        filters.append(Tender.status == status)
    if min_budget is not None:
        filters.append(Tender.budget_with_vat >= min_budget)
    if max_budget is not None:
        filters.append(Tender.budget_with_vat <= max_budget)
    if location is not None:
        filters.append(Tender.location == location)

    total = await session.scalar(select(func.count()).select_from(Tender).where(*filters))

    # published_at desc: orden explícito y estable, imprescindible para que
    # limit/offset devuelva páginas consistentes entre llamadas.
    items_stmt = (
        select(Tender)
        .where(*filters)
        .order_by(Tender.published_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = (await session.scalars(items_stmt)).all()

    return list(items), total or 0
