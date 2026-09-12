"""Tests for `analyze_tender` (the real orchestration, real Postgres via `db_session`, no
real network) and `analyze_tender_task` (the Celery/lock wrapper, mocked orchestration) --
same split as `tests/ingestion/test_daily_ingestion_task.py` and `tests/matching/test_tasks.py`.
"""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import httpx2
import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from compass.analysis.document import PcapTooLargeError, hash_document
from compass.analysis.enums import AnalysisStatus
from compass.analysis.models import TenderAnalysis
from compass.analysis.openrouter import CHAT_COMPLETIONS_URL
from compass.analysis.repository import get_analysis_for_tender, get_or_create_analysis
from compass.analysis.tasks import LOCK_KEY_TEMPLATE, analyze_tender, analyze_tender_task
from compass.core.redis_client import get_redis_client
from compass.tenders.enums import ContractType, TenderStatus
from compass.tenders.models import Tender

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_PLIEGO = (FIXTURES_DIR / "sample_pliego.pdf").read_bytes()
SCANNED_DOCUMENT = (FIXTURES_DIR / "scanned_document.pdf").read_bytes()
SAMPLE_PLIEGO_HASH = hash_document(SAMPLE_PLIEGO)
PCAP_URL = "https://fake/pliego.pdf"

# A single valid extraction, reused by every test that needs the LLM call to
# actually succeed -- the extraction schema itself is already exhaustively
# covered by test_extraction_schema.py/test_verification.py; nothing here
# depends on its content beyond "it validates".
_VALID_EXTRACTION: dict[str, object] = {
    "economic_solvency": {
        "minimum_annual_turnover_eur": None,
        "description": "",
        "citation": None,
    },
    "technical_solvency": {"minimum_amount_eur": None, "description": "", "citation": None},
    "certifications": [],
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
    "execution_deadline": {
        "description": "",
        "extensions_allowed": None,
        "extensions_description": None,
        "citation": None,
    },
    "submission_deadline": {"description": "", "citation": None},
    "subcontracting": {"allowed": True, "description": "", "citation": None},
    "lots": {
        "divided_into_lots": False,
        "can_bid_partial_lots": None,
        "description": "",
        "citation": None,
    },
}


