"""Tests for the 3.6 LangGraph orchestration -- fetch, detect, extract, verify wired
together as one graph. No real network calls: `httpx2.MockTransport` stands in for both
the PCAP download and the OpenRouter call, same pattern as `test_document.py`, plus a
canned SSE body for the streaming chat-completions endpoint.
"""

import asyncio
import json
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import cast

import httpx2
import pytest

from compass.analysis import graph
from compass.analysis.document import hash_document
from compass.analysis.enums import AnalysisStatus
from compass.analysis.extraction_schema import PliegoExtraction
from compass.analysis.graph import analyze_pliego, build_prompt
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


_ExtractResponse = httpx2.Response | Coroutine[None, None, httpx2.Response]


def _client(
    *,
    pcap_response: httpx2.Response,
    extract_handler: Callable[[httpx2.Request], _ExtractResponse] | None,
) -> httpx2.AsyncClient:
    """A client whose transport routes the PCAP download and the OpenRouter call
    separately -- `extract_handler=None` asserts `extract` is never called at all,
    for the `NOT_ANALYZABLE` path. `extract_handler` may be an `async def` (as
    `httpx2.MockTransport` allows) when a test needs to actually yield to the event
    loop, e.g. to simulate a stalled call.
    """

    def handler(request: httpx2.Request) -> _ExtractResponse:
        if str(request.url) == PCAP_URL:
            return pcap_response
        if str(request.url) == CHAT_COMPLETIONS_URL:
            if extract_handler is None:
                raise AssertionError("extract must not be called on this path")
            return extract_handler(request)
        raise AssertionError(f"unexpected request to {request.url}")

    # MockTransport's own runtime (`handle_async_request`) accepts a handler that
    # returns either a Response or an awaitable of one, per call -- its type stub
    # only declares one fixed return type per handler value, not this per-call
    # union, so this narrows back to satisfy it.
    return httpx2.AsyncClient(
        transport=httpx2.MockTransport(cast(Callable[[httpx2.Request], httpx2.Response], handler))
    )


def test_build_prompt_wraps_the_untrusted_pcap_text_in_delimiters() -> None:
    """Protects the 4.5 prompt-injection boundary: the PDF text (a third party's
    document, never fully trusted) is wrapped in <PLIEGO>/</PLIEGO> so `SYSTEM_PROMPT`
    has something concrete to tell the model to treat as inert data.
    """
    prompt = build_prompt(["texto de la página uno", "texto de la página dos"])

    assert prompt.startswith("<PLIEGO>\n")
    assert prompt.endswith("\n</PLIEGO>")
    assert "texto de la página uno" in prompt
    assert "texto de la página dos" in prompt


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


async def test_analyze_pliego_fails_when_the_extraction_call_stalls_past_the_wall_clock_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Protects the 3.9 wall-clock cap: a call that keeps streaming past
    `_EXTRACT_TOTAL_TIMEOUT_SECONDS` is cut off and reported as `FAILED`, instead of
    running unbounded -- the real risk phase3.5.md's >10-minute nemotron call exposed,
    since httpx2's own per-chunk timeout never trips as long as data keeps trickling in.
    Also protects that a stall isn't retried: `_EXTRACT_RETRY_POLICY.retry_on` deliberately
    excludes it, so doubling the wait within the same task run doesn't happen.
    """
    monkeypatch.setattr(graph, "_EXTRACT_TOTAL_TIMEOUT_SECONDS", 0.05)
    call_count = 0

    async def stalling_extract(_: httpx2.Request) -> httpx2.Response:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.2)
        return httpx2.Response(200, content=_sse_body(FIXTURE_EXTRACTION))

    client = _client(
        pcap_response=httpx2.Response(200, content=SAMPLE_PLIEGO), extract_handler=stalling_extract
    )

    result = await analyze_pliego(PCAP_URL, api_key="fake-key", client=client)

    assert result["status"] == AnalysisStatus.FAILED
    error_message = result.get("error_message")
    assert error_message is not None
    assert "wall-clock cap" in error_message
    assert call_count == 1
