"""Persistence for pliego analyses -- create and read by `pdf_hash`.

No upsert here, unlike `tenders.repository.upsert_tender`: a `pdf_hash` is a
content hash, not a republishable identifier -- the same hash means the same
document, so there is nothing to update in place. The "does this hash already
have a cached analysis, or do we need to start one" decision belongs to
whoever has a real hash to check (Phase 3.2 onward), not to this module.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from compass.analysis.enums import AnalysisStatus
from compass.analysis.models import TenderAnalysis


async def create_analysis(
    session: AsyncSession, *, expediente: str, pdf_hash: str
) -> TenderAnalysis:
    """Starts a new analysis row for `pdf_hash`, in `PENDING` status.

    Args:
        session: The active database session; the caller commits.
        expediente: Which tender this PCAP came from.
        pdf_hash: The document's own content hash -- the primary key, and
            what makes a duplicate call fail loudly (a real `pdf_hash`
            should only ever be created once) rather than silently
            overwriting an existing analysis.

    Returns:
        The newly created row, not yet flushed.
    """
    analysis = TenderAnalysis(
        pdf_hash=pdf_hash, expediente=expediente, status=AnalysisStatus.PENDING
    )
    session.add(analysis)
    return analysis


async def get_analysis(session: AsyncSession, pdf_hash: str) -> TenderAnalysis | None:
    """The analysis for `pdf_hash`, or `None` if this document has never been seen.

    Args:
        session: The active database session.
        pdf_hash: The document's own content hash.

    Returns:
        The cached row, whatever its `status`, or `None`.
    """
    return await session.get(TenderAnalysis, pdf_hash)


async def get_latest_analysis_for_tender(
    session: AsyncSession, expediente: str
) -> TenderAnalysis | None:
    """The most recent analysis for `expediente`, for `GET /tenders/{expediente}/analysis`.

    By `expediente` via `ix_tender_analyses_expediente`, not by `pdf_hash`: a caller here
    only ever knows the tender, never the PCAP's own content hash -- that's the whole
    reason this lookup exists alongside `get_analysis`, which the analysis task itself
    uses once it has actually downloaded and hashed the document.

    Args:
        session: The active database session.
        expediente: Which tender to look up.

    Returns:
        The row from the most recent analysis run for this tender, or `None` if it has
        never been analyzed.
    """
    stmt = (
        select(TenderAnalysis)
        .where(TenderAnalysis.expediente == expediente)
        .order_by(TenderAnalysis.created_at.desc())
        .limit(1)
    )
    return (await session.scalars(stmt)).first()