def _sse_body(content: dict[str, object]) -> bytes:
    """A canned OpenRouter streaming response with one content chunk, same shape as
    `test_graph.py`'s `_sse_body`.
    """
    chunk = {"choices": [{"delta": {"content": json.dumps(content)}}]}
    done = {
        "choices": [{"delta": {}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }
    lines = [f"data: {json.dumps(c)}" for c in (chunk, done)] + ["data: [DONE]"]
    return ("\n\n".join(lines) + "\n\n").encode()


def _client(
    *,
    pcap_content: bytes,
    extract_handler: Callable[[httpx2.Request], httpx2.Response] | None,
) -> httpx2.AsyncClient:
    """A client whose transport routes the PCAP download and the OpenRouter call
    separately -- `extract_handler=None` asserts extraction is never called at all,
    for the cache-hit and NOT_ANALYZABLE paths. Same pattern as `test_graph.py`.
    """

    def handler(request: httpx2.Request) -> httpx2.Response:
        if str(request.url) == PCAP_URL:
            return httpx2.Response(200, content=pcap_content)
        if str(request.url) == CHAT_COMPLETIONS_URL:
            if extract_handler is None:
                raise AssertionError("extraction must not be called on this path")
            return extract_handler(request)
        raise AssertionError(f"unexpected request to {request.url}")

    return httpx2.AsyncClient(transport=httpx2.MockTransport(handler))


def _tender(expediente: str, *, pcap_url: str | None = PCAP_URL) -> Tender:
    """A minimal valid `Tender` for the FK `TenderAnalysis.expediente` references."""
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
    """Deletes every row a test committed for real, by `expediente`.

    Unlike every other repository/task test in this project, `analyze_tender`
    commits internally (see its own docstring) -- so the usual "flush, then let
    `db_session` roll back at teardown" pattern doesn't apply to a test that
    actually reaches those commits. Same real-commit-then-clean-up shape as
    `test_tenders_endpoint.py`.
    """
    await session.execute(delete(TenderAnalysis).where(TenderAnalysis.expediente == expediente))
    await session.execute(delete(Tender).where(Tender.expediente == expediente))
    await session.commit()


async def test_analyze_tender_returns_none_when_the_tender_does_not_exist(
    db_session: AsyncSession,
) -> None:
    """Protects against analyzing a tender that was never ingested."""
    client = _client(pcap_content=b"", extract_handler=None)

    result = await analyze_tender(db_session, client, "TEST-TASK-MISSING")

    assert result is None


async def test_analyze_tender_returns_none_when_the_tender_has_no_pcap_url(
    db_session: AsyncSession,
) -> None:
    """Protects against enqueuing work with nothing to download -- no network call happens."""
    db_session.add(_tender("TEST-TASK-NO-PCAP", pcap_url=None))
    await db_session.flush()
    client = _client(pcap_content=b"", extract_handler=None)

    result = await analyze_tender(db_session, client, "TEST-TASK-NO-PCAP")

    assert result is None


async def test_analyze_tender_persists_a_completed_analysis_on_a_cache_miss(
    db_session: AsyncSession,
) -> None:
    """Protects the real, end-to-end path: a genuinely new document is fetched, extracted,
    and the full result -- status, extraction, citation_faithfulness -- lands in the row.
    """
    try:
        db_session.add(_tender("TEST-TASK-MISS"))
        await db_session.flush()
        client = _client(
            pcap_content=SAMPLE_PLIEGO,
            extract_handler=lambda _: httpx2.Response(200, content=_sse_body(_VALID_EXTRACTION)),
        )

        result = await analyze_tender(db_session, client, "TEST-TASK-MISS")

        assert result == AnalysisStatus.COMPLETED
        stored = await get_analysis_for_tender(db_session, "TEST-TASK-MISS")
        assert stored is not None
        assert stored.pdf_hash == SAMPLE_PLIEGO_HASH
        assert stored.status == AnalysisStatus.COMPLETED
        assert stored.extraction is not None
        assert stored.citation_faithfulness == 1.0
    finally:
        await _cleanup(db_session, "TEST-TASK-MISS")


async def test_analyze_tender_skips_the_llm_call_on_a_completed_cache_hit(
    db_session: AsyncSession,
) -> None:
    """Protects the whole point of caching by hash: a second run over the same document,
    for the same tender, costs one download and zero LLM calls.
    """
    db_session.add(_tender("TEST-TASK-HIT"))
    await db_session.flush()
    analysis = await get_or_create_analysis(db_session, expediente="TEST-TASK-HIT")
    analysis.pdf_hash = SAMPLE_PLIEGO_HASH
    analysis.status = AnalysisStatus.COMPLETED
    await db_session.flush()
    client = _client(pcap_content=SAMPLE_PLIEGO, extract_handler=None)

    result = await analyze_tender(db_session, client, "TEST-TASK-HIT")

    assert result == AnalysisStatus.COMPLETED


async def test_analyze_tender_skips_the_llm_call_for_a_cached_not_analyzable_document(
    db_session: AsyncSession,
) -> None:
    """Protects the other terminal cache state: a scanned document already marked
    `NOT_ANALYZABLE` is never re-attempted, same reasoning as `COMPLETED`.
    """
    scanned_hash = hash_document(SCANNED_DOCUMENT)
    db_session.add(_tender("TEST-TASK-SCANNED"))
    await db_session.flush()
    analysis = await get_or_create_analysis(db_session, expediente="TEST-TASK-SCANNED")
    analysis.pdf_hash = scanned_hash
    analysis.status = AnalysisStatus.NOT_ANALYZABLE
    await db_session.flush()
    client = _client(pcap_content=SCANNED_DOCUMENT, extract_handler=None)

    result = await analyze_tender(db_session, client, "TEST-TASK-SCANNED")

    assert result == AnalysisStatus.NOT_ANALYZABLE


async def test_analyze_tender_retries_a_previously_failed_analysis(
    db_session: AsyncSession,
) -> None:
    """Protects that `FAILED` isn't treated as a permanent answer, unlike `NOT_ANALYZABLE`
    -- a retry against the same hash gets a real extraction attempt, not skipped.
    """
    try:
        db_session.add(_tender("TEST-TASK-RETRY"))
        await db_session.flush()
        analysis = await get_or_create_analysis(db_session, expediente="TEST-TASK-RETRY")
        analysis.pdf_hash = SAMPLE_PLIEGO_HASH
        analysis.status = AnalysisStatus.FAILED
        analysis.error_message = "boom"
        await db_session.flush()
        client = _client(
            pcap_content=SAMPLE_PLIEGO,
            extract_handler=lambda _: httpx2.Response(200, content=_sse_body(_VALID_EXTRACTION)),
        )

        result = await analyze_tender(db_session, client, "TEST-TASK-RETRY")

        assert result == AnalysisStatus.COMPLETED
        stored = await get_analysis_for_tender(db_session, "TEST-TASK-RETRY")
        assert stored is not None
        assert stored.error_message is None
    finally:
        await _cleanup(db_session, "TEST-TASK-RETRY")


async def test_analyze_tender_copies_a_cached_extraction_onto_the_second_tenders_row(
    db_session: AsyncSession,
) -> None:
    """Protects the fix for the dead end two tenders sharing a PCAP used to hit.

    The cache still saves the LLM call -- `extract_handler=None` makes any attempt at one
    blow up -- but the result now lands on *this* tender's own row, so reading its analysis
    by expediente finds it. Before 5.2 the task returned the other tender's status and
    wrote nothing, leaving the dashboard on a permanent 404 and a button that did nothing.
    """
    try:
        db_session.add_all([_tender("TEST-TASK-SHARED-A"), _tender("TEST-TASK-SHARED-B")])
        await db_session.flush()
        done = await get_or_create_analysis(db_session, expediente="TEST-TASK-SHARED-A")
        done.pdf_hash = SAMPLE_PLIEGO_HASH
        done.status = AnalysisStatus.COMPLETED
        done.extraction = _VALID_EXTRACTION
        done.citation_faithfulness = 1.0
        await db_session.commit()
        client = _client(pcap_content=SAMPLE_PLIEGO, extract_handler=None)

        result = await analyze_tender(db_session, client, "TEST-TASK-SHARED-B")

        assert result == AnalysisStatus.COMPLETED
        stored = await get_analysis_for_tender(db_session, "TEST-TASK-SHARED-B")
        assert stored is not None
        assert stored.extraction == _VALID_EXTRACTION
        assert stored.citation_faithfulness == 1.0
    finally:
        await _cleanup(db_session, "TEST-TASK-SHARED-A")
        await _cleanup(db_session, "TEST-TASK-SHARED-B")


async def test_analyze_tender_records_a_pcap_over_the_download_cap(
    db_session: AsyncSession,
) -> None:
    """Protects the worker against an oversized document, and the user against silence.

    The download is abandoned instead of buffering the whole thing -- with `--pool=solo`
    an out-of-memory worker takes the daily ingestion down too -- and the reason is
    recorded as `NOT_ANALYZABLE` so the dashboard can say why rather than leaving the
    button looking broken.
    """
    try:
        db_session.add(_tender("TEST-TASK-HUGE"))
        await db_session.flush()
        client = _client(pcap_content=b"%PDF-" + b"x" * 4096, extract_handler=None)

        with patch("compass.analysis.tasks.download_pcap", side_effect=PcapTooLargeError("50 MB")):
            result = await analyze_tender(db_session, client, "TEST-TASK-HUGE")

        assert result == AnalysisStatus.NOT_ANALYZABLE
        stored = await get_analysis_for_tender(db_session, "TEST-TASK-HUGE")
        assert stored is not None
        assert stored.pdf_hash is None
        assert "50 MB" in (stored.error_message or "")
    finally:
        await _cleanup(db_session, "TEST-TASK-HUGE")


async def test_analyze_tender_downloads_the_pliego_only_once(
    db_session: AsyncSession,
) -> None:
    """Protects against the duplicate download: the task needs the bytes to compute the
    cache key, and the graph used to fetch the very same file again for itself -- twice the
    traffic and twice the memory, with a window where the two could disagree.
    """
    try:
        db_session.add(_tender("TEST-TASK-ONEFETCH"))
        await db_session.flush()
        downloads = 0

        def handler(request: httpx2.Request) -> httpx2.Response:
            """Counts PCAP fetches; serves the extraction for the OpenRouter call."""
            nonlocal downloads
            if request.url.host != "openrouter.ai":
                downloads += 1
                return httpx2.Response(200, content=SAMPLE_PLIEGO)
            return httpx2.Response(200, content=_sse_body(_VALID_EXTRACTION))

        client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))

        result = await analyze_tender(db_session, client, "TEST-TASK-ONEFETCH")

        assert result == AnalysisStatus.COMPLETED
        assert downloads == 1
    finally:
        await _cleanup(db_session, "TEST-TASK-ONEFETCH")


