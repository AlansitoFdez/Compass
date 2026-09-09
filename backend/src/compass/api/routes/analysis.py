"""POST/GET /tenders/{expediente}/analyze|analysis — trigger and read a pliego analysis.

Bajo demanda only, mirroring `analysis.tasks.analyze_tender_task` itself: there is no
"analyze everything" endpoint, only "analyze this one tender someone is actually
looking at" (see docs/phases/phase3/phase3.md).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from compass.analysis.enums import AnalysisStatus
from compass.analysis.extraction_schema import PliegoExtraction
from compass.analysis.repository import get_latest_analysis_for_tender
from compass.analysis.schemas import TenderAnalysisResultSchema
from compass.analysis.tasks import analyze_tender_task
from compass.analysis.verdict import compute_verdict
from compass.core.db import get_db
from compass.providers.repository import get_provider
from compass.tenders.models import Tender

router = APIRouter(prefix="/tenders/{expediente}", tags=["analysis"])


@router.post("/analyze", status_code=202)
async def trigger_analysis(
    expediente: str, session: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    """Enqueues an analysis for this tender's current `pcap_url`.

    Fails fast, synchronously, on what's already knowable without a worker: a
    missing tender or one with no PCAP to analyze. Everything past that --
    whether this exact document is already cached, already in progress, or
    genuinely new -- is `analyze_tender_task`'s own decision (`analysis/tasks.py`),
    not duplicated here.

    Raises:
        HTTPException: 404 if `expediente` doesn't exist; 422 if it has no
            `pcap_url` to analyze.

    Returns:
        A plain acknowledgement -- there is no result backend (see
        `core/celery_app.py`), so `GET /tenders/{expediente}/analysis` is the only
        way to observe the outcome, by polling.
    """
    tender = await session.get(Tender, expediente)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found")
    if tender.pcap_url is None:
        raise HTTPException(status_code=422, detail="Tender has no pcap_url to analyze")

    analyze_tender_task.delay(expediente)
    return {"detail": f"Analysis queued for {expediente}"}


@router.get("/analysis")
async def get_analysis_result(
    expediente: str, session: AsyncSession = Depends(get_db)
) -> TenderAnalysisResultSchema:
    """The most recent analysis for this tender, with the verdict computed live.

    The verdict is never stored (see `models.TenderAnalysis`): it's recomputed here,
    every call, from `extraction` against whichever `Provider` is current -- so an
    edit to the provider profile changes the verdict on the next read, with nothing
    to invalidate.

    Raises:
        HTTPException: 404 if this tender has never been analyzed; 404 if `status`
            is `COMPLETED` but no provider profile is seeded yet (same condition
            `GET /matches` reports the same way).

    Returns:
        The analysis's status, extraction, citation faithfulness, and (once
        `COMPLETED`) its verdict.
    """
    analysis = await get_latest_analysis_for_tender(session, expediente)
    if analysis is None:
        raise HTTPException(status_code=404, detail="This tender has not been analyzed yet")

    extraction = (
        PliegoExtraction.model_validate(analysis.extraction)
        if analysis.extraction is not None
        else None
    )

    verdict = None
    if analysis.status == AnalysisStatus.COMPLETED and extraction is not None:
        provider = await get_provider(session)
        if provider is None:
            raise HTTPException(status_code=404, detail="Provider profile not seeded yet")
        verdict = compute_verdict(extraction, provider)

    return TenderAnalysisResultSchema(
        expediente=analysis.expediente,
        status=analysis.status,
        extraction=extraction,
        citation_faithfulness=analysis.citation_faithfulness,
        error_message=analysis.error_message,
        verdict=verdict,
    )
