"""Persistence round-trip test for the Tender ORM model, against the real database."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from compass.tenders.enums import ContractType, TenderStatus
from compass.tenders.models import EMBEDDING_DIMENSIONS, Tender
from compass.tenders.schemas import TenderSchema


async def test_tender_persists_and_round_trips(db_session: AsyncSession) -> None:
    """Protects the ORM mapping end to end: insert, fetch back, and re-validate as a schema.

    In particular, that `contract_type`/`status` come back as real enum
    members (not the raw stored strings) -- the `values_callable=` mapping
    in `models.py` is what makes that work, and a regression there would
    silently pass a string where an enum is expected instead of failing loud.
    Also that `created_at`'s `server_default=func.now()` actually fires, and
    that a fetched row can build a `TenderSchema` via `from_attributes=True`.
    """
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


async def test_tender_title_embedding_defaults_to_null_and_round_trips_when_set(
    db_session: AsyncSession,
) -> None:
    """Protects two things about `title_embedding`: a freshly inserted tender leaves it NULL
    (populated later by `matching.tasks.generate_embeddings_task`, not at insert time), and a
    real `EMBEDDING_DIMENSIONS`-length vector persists and comes back unchanged via pgvector.
    """
    tender = Tender(
        expediente="TEST-0002",
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
    assert tender.title_embedding is None

    vector = [0.1] * EMBEDDING_DIMENSIONS
    tender.title_embedding = vector
    await db_session.flush()
    await db_session.refresh(tender)

    assert tender.title_embedding == pytest.approx(vector)
