"""Tests for POST/GET /tenders/{expediente}/analyze|analysis over the real ASGI app --
wiring, status codes, and the live verdict computation. `analyze_tender_task.delay` is
mocked (no real worker in tests, same reasoning `test_matches_endpoint.py` gives for
mocking `get_provider`); orchestration itself is already covered end to end in
`test_analysis_tasks.py`.

Real commits, not the usual flush()+rollback `db_session` pattern -- same reasoning as
`test_tenders_endpoint.py`'s own module docstring: the real ASGI app's `get_db()`
dependency runs on a different event loop than pytest-asyncio's, so only a real commit
is guaranteed visible to it.
"""

from datetime import UTC, datetime
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from compass.analysis.enums import AnalysisStatus
from compass.analysis.models import TenderAnalysis
from compass.tenders.enums import ContractType, TenderStatus
from compass.tenders.models import Tender

TEST_HASH = "e" * 64

# The shape a real PLACSP expediente actually has -- slashes, a space and an accent all
# at once (`2026/S-ABT/0000025771 - Gestión de expedientes` is a live one). The tests
# below run every route against this, not only against a slash-free identifier: until
# 5.2 the analysis routes matched a single path segment, so none of them reached this
# endpoint at all for the 2.282 of 3.583 corpus expedientes that carry a slash, and a
# suite written only around `TEST-EP-...` names had no way to notice.
REAL_SHAPED_EXPEDIENTE = "TEST/EP/2026/0001 - Análisis con barras"

# A minimal, syntactically valid extraction requiring the one certification the
# real seeded provider actually declares (see `mcp__postgres__execute_sql`
# check during planning: `certifications: ['ENS', 'ISO 27001']`) and no
# quantified solvency -- deliberately the simplest case that resolves to APTO,
# so the test protects "the endpoint wires extraction + provider into a real
# verdict", not the comparison logic itself (already exhaustive in test_verdict.py).
_APTO_EXTRACTION: dict[str, object] = {
    "economic_solvency": {"minimum_annual_turnover_eur": None, "description": "", "citation": None},
    "technical_solvency": {"minimum_amount_eur": None, "description": "", "citation": None},
    "certifications": ["ISO 27001"],
    "certifications_citation": {"clause": "9", "page": 2, "quote": "Se exige ISO 27001"},
    "award_criteria": {
        "total_points": 100,
        "criteria": [{"name": "Precio", "points": 60, "is_price": True}],
        "citation": None,
    },
    "guarantees": {
        "provisional_required": False,
        "definitive_percentage": None,
        "description": "",
        "citation": None,
    },
    "execution_deadline": {"description": "", "citation": None},
    "submission_deadline": {"description": "", "citation": None},
    "subcontracting": {"allowed": True, "description": "", "citation": None},
    "lots": {
        "divided_into_lots": False,
        "can_bid_partial_lots": None,
        "description": "",
        "citation": None,
    },
}


def _tender(expediente: str, *, pcap_url: str | None) -> Tender:
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
        pcap_url=pcap_url,
    )


async def _cleanup(session: AsyncSession, expediente: str) -> None:
    await session.execute(delete(TenderAnalysis).where(TenderAnalysis.expediente == expediente))
    await session.execute(delete(Tender).where(Tender.expediente == expediente))
    await session.commit()


async def test_post_analyze_returns_404_for_an_unknown_tender(client: TestClient) -> None:
    """Protects against enqueuing work for a tender that was never ingested."""
    response = client.post("/tenders/TEST-EP-ANALYZE-MISSING/analyze")

    assert response.status_code == 404


async def test_post_analyze_returns_422_when_the_tender_has_no_pcap_url(
    db_session: AsyncSession, client: TestClient
) -> None:
    """Protects against enqueuing work with nothing to download -- fails fast, no task
    reaches Celery at all.
    """
    expediente = "TEST-EP-ANALYZE-NO-PCAP"
    try:
        db_session.add(_tender(expediente, pcap_url=None))
        await db_session.commit()

        with patch("compass.api.routes.analysis.analyze_tender_task") as mocked_task:
            response = client.post(f"/tenders/{expediente}/analyze")

        assert response.status_code == 422
        mocked_task.delay.assert_not_called()
    finally:
        await _cleanup(db_session, expediente)


async def test_post_analyze_enqueues_the_task_and_returns_202(
    db_session: AsyncSession, client: TestClient
) -> None:
    """Protects the actual wiring: a valid tender enqueues `analyze_tender_task` with its
    own `expediente`, and the caller gets back an immediate acknowledgement.
    """
    expediente = "TEST-EP-ANALYZE-OK"
    try:
        db_session.add(_tender(expediente, pcap_url="https://fake/pliego.pdf"))
        await db_session.commit()

        with patch("compass.api.routes.analysis.analyze_tender_task") as mocked_task:
            response = client.post(f"/tenders/{expediente}/analyze")

        assert response.status_code == 202
        mocked_task.delay.assert_called_once_with(expediente)
    finally:
        await _cleanup(db_session, expediente)


