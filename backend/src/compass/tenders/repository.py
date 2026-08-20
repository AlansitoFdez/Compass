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
    filters: list[ColumnElement[bool]] = []
    if cpv is not None:
        # Prefijo, no exacto: la 1.10 usaba `@>` (coincidencia exacta) para
        # evitar un unnest(), pero eso rompe el caso de uso real -- filtrar
        # por división CPV (p.ej. "72", los servicios TI que definen el
        # producto entero) siempre devolvía cero resultados, porque ningún
        # código guardado es literalmente "72". `vertical.py` ya filtra por
        # prefijo en la ingesta; la API debe ser consistente con eso (bug 7
        # de la 1.11). Un prefijo de 8 dígitos completo sigue actuando como
        # coincidencia exacta -- ningún otro código CPV comparte ese prefijo.
        escaped = (
            normalize_cpv_code(cpv).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
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
