"""Tests for the 3.6 LangGraph orchestration -- fetch, detect, extract, verify wired
together as one graph. No real network calls: `httpx2.MockTransport` stands in for both
the PCAP download and the OpenRouter call, same pattern as `test_document.py`, plus a
canned SSE body for the streaming chat-completions endpoint.
"""

import json
from collections.abc import Callable
from pathlib import Path

import httpx2

from compass.analysis.document import hash_document
from compass.analysis.enums import AnalysisStatus
from compass.analysis.extraction_schema import PliegoExtraction
from compass.analysis.graph import analyze_pliego
from compass.analysis.openrouter import CHAT_COMPLETIONS_URL

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_PLIEGO = (FIXTURES_DIR / "sample_pliego.pdf").read_bytes()
SCANNED_DOCUMENT = (FIXTURES_DIR / "scanned_document.pdf").read_bytes()
PCAP_URL = "https://fake/pliego.pdf"

# One real, verifying citation (economic_solvency, re-flowing sample_pliego.pdf's own
# line-wrapped sentence -- the exact case 3.5 built `verify_citation` for) and one
# fabricated citation (lots) that doesn't appear in the fixture at all, so the happy
# path exercises `citation_faithfulness` as a real fraction (0.5), not a 1.0/0.0 that
# construction alone would already guarantee.
FIXTURE_EXTRACTION: dict[str, object] = {
    "economic_solvency": {
        "minimum_annual_turnover_eur": 100000.0,
        "description": "Cifra de negocio minima de 100000 euros",
        "citation": {
            "clause": "2",
            "page": 1,
            "quote": "cifra de negocio minima de 100000 euros en alguno de los tres",
        },
    },
    "technical_solvency": {"minimum_amount_eur": None, "description": "", "citation": None},
    "certifications": [],
    "certifications_citation": None,
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
        "citation": {"clause": "1", "page": 1, "quote": "texto que no existe en el pliego"},
    },
}


def _sse_body(content: dict[str, object] | None) -> bytes:
    """A canned OpenRouter streaming response -- one content chunk (unless `content`
    is `None`, which serves an empty completion, the transient failure `extract`'s
    `RetryPolicy` is meant to absorb) plus a usage chunk and `[DONE]`.
    """
    chunks: list[dict[str, object]] = []
    if content is not None:
        chunks.append({"choices": [{"delta": {"content": json.dumps(content)}}]})
    chunks.append(
        {
            "choices": [{"delta": {}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }
    )
    lines = [f"data: {json.dumps(c)}" for c in chunks] + ["data: [DONE]"]
    return ("\n\n".join(lines) + "\n\n").encode()


def _client(
    *,
    pcap_response: httpx2.Response,
    extract_handler: Callable[[httpx2.Request], httpx2.Response] | None,
) -> httpx2.AsyncClient:
    """A client whose transport routes the PCAP download and the OpenRouter call
    separately -- `extract_handler=None` asserts `extract` is never called at all,
    for the `NOT_ANALYZABLE` path.
    """

    def handler(request: httpx2.Request) -> httpx2.Response:
        if str(request.url) == PCAP_URL:
            return pcap_response
        if str(request.url) == CHAT_COMPLETIONS_URL:
            if extract_handler is None:
                raise AssertionError("extract must not be called on this path")
            return extract_handler(request)
        raise AssertionError(f"unexpected request to {request.url}")

    return httpx2.AsyncClient(transport=httpx2.MockTransport(handler))


async def test_analyze_pliego_completes_with_extraction_and_real_faithfulness_fraction() -> None:
    """Protects the full happy path: a real, real-text-bearing pliego and a valid
    model response end in `COMPLETED`, with `citation_faithfulness` computed against
    the actual fixture text (not hardcoded), landing on the real 0.5 mix.
    """
    client = _client(
        pcap_response=httpx2.Response(200, content=SAMPLE_PLIEGO),
        extract_handler=lambda _: httpx2.Response(200, content=_sse_body(FIXTURE_EXTRACTION)),
    )

    result = await analyze_pliego(PCAP_URL, api_key="fake-key", client=client)

    assert result["status"] == AnalysisStatus.COMPLETED
    assert result["pdf_hash"] == hash_document(SAMPLE_PLIEGO)
    assert result["extraction"] == PliegoExtraction.model_validate(FIXTURE_EXTRACTION)
    assert result["citation_faithfulness"] == 0.5


async def test_analyze_pliego_marks_a_scanned_document_not_analyzable_without_extracting() -> None:
    """Protects the point of the text-layer check: a scanned PCAP never reaches (and
    never pays for) the extraction call at all.
    """
    client = _client(
        pcap_response=httpx2.Response(200, content=SCANNED_DOCUMENT), extract_handler=None
    )

    result = await analyze_pliego(PCAP_URL, api_key="fake-key", client=client)

    assert result["status"] == AnalysisStatus.NOT_ANALYZABLE
    assert result.get("extraction") is None


async def test_analyze_pliego_returns_failed_instead_of_raising_on_a_dead_pcap_url() -> None:
    """Protects the graph's own error boundary: a 404 pcap_url becomes `FAILED` with
    a message, not an exception the caller has to catch.
    """
    client = _client(pcap_response=httpx2.Response(404), extract_handler=None)

    result = await analyze_pliego(PCAP_URL, api_key="fake-key", client=client)

    assert result["status"] == AnalysisStatus.FAILED
    assert result.get("error_message")


async def test_analyze_pliego_retries_once_then_fails_on_a_persistently_empty_completion() -> None:
    """Protects the `extract` node's `RetryPolicy`: an empty completion (the OpenRouter
    free tier's real observed failure mode, phase3.5.md) is retried exactly once
    (`max_attempts=2`) before the analysis gives up as `FAILED` -- never an
    unhandled `OpenRouterError` escaping to the caller.
    """
    call_count = 0

    def failing_extract(_: httpx2.Request) -> httpx2.Response:
        nonlocal call_count
        call_count += 1
        return httpx2.Response(200, content=_sse_body(None))

    client = _client(
        pcap_response=httpx2.Response(200, content=SAMPLE_PLIEGO), extract_handler=failing_extract
    )

    result = await analyze_pliego(PCAP_URL, api_key="fake-key", client=client)

    assert result["status"] == AnalysisStatus.FAILED
    assert result.get("error_message")
    assert call_count == 2
