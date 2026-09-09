"""Persistence for pliego analyses -- create and read by `pdf_hash`.

No upsert here, unlike `tenders.repository.upsert_tender`: a `pdf_hash` is a
content hash, not a republishable identifier -- the same hash means the same
document, so there is nothing to update in place. The "does this hash already
have a cached analysis, or do we need to start one" decision belongs to
whoever has a real hash to check (Phase 3.2 onward), not to this module.
"""

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
