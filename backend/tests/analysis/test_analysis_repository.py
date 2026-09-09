"""Tests for create_analysis/get_analysis -- real Postgres, no mocking."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from compass.analysis.enums import AnalysisStatus
from compass.analysis.repository import create_analysis, get_analysis
from compass.tenders.enums import ContractType, TenderStatus
from compass.tenders.models import Tender

TEST_HASH = "b" * 64


def _tender(expediente: str) -> Tender:
    """A minimal valid `Tender` for `create_analysis`'s `expediente` to reference via its FK."""
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


async def test_create_analysis_starts_pending(db_session: AsyncSession) -> None:
    """Protects the base case: a new analysis starts `PENDING`, with no extraction yet."""
    db_session.add(_tender("TEST-REPO-ANALYSIS-0001"))
    await db_session.flush()

    analysis = await create_analysis(
        db_session, expediente="TEST-REPO-ANALYSIS-0001", pdf_hash=TEST_HASH
    )
    await db_session.flush()

    assert analysis.status is AnalysisStatus.PENDING
    assert analysis.extraction is None


async def test_get_analysis_returns_none_for_an_unseen_hash(db_session: AsyncSession) -> None:
    """Protects the cache-miss case: a hash never analyzed returns `None`, not an error."""
    result = await get_analysis(db_session, "never-seen-" + "c" * 53)

    assert result is None


async def test_get_analysis_returns_the_cached_row(db_session: AsyncSession) -> None:
    """Protects the cache-hit case: a previously created analysis comes back by its hash."""
    db_session.add(_tender("TEST-REPO-ANALYSIS-0002"))
    await db_session.flush()
    await create_analysis(db_session, expediente="TEST-REPO-ANALYSIS-0002", pdf_hash=TEST_HASH)
    await db_session.flush()

    result = await get_analysis(db_session, TEST_HASH)

    assert result is not None
    assert result.expediente == "TEST-REPO-ANALYSIS-0002"


async def test_create_analysis_rejects_a_duplicate_hash(db_session: AsyncSession) -> None:
    """Protects the cache's own invariant: `pdf_hash` identifies one document, so creating it
    twice must fail loudly (a primary-key violation), never silently overwrite the first row.
    """
    db_session.add(_tender("TEST-REPO-ANALYSIS-0003"))
    await db_session.flush()
    await create_analysis(db_session, expediente="TEST-REPO-ANALYSIS-0003", pdf_hash=TEST_HASH)
    await db_session.flush()

    await create_analysis(db_session, expediente="TEST-REPO-ANALYSIS-0003", pdf_hash=TEST_HASH)
    with pytest.raises(IntegrityError):
        await db_session.flush()
