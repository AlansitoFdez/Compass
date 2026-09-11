"""Tests for download_pcap/hash_document/extract_pages/has_text_layer -- real fixture PDFs,
no OCR/mocking of the PDF parsing itself; only the HTTP fetch is mocked (no real network calls).
"""

import asyncio
from pathlib import Path

import httpx2
import pytest

from compass.analysis.document import (
    MAX_PCAP_BYTES,
    PcapTooLargeError,
    download_pcap,
    extract_pages,
    has_text_layer,
    hash_document,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_PLIEGO = (FIXTURES_DIR / "sample_pliego.pdf").read_bytes()
SCANNED_DOCUMENT = (FIXTURES_DIR / "scanned_document.pdf").read_bytes()


def test_hash_document_is_deterministic() -> None:
    """Protects the cache key's core property: the same bytes always hash the same way."""
    assert hash_document(SAMPLE_PLIEGO) == hash_document(SAMPLE_PLIEGO)


def test_hash_document_differs_for_different_content() -> None:
    """Protects against a hash collision between two real, different fixtures."""
    assert hash_document(SAMPLE_PLIEGO) != hash_document(SCANNED_DOCUMENT)


def test_extract_pages_returns_one_string_per_page() -> None:
    """Protects the per-page shape: `sample_pliego.pdf` has 2 real pages of clause text."""
    pages = extract_pages(SAMPLE_PLIEGO)

    assert len(pages) == 2
    assert "Clausula 1" in pages[0]
    assert "Clausula 3" in pages[1]


def test_has_text_layer_is_true_for_a_real_text_document() -> None:
    """Protects the core positive case against a real (hand-built, not mocked) text-bearing PDF."""
    pages = extract_pages(SAMPLE_PLIEGO)

    assert has_text_layer(pages) is True


def test_has_text_layer_is_false_for_a_scanned_document() -> None:
    """Protects the case this exists for: a PDF with no text layer at all must be detected,
    not silently treated as analyzable.
    """
    pages = extract_pages(SCANNED_DOCUMENT)

    assert has_text_layer(pages) is False


def test_has_text_layer_is_false_for_an_empty_page_list() -> None:
    """Protects a degenerate edge: a zero-page document isn't analyzable either."""
    assert has_text_layer([]) is False


def test_download_pcap_returns_the_whole_document() -> None:
    """Protects the happy path of the streamed download: the bytes come back identical to
    what the server sent, chunking included.
    """

    def handler(request: httpx2.Request) -> httpx2.Response:
        """Serves the fixture pliego for any request."""
        return httpx2.Response(200, content=SAMPLE_PLIEGO)

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))

    async def run() -> bytes:
        async with client:
            return await download_pcap("https://fake/pliego.pdf", client)

    assert asyncio.run(run()) == SAMPLE_PLIEGO


def test_download_pcap_refuses_a_document_over_the_cap() -> None:
    """Protects the worker's memory: both callers used to read the whole response with no
    bound, and `--pool=solo` means one oversized PCAP takes down the daily ingestion too,
    not just this analysis.
    """

    def handler(request: httpx2.Request) -> httpx2.Response:
        """Serves more bytes than the caller allows."""
        return httpx2.Response(200, content=b"x" * 2048)

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))

    async def run() -> bytes:
        async with client:
            return await download_pcap("https://fake/huge.pdf", client, max_bytes=1024)

    with pytest.raises(PcapTooLargeError):
        asyncio.run(run())


def test_download_pcap_raises_on_http_error() -> None:
    """Protects against a 404/5xx (a stale or dead pcap_url) being silently treated as an
    empty document instead of raising.
    """

    def handler(request: httpx2.Request) -> httpx2.Response:
        """Serves a 404 for any request, standing in for a dead pcap_url."""
        return httpx2.Response(404)

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))

    async def run() -> bytes:
        async with client:
            return await download_pcap("https://fake/missing.pdf", client)

    with pytest.raises(httpx2.HTTPStatusError):
        asyncio.run(run())


def test_the_cap_is_generous_for_a_real_text_pliego() -> None:
    """Protects against the ceiling being tightened to where it would reject the documents
    this is supposed to analyze -- a PCAP with a text layer is megabytes, not tens of them.
    """
    assert MAX_PCAP_BYTES >= 20 * 1024 * 1024