def _lock_key(expediente: str) -> str:
    return LOCK_KEY_TEMPLATE.format(expediente=expediente)


def test_analyze_tender_task_runs_end_to_end_with_mocked_orchestration() -> None:
    """Protects the end-to-end wiring: the real lock and event-loop plumbing, mocked
    orchestration. The task must return whatever `analyze_tender` reports.
    """
    expediente = "TEST-CELERY-OK"
    get_redis_client().delete(_lock_key(expediente))

    async def fake_analyze_tender(
        session: object, client: object, expediente: str
    ) -> AnalysisStatus:
        return AnalysisStatus.COMPLETED

    with patch("compass.analysis.tasks.analyze_tender", side_effect=fake_analyze_tender):
        result = analyze_tender_task(expediente)

    assert result == "completed"


def test_analyze_tender_task_returns_none_when_orchestration_finds_nothing_to_analyze() -> None:
    """Protects the "no pcap_url / unknown tender" case surfacing as `None`, not a fake status."""
    expediente = "TEST-CELERY-NOTHING"
    get_redis_client().delete(_lock_key(expediente))

    async def fake_analyze_tender(session: object, client: object, expediente: str) -> None:
        return None

    with patch("compass.analysis.tasks.analyze_tender", side_effect=fake_analyze_tender):
        result = analyze_tender_task(expediente)

    assert result is None


