"""Persistence round-trip test for the Tender ORM model, against the real database."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from compass.tenders.enums import ContractType, TenderStatus
from compass.tenders.models import Tender
from compass.tenders.schemas import TenderSchema


async def test_tender_persists_and_round_trips(db_session: AsyncSession) -> None:
    tender = Tender(
        expediente="TEST-0001",
        contracting_body="Ayuntamiento de Prueba",
        title="Servicio de desarrollo de prueba",
        cpv_codes=["72000000"],
        contract_type=ContractType.SERVICES,
        procedure_type="open",
        status=TenderStatus.OPEN_FOR_SUBMISSION,
        published_at=datetime.now(UTC),
        updated_at_source=datetime.now(UTC),
    )
    db_session.add(tender)
    await db_session.flush()

    result = await db_session.execute(select(Tender).where(Tender.expediente == "TEST-0001"))
    fetched = result.scalar_one()

    assert fetched.contract_type is ContractType.SERVICES
    assert fetched.status is TenderStatus.OPEN_FOR_SUBMISSION
    assert fetched.created_at is not None

    schema = TenderSchema.model_validate(fetched)
    assert schema.expediente == "TEST-0001"
