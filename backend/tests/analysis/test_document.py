"""Tests for fetch_pcap/hash_document/extract_pages/has_text_layer -- real fixture PDFs,
no OCR/mocking of the PDF parsing itself; only the HTTP fetch is mocked (no real network calls).
"""

from pathlib import Path

import httpx2
import pytest

from compass.analysis.document import extract_pages, fetch_pcap, has_text_layer, hash_document

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


def test_fetch_pcap_uses_mocked_transport() -> None:
    """Protects that `fetch_pcap` requests the given URL and returns the raw bytes."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        """Confirms the requested URL, then serves the real sample fixture's bytes."""
        assert str(request.url) == "https://fake/pliego.pdf"
        return httpx2.Response(200, content=SAMPLE_PLIEGO)

    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    content = fetch_pcap("https://fake/pliego.pdf", client)

    assert content == SAMPLE_PLIEGO


def test_fetch_pcap_raises_on_http_error() -> None:
    """Protects against a 404/5xx (a stale or dead pcap_url) being silently treated as an
    empty document instead of raising.
    """

    def handler(request: httpx2.Request) -> httpx2.Response:
        """Serves a 404 for any request, standing in for a dead pcap_url."""
        return httpx2.Response(404)

    client = httpx2.Client(transport=httpx2.MockTransport(handler))

    with pytest.raises(httpx2.HTTPStatusError):
        fetch_pcap("https://fake/missing.pdf", client)