def test_analyze_tender_task_skips_when_a_run_for_the_same_expediente_holds_the_lock() -> None:
    """Protects against a double click on "analizar" racing two runs for the same tender."""
    expediente = "TEST-CELERY-LOCKED"
    held_by_another_run = get_redis_client().lock(_lock_key(expediente), timeout=60)
    assert held_by_another_run.acquire(blocking=False)

    try:
        with patch("compass.analysis.tasks.analyze_tender") as mocked:
            result = analyze_tender_task(expediente)

        assert result is None
        mocked.assert_not_called()
    finally:
        held_by_another_run.release()


def test_analyze_tender_task_releases_the_lock_after_a_successful_run() -> None:
    """Protects against a successful run leaving the lock held, blocking every future retry."""
    expediente = "TEST-CELERY-RELEASE-OK"
    get_redis_client().delete(_lock_key(expediente))

    async def fake_analyze_tender(
        session: object, client: object, expediente: str
    ) -> AnalysisStatus:
        return AnalysisStatus.COMPLETED

    with patch("compass.analysis.tasks.analyze_tender", side_effect=fake_analyze_tender):
        analyze_tender_task(expediente)

    lock = get_redis_client().lock(_lock_key(expediente), timeout=60)
    assert lock.acquire(blocking=False)
    lock.release()


def test_analyze_tender_task_releases_the_lock_even_if_the_run_fails() -> None:
    """Protects the `finally: lock.release()` path -- a crash must not leave the lock stuck."""
    expediente = "TEST-CELERY-RELEASE-FAIL"
    get_redis_client().delete(_lock_key(expediente))

    async def failing_analyze_tender(session: object, client: object, expediente: str) -> None:
        raise RuntimeError("boom")

    with (
        patch("compass.analysis.tasks.analyze_tender", side_effect=failing_analyze_tender),
        pytest.raises(RuntimeError),
    ):
        analyze_tender_task(expediente)

    lock = get_redis_client().lock(_lock_key(expediente), timeout=60)
    assert lock.acquire(blocking=False)
    lock.release()
