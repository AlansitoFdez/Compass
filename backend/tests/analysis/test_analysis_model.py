"""Persistence round-trip test for the TenderAnalysis ORM model, against the real database."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from compass.analysis.enums import AnalysisStatus
from compass.analysis.models import TenderAnalysis
from compass.analysis.schemas import TenderAnalysisSchema
from compass.tenders.enums import ContractType, TenderStatus
from compass.tenders.models import Tender

# A hash-shaped string, not a real sha256 of anything -- the column doesn't
# care, it's just a String(64) primary key.
TEST_HASH = "a" * 64


def _tender(expediente: str) -> Tender:
    """A minimal valid `Tender` for `TenderAnalysis.expediente` to reference via its FK."""
    return Tender(
        expediente=expediente,
        contracting_body="Ayuntamiento de Prueba",
        title="Servicio de prueba",
        cpv_codes=["72000000"],
        contract_type=ContractType.SERVICES,
        procedure_type="Abierto",
        status=TenderStatus.OPEN_FOR_SUBMISSION,
        published_at=datetime.now(UTC),
        updated_at_source=datetime.now(UTC),
    )


async def test_tender_analysis_persists_and_round_trips(db_session: AsyncSession) -> None:
    """Protects the ORM mapping end to end: insert, fetch back, and re-validate as a schema.

    In particular, that `status` comes back as a real enum member (not the
    raw stored string), and that `created_at`'s `server_default=func.now()`
    actually fires.
    """
    db_session.add(_tender("TEST-ANALYSIS-0001"))
    await db_session.flush()

    analysis = TenderAnalysis(
        pdf_hash=TEST_HASH, expediente="TEST-ANALYSIS-0001", status=AnalysisStatus.PENDING
    )
    db_session.add(analysis)
    await db_session.flush()

    result = await db_session.execute(
        select(TenderAnalysis).where(TenderAnalysis.pdf_hash == TEST_HASH)
    )
    fetched = result.scalar_one()

    assert fetched.status is AnalysisStatus.PENDING
    assert fetched.extraction is None
    assert fetched.error_message is None
    assert fetched.created_at is not None

    schema = TenderAnalysisSchema.model_validate(fetched)
    assert schema.pdf_hash == TEST_HASH
