"""Tests for the analysis repository -- real Postgres, no mocking.

Rewritten in 5.2 around the rekeying: the row is keyed by `expediente` now, and the
document hash only drives the extraction cache. The tests that used to protect the old
key (creating the same `pdf_hash` twice must raise) protect the opposite property now --
two tenders sharing a PCAP must *both* get a row.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from compass.analysis.enums import AnalysisStatus
from compass.analysis.models import STALE_AFTER_SECONDS, TenderAnalysis
from compass.analysis.repository import (
    find_cached_extraction,
    get_analysis_for_tender,
    get_or_create_analysis,
    is_stale,
)
from compass.tenders.enums import ContractType, TenderStatus
from compass.tenders.models import Tender

TEST_HASH = "b" * 64


def _tender(expediente: str) -> Tender:
    """A minimal valid `Tender` for the analysis `expediente` to reference via its FK."""
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


async def test_get_or_create_starts_pending(db_session: AsyncSession) -> None:
    """Protects the base case: a new analysis starts `PENDING`, with no extraction yet."""
    db_session.add(_tender("TEST-REPO-ANALYSIS-0001"))
    await db_session.flush()

    analysis = await get_or_create_analysis(db_session, expediente="TEST-REPO-ANALYSIS-0001")
    await db_session.flush()

    assert analysis.status is AnalysisStatus.PENDING
    assert analysis.extraction is None
    assert analysis.pdf_hash is None


async def test_get_or_create_returns_the_same_row_twice(db_session: AsyncSession) -> None:
    """Protects re-analysis: a tender has one analysis row that gets rewritten in place, so
    asking twice must not produce a second row -- which under the old `pdf_hash` key was a
    primary-key violation instead.
    """
    db_session.add(_tender("TEST-REPO-ANALYSIS-0002"))
    await db_session.flush()

    first = await get_or_create_analysis(db_session, expediente="TEST-REPO-ANALYSIS-0002")
    first.pdf_hash = TEST_HASH
    await db_session.flush()
    second = await get_or_create_analysis(db_session, expediente="TEST-REPO-ANALYSIS-0002")

    assert second is first
    assert second.pdf_hash == TEST_HASH


async def test_get_analysis_for_tender_returns_none_when_never_analyzed(
    db_session: AsyncSession,
) -> None:
    """Protects the miss case: a tender never analyzed reads as `None`, not an error."""
    assert await get_analysis_for_tender(db_session, "TEST-REPO-ANALYSIS-MISSING") is None


async def test_two_tenders_sharing_a_pcap_each_keep_their_own_row(
    db_session: AsyncSession,
) -> None:
    """Protects the bug the rekeying fixed: with `pdf_hash` as the primary key, the second
    tender to be analyzed had no row of its own, so reading its analysis by expediente
    returned 404 forever while the task kept hitting the cache and writing nothing.
    """
    db_session.add_all([_tender("TEST-REPO-SHARED-A"), _tender("TEST-REPO-SHARED-B")])
    await db_session.flush()

    for expediente in ("TEST-REPO-SHARED-A", "TEST-REPO-SHARED-B"):
        analysis = await get_or_create_analysis(db_session, expediente=expediente)
        analysis.pdf_hash = TEST_HASH
        analysis.status = AnalysisStatus.COMPLETED
    await db_session.flush()

    for expediente in ("TEST-REPO-SHARED-A", "TEST-REPO-SHARED-B"):
        found = await get_analysis_for_tender(db_session, expediente)
        assert found is not None
        assert found.expediente == expediente


async def test_find_cached_extraction_finds_another_tenders_settled_analysis(
    db_session: AsyncSession,
) -> None:
    """Protects what the hash is still for: the same document already read by the model
    must be reusable, so an identical PCAP never costs a second LLM call.
    """
    db_session.add_all([_tender("TEST-REPO-CACHE-A"), _tender("TEST-REPO-CACHE-B")])
    await db_session.flush()
    done = await get_or_create_analysis(db_session, expediente="TEST-REPO-CACHE-A")
    done.pdf_hash = TEST_HASH
    done.status = AnalysisStatus.COMPLETED
    await db_session.flush()

    cached = await find_cached_extraction(
        db_session, TEST_HASH, exclude_expediente="TEST-REPO-CACHE-B"
    )

    assert cached is not None
    assert cached.expediente == "TEST-REPO-CACHE-A"


async def test_find_cached_extraction_ignores_unsettled_and_own_rows(
    db_session: AsyncSession,
) -> None:
    """Protects the two ways a "hit" would be wrong: a run still in progress is not an
    answer to copy, and a tender must never mistake its own row for someone else's cache.
    """
    db_session.add_all([_tender("TEST-REPO-CACHE-C"), _tender("TEST-REPO-CACHE-D")])
    await db_session.flush()
    running = await get_or_create_analysis(db_session, expediente="TEST-REPO-CACHE-C")
    running.pdf_hash = TEST_HASH
    running.status = AnalysisStatus.IN_PROGRESS
    own = await get_or_create_analysis(db_session, expediente="TEST-REPO-CACHE-D")
    own.pdf_hash = TEST_HASH
    own.status = AnalysisStatus.COMPLETED
    await db_session.flush()

    assert (
        await find_cached_extraction(db_session, TEST_HASH, exclude_expediente="TEST-REPO-CACHE-D")
        is None
    )


def _analysis(status: AnalysisStatus, *, age_seconds: float) -> TenderAnalysis:
    """A detached row with a chosen status and `updated_at` age, for `is_stale`."""
    analysis = TenderAnalysis(expediente="TEST-REPO-STALE", status=status)
    analysis.updated_at = datetime.now(UTC) - timedelta(seconds=age_seconds)
    return analysis


def test_is_stale_only_flags_an_abandoned_in_progress_row() -> None:
    """Protects the window a live run is entitled to: while its Redis lock still holds, an
    `IN_PROGRESS` row is work in progress, not a corpse.
    """
    assert is_stale(_analysis(AnalysisStatus.IN_PROGRESS, age_seconds=STALE_AFTER_SECONDS + 60))
    assert not is_stale(_analysis(AnalysisStatus.IN_PROGRESS, age_seconds=30))


def test_is_stale_never_flags_a_settled_row() -> None:
    """Protects against an old completed analysis being reported as a failure just for
    having been finished a long time ago.
    """
    for status in (AnalysisStatus.COMPLETED, AnalysisStatus.FAILED, AnalysisStatus.NOT_ANALYZABLE):
        assert not is_stale(_analysis(status, age_seconds=STALE_AFTER_SECONDS * 10))