async def test_post_analyze_reaches_the_analysis_route_for_a_real_shaped_expediente(
    db_session: AsyncSession, client: TestClient
) -> None:
    """Protects the routing itself, not the handler: with the expediente declared as a
    single path segment this POST never reached `trigger_analysis` at all and came back
    405, because `GET /tenders/{expediente:path}` was the only route that matched.
    """
    try:
        db_session.add(_tender(REAL_SHAPED_EXPEDIENTE, pcap_url="https://fake/pliego.pdf"))
        await db_session.commit()

        with patch("compass.api.routes.analysis.analyze_tender_task") as mocked_task:
            response = client.post(f"/tenders/{REAL_SHAPED_EXPEDIENTE}/analyze")

        assert response.status_code == 202
        # The expediente survives the round trip through the URL intact -- the slashes
        # stay separators, the space and the accent come back decoded.
        mocked_task.delay.assert_called_once_with(REAL_SHAPED_EXPEDIENTE)
    finally:
        await _cleanup(db_session, REAL_SHAPED_EXPEDIENTE)


async def test_get_analysis_reaches_the_analysis_route_for_a_real_shaped_expediente(
    db_session: AsyncSession, client: TestClient
) -> None:
    """The read half of the same protection: this used to be answered by the tender detail
    route with "Tender not found", which the dashboard renders as "never analyzed" -- an
    existing analysis was invisible on two thirds of the corpus.
    """
    try:
        db_session.add(_tender(REAL_SHAPED_EXPEDIENTE, pcap_url="https://fake/pliego.pdf"))
        await db_session.flush()
        db_session.add(
            TenderAnalysis(
                pdf_hash=TEST_HASH,
                expediente=REAL_SHAPED_EXPEDIENTE,
                status=AnalysisStatus.PENDING,
            )
        )
        await db_session.commit()

        response = client.get(f"/tenders/{REAL_SHAPED_EXPEDIENTE}/analysis")

        assert response.status_code == 200
        assert response.json()["expediente"] == REAL_SHAPED_EXPEDIENTE
    finally:
        await _cleanup(db_session, REAL_SHAPED_EXPEDIENTE)


async def test_get_analysis_returns_404_when_never_analyzed(client: TestClient) -> None:
    """Protects the "nothing to show yet" case: never analyzed reads as 404, not an
    empty/null body.
    """
    response = client.get("/tenders/TEST-EP-ANALYSIS-MISSING/analysis")

    assert response.status_code == 404


async def test_get_analysis_returns_a_pending_analysis_with_no_verdict(
    db_session: AsyncSession, client: TestClient
) -> None:
    """Protects that a verdict is never fabricated before there's an extraction to compute
    it from -- `verdict` stays `None` for any non-`COMPLETED` status.
    """
    expediente = "TEST-EP-ANALYSIS-PENDING"
    try:
        db_session.add(_tender(expediente, pcap_url="https://fake/pliego.pdf"))
        await db_session.flush()
        db_session.add(
            TenderAnalysis(pdf_hash=TEST_HASH, expediente=expediente, status=AnalysisStatus.PENDING)
        )
        await db_session.commit()

        response = client.get(f"/tenders/{expediente}/analysis")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "pending"
        assert body["verdict"] is None
    finally:
        await _cleanup(db_session, expediente)


async def test_get_analysis_computes_the_live_verdict_for_a_completed_analysis(
    db_session: AsyncSession, client: TestClient
) -> None:
    """Protects the point of the whole endpoint: a `COMPLETED` analysis is read back with
    a real verdict, computed against the real seeded provider profile -- not stored, not
    fabricated by the endpoint itself.
    """
    expediente = "TEST-EP-ANALYSIS-COMPLETED"
    try:
        db_session.add(_tender(expediente, pcap_url="https://fake/pliego.pdf"))
        await db_session.flush()
        db_session.add(
            TenderAnalysis(
                pdf_hash=TEST_HASH,
                expediente=expediente,
                status=AnalysisStatus.COMPLETED,
                extraction=_APTO_EXTRACTION,
                citation_faithfulness=1.0,
            )
        )
        await db_session.commit()

        response = client.get(f"/tenders/{expediente}/analysis")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "completed"
        assert body["extraction"]["certifications"] == ["ISO 27001"]
        assert body["verdict"]["verdict"] == "apto"
        assert body["verdict"]["reasons"] == []
    finally:
        await _cleanup(db_session, expediente)


async def test_get_analysis_returns_404_when_completed_but_no_provider_is_seeded(
    db_session: AsyncSession, client: TestClient
) -> None:
    """Protects the one other 404 this endpoint can produce: a verdict needs a provider
    profile to compare against, same condition `GET /matches` reports the same way.
    """
    expediente = "TEST-EP-ANALYSIS-NO-PROVIDER"
    try:
        db_session.add(_tender(expediente, pcap_url="https://fake/pliego.pdf"))
        await db_session.flush()
        db_session.add(
            TenderAnalysis(
                pdf_hash=TEST_HASH,
                expediente=expediente,
                status=AnalysisStatus.COMPLETED,
                extraction=_APTO_EXTRACTION,
                citation_faithfulness=1.0,
            )
        )
        await db_session.commit()

        with patch("compass.api.routes.analysis.get_provider", return_value=None):
            response = client.get(f"/tenders/{expediente}/analysis")

        assert response.status_code == 404
    finally:
        await _cleanup(db_session, expediente)
