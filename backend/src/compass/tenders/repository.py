"""Idempotent persistence for tenders: upsert by expediente, never a plain insert."""

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from compass.tenders.models import Tender
from compass.tenders.schemas import TenderSchema


async def upsert_tender(session: AsyncSession, tender: TenderSchema) -> None:
    values = tender.model_dump()

    stmt = pg_insert(Tender).values(**values)
    update_values = {key: getattr(stmt.excluded, key) for key in values if key != "expediente"}
    update_values["updated_at"] = func.now()

    stmt = stmt.on_conflict_do_update(index_elements=[Tender.expediente], set_=update_values)
    await session.execute(stmt)
