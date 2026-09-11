"""Persistence for pliego analyses -- one row per tender, plus the extraction cache.

Two lookups, and the difference between them is the whole point of the 5.2 rekeying:

- `get_analysis_for_tender` answers "what is the state of *this tender's* analysis",
  which is what `GET /tenders/{expediente}/analysis` and the dashboard need.
- `find_cached_extraction` answers "has this exact *document* already been read by the
  model, for any tender at all", which is what saves the expensive LLM call.

Before 5.2 both were the same lookup, keyed by `pdf_hash`, and the first one silently
failed whenever two tenders shared a PCAP. See `models.TenderAnalysis`.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from compass.analysis.enums import AnalysisStatus
from compass.analysis.models import STALE_AFTER_SECONDS, TenderAnalysis

# What a cached row must have reached for its extraction to be worth copying instead of
# calling the model again. `NOT_ANALYZABLE` counts: a scanned PCAP with no text layer is a
# settled answer, not a failure to retry (v1 does no OCR).
_REUSABLE_STATUSES = (AnalysisStatus.COMPLETED, AnalysisStatus.NOT_ANALYZABLE)


async def get_or_create_analysis(session: AsyncSession, *, expediente: str) -> TenderAnalysis:
    """This tender's analysis row, creating it in `PENDING` if it has none yet.

    Get-or-create rather than a plain insert: there is exactly one row per tender, and it
    is rewritten in place every time that tender is re-analyzed (a republished PCAP, a
    retry after a failure).

    Args:
        session: The active database session; the caller commits.
        expediente: Which tender the analysis belongs to.

    Returns:
        The existing row, or a new `PENDING` one already added to the session.
    """
    existing = await session.get(TenderAnalysis, expediente)
    if existing is not None:
        return existing

    analysis = TenderAnalysis(expediente=expediente, status=AnalysisStatus.PENDING)
    session.add(analysis)
    return analysis


async def get_analysis_for_tender(session: AsyncSession, expediente: str) -> TenderAnalysis | None:
    """This tender's analysis, or `None` if it has never been analyzed.

    A primary-key read since 5.2, which also removes the tie it used to have: the previous
    implementation ordered several rows by `created_at`, a column whose `server_default` is
    `now()` -- frozen for a whole transaction, so two rows written together compared equal
    and "the most recent" was whichever the planner happened to return.

    Args:
        session: The active database session.
        expediente: Which tender to look up.

    Returns:
        The row, or `None`.
    """
    return await session.get(TenderAnalysis, expediente)


async def find_cached_extraction(
    session: AsyncSession, pdf_hash: str, *, exclude_expediente: str
) -> TenderAnalysis | None:
    """A settled analysis of this exact document, from some *other* tender.

    The extraction is provider-agnostic and derived only from the PDF's bytes, so an
    identical document never needs a second LLM call -- the expensive half of an analysis
    (see docs/phases/phase3/phase3.md).

    Args:
        session: The active database session.
        pdf_hash: The document's content hash.
        exclude_expediente: The tender being analyzed, skipped so a caller can't "reuse"
            its own row and mistake it for a cache hit.

    Returns:
        A row whose status is `COMPLETED` or `NOT_ANALYZABLE`, or `None`.
    """
    stmt = (
        select(TenderAnalysis)
        .where(
            TenderAnalysis.pdf_hash == pdf_hash,
            TenderAnalysis.expediente != exclude_expediente,
            TenderAnalysis.status.in_(_REUSABLE_STATUSES),
        )
        .limit(1)
    )
    return (await session.scalars(stmt)).first()


def is_stale(analysis: TenderAnalysis, *, now: datetime | None = None) -> bool:
    """Whether an `IN_PROGRESS` row has outlived the run that was supposed to finish it.

    A worker killed between the commit that sets `IN_PROGRESS` and the one that writes the
    result leaves a row nothing will ever touch again: the Redis lock expires on its own,
    the row does not. The dashboard then polls that status forever and never shows the
    button again, because the button only appears for "never analyzed" or "failed".

    Args:
        analysis: The row to judge.
        now: Current time, injectable for tests.

    Returns:
        `True` only for an `IN_PROGRESS` row last touched more than
        `STALE_AFTER_SECONDS` ago -- the window in which a real run is still protected by
        its lock.
    """
    if analysis.status != AnalysisStatus.IN_PROGRESS:
        return False
    reference = now or datetime.now(UTC)
    return (reference - analysis.updated_at).total_seconds() > STALE_AFTER_SECONDS
