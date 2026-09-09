"""The on-demand pliego analysis Celery task: bridges the sync Celery model into our
async pipeline, same shape as `compass.ingestion.tasks.daily_ingestion_task` and
`compass.matching.tasks.generate_embeddings_task`.

Unlike those two, this task is never scheduled by beat (see `core/celery_app.py`): an
analysis is expensive (an LLM call) and only worth running when someone actually asks
for a specific tender, never in batch over every match -- see
`docs/phases/phase3/phase3.md`.
"""

import asyncio
import logging
import sys

import httpx2
from redis.exceptions import LockError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from compass.analysis.document import hash_document
from compass.analysis.enums import AnalysisStatus
from compass.analysis.graph import EXTRACTION_MODEL, analyze_pliego
from compass.analysis.repository import create_analysis, get_analysis
from compass.core.celery_app import celery_app
from compass.core.config import get_settings
from compass.core.db import create_task_engine
from compass.core.redis_client import get_redis_client
from compass.tenders.models import Tender

logger = logging.getLogger(__name__)

LOCK_KEY_TEMPLATE = "analysis:{expediente}:lock"
# An analysis is one HTTP download plus one LLM call over a single pliego --
# minutes at worst, not the hours a full ingestion backlog could take. Kept
# generous anyway for the same reason as daily_ingestion_task's own timeout:
# a run that outlives this expires the lock on its own rather than blocking
# every future retry forever if a worker process dies mid-run.
LOCK_TIMEOUT_SECONDS = 900

# Statuses that mean "don't bother calling the LLM again for this exact
# document" -- NOT_ANALYZABLE is terminal by design (v1 does no OCR, see
# AnalysisStatus's own docstring); COMPLETED is the real cache hit this
# whole subphase exists to serve. FAILED and IN_PROGRESS are deliberately
# absent: a FAILED run is retried, not treated as a permanent answer, and
# IN_PROGRESS on a *different* expediente sharing this exact hash still
# needs its own row's outcome, not a second one racing it.
_SKIP_STATUSES = frozenset({AnalysisStatus.COMPLETED, AnalysisStatus.NOT_ANALYZABLE})


async def _run(expediente: str) -> AnalysisStatus | None:
    """Runs one analysis inside its own event loop and engine.

    Returns:
        The resulting status, or `None` if there was nothing to analyze (missing
        tender or `pcap_url`) -- distinct from every real `AnalysisStatus`, since a
        Celery task with no result backend only surfaces this to the log, not to a
        caller (see the task's own docstring).
    """
    engine = create_task_engine()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session, httpx2.AsyncClient(timeout=60) as client:
            return await analyze_tender(session, client, expediente)
    finally:
        await engine.dispose()


async def analyze_tender(
    session: AsyncSession, client: httpx2.AsyncClient, expediente: str
) -> AnalysisStatus | None:
    """Analyzes one tender's current PCAP, reusing a cached result when one already exists.

    The real orchestration -- `analyze_tender_task` is only the Celery/lock wrapper
    around this, same split as `ingestion.daily_ingestion.run_daily_ingestion` and
    `matching.tasks.generate_embeddings`.

    Args:
        session: The active database session; commits happen inside this function
            (once before the extraction call, so `IN_PROGRESS` is visible to a
            poller, and once after), not left to the caller.
        client: The async HTTP client to fetch the PCAP and call OpenRouter with.
        expediente: Which tender to analyze.

    Returns:
        The resulting `AnalysisStatus`, or `None` if there was nothing to analyze
        (the tender doesn't exist, or has no `pcap_url`).
    """
    tender = await session.get(Tender, expediente)
    if tender is None or tender.pcap_url is None:
        logger.warning("analyze_tender: %s has no pcap_url to analyze, skipping", expediente)
        return None

    # Downloaded once here just to compute the cache key. On a genuine cache
    # miss, analyze_pliego (3.6) downloads the same PCAP a second time inside
    # its own `fetch` node -- accepted duplication: the alternative is
    # threading a pre-fetched payload through the already-closed, tested
    # graph from 3.6, for a download that's cheap next to the LLM call it
    # gates.
    response = await client.get(tender.pcap_url)
    response.raise_for_status()
    pdf_hash = hash_document(response.content)

    existing = await get_analysis(session, pdf_hash)
    if existing is not None and existing.status in _SKIP_STATUSES:
        logger.info(
            "analyze_tender: %s already %s for pdf_hash %s, skipping",
            expediente,
            existing.status,
            pdf_hash,
        )
        return existing.status

    analysis = existing or await create_analysis(session, expediente=expediente, pdf_hash=pdf_hash)
    analysis.status = AnalysisStatus.IN_PROGRESS
    analysis.error_message = None
    await session.commit()

    settings = get_settings()
    result = await analyze_pliego(
        tender.pcap_url, api_key=settings.openrouter_api_key, client=client, model=EXTRACTION_MODEL
    )

    analysis.status = result["status"]
    extraction = result.get("extraction")
    analysis.extraction = extraction.model_dump(mode="json") if extraction is not None else None
    analysis.citation_faithfulness = result.get("citation_faithfulness")
    analysis.error_message = result.get("error_message")
    await session.commit()

    logger.info("analyze_tender: %s finished as %s", expediente, analysis.status)
    return analysis.status


@celery_app.task(name="analyze_tender")
def analyze_tender_task(expediente: str) -> str | None:
    """Celery entry point for an on-demand pliego analysis, guarded by a per-expediente
    Redis lock.

    Args:
        expediente: Which tender to analyze -- `pcap_url` and any prior analyses are
            looked up from this, nothing else is passed in.

    Returns:
        The resulting status's value, or `None` if this run was skipped (a
        concurrent run already in progress for this expediente, a missing tender, or
        a tender with no `pcap_url` to analyze).
    """
    lock = get_redis_client().lock(
        LOCK_KEY_TEMPLATE.format(expediente=expediente), timeout=LOCK_TIMEOUT_SECONDS
    )
    if not lock.acquire(blocking=False):
        # Two concurrent runs for the same expediente would both try to
        # create/update the same TenderAnalysis row -- e.g. a double click
        # on "analizar" -- so the second is skipped outright rather than
        # racing the first.
        logger.warning("analyze_tender: %s already in progress, skipping", expediente)
        return None

    try:
        try:
            if sys.platform == "win32":
                status = asyncio.run(_run(expediente), loop_factory=asyncio.SelectorEventLoop)
            else:
                status = asyncio.run(_run(expediente))
        except Exception:
            logger.exception("analyze_tender: %s failed", expediente)
            raise
        return status.value if status is not None else None
    finally:
        try:
            lock.release()
        except LockError:
            logger.warning("analyze_tender: %s lock already expired or released", expediente)
