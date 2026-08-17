"""Idempotency tests for upsert_tender — real Postgres, no mocking."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from compass.tenders.enums import ContractType, TenderStatus
from compass.tenders.models import Tender
from compass.tenders.repository import upsert_tender
from compass.tenders.schemas import TenderSchema

BASE_TENDER = TenderSchema(
    expediente="TEST-REPO-0001",
    contracting_body="Ayuntamiento de Prueba",
    title="Servicio de prueba",
    cpv_codes=["72000000"],
    contract_type=ContractType.SERVICES,
    procedure_type="Abierto",
    status=TenderStatus.OPEN_FOR_SUBMISSION,
    submission_deadline=datetime.now(UTC),
    published_at=datetime.now(UTC),
    updated_at_source=datetime.now(UTC),
)


async def _fetch_all(session: AsyncSession, expediente: str) -> list[Tender]:
    # expire_all(): olvida lo que la sesión tuviera en caché, para releer de
    # verdad de la base de datos tras un upsert (ver hallazgo en phase1.7.md).
    session.expire_all()
    result = await session.execute(select(Tender).where(Tender.expediente == expediente))
    return list(result.scalars().all())


async def test_upsert_tender_creates_a_new_row(db_session: AsyncSession) -> None:
    await upsert_tender(db_session, BASE_TENDER)
    await db_session.flush()

    assert len(await _fetch_all(db_session, BASE_TENDER.expediente)) == 1


async def test_upsert_tender_processed_twice_with_same_data_is_one_row(
    db_session: AsyncSession,
) -> None:
    await upsert_tender(db_session, BASE_TENDER)
    await upsert_tender(db_session, BASE_TENDER)
    await db_session.flush()

    assert len(await _fetch_all(db_session, BASE_TENDER.expediente)) == 1


async def test_upsert_tender_updates_fields_and_preserves_created_at(
    db_session: AsyncSession,
) -> None:
    await upsert_tender(db_session, BASE_TENDER)
    await db_session.flush()
    first = (await _fetch_all(db_session, BASE_TENDER.expediente))[0]
    # Capturados como valores sueltos, no como atributos de `first`: el mapa
    # de identidad de la sesión muta `first` in-place en la siguiente consulta
    # (misma fila = mismo objeto Python), así que comparar contra `first.x`
    # más adelante compararía un objeto contra sí mismo ya actualizado.
    first_created_at = first.created_at
    first_updated_at = first.updated_at

    modified = BASE_TENDER.model_copy(
        update={"title": "Servicio de prueba (modificado)", "submission_deadline": None}
    )
    await upsert_tender(db_session, modified)
    await db_session.flush()
    second = (await _fetch_all(db_session, BASE_TENDER.expediente))[0]

    assert second.title == "Servicio de prueba (modificado)"
    assert second.submission_deadline is None
    assert second.created_at == first_created_at
    assert second.updated_at > first_updated_at
