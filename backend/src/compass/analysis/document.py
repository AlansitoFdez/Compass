"""Fetches a pliego (PCAP) PDF, hashes it, and detects whether it has a real text layer.

Pure, testable steps -- no orchestration here. Wiring these into an actual
analysis (deciding what to do with a `NOT_ANALYZABLE` document, persisting
the result) is Phase 3.8's job.
"""

import hashlib
import io

import httpx2
import pdfplumber

# Real PCAPs run dozens of pages of dense clause text -- thousands of
# characters per page. A scanned page with no text layer extracts to (close
# to) nothing. This threshold only has to separate those two cases, not
# measure extraction quality, so it stays deliberately low: v1 does no OCR
# and isn't trying to -- it only needs to tell "readable" from "not".
MIN_CHARS_PER_PAGE = 20


def fetch_pcap(url: str, client: httpx2.Client) -> bytes:
    """Downloads the pliego PDF from `url`.

    Args:
        url: A tender's `pcap_url`.
        client: The HTTP client to fetch with.

    Returns:
        The raw PDF bytes.
    """
    response = client.get(url)
    response.raise_for_status()
    return response.content


def hash_document(content: bytes) -> str:
    """The document's own content hash -- the cache key `TenderAnalysis.pdf_hash` uses.

    sha256, not a weaker/faster hash: this is a cache key computed once per
    analysis, not a hot path, so collision resistance matters more than speed.
    """
    return hashlib.sha256(content).hexdigest()


def extract_pages(content: bytes) -> list[str]:
    """The text of each page, in order -- empty string for a page with nothing extractable.

    Args:
        content: Raw PDF bytes.

    Returns:
        One string per page.
    """
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        return [page.extract_text() or "" for page in pdf.pages]


def has_text_layer(pages: list[str]) -> bool:
    """Whether `pages` looks like a real text-bearing document, not a scan with no text layer.

    Args:
        pages: Per-page extracted text, from `extract_pages`.

    Returns:
        `False` for an empty document or one averaging under
        `MIN_CHARS_PER_PAGE` non-whitespace characters per page -- the
        signal a future orchestrator (Phase 3.8) uses to mark a
        `TenderAnalysis` `NOT_ANALYZABLE` instead of attempting extraction.
    """
    if not pages:
        return False
    total_chars = sum(len("".join(page.split())) for page in pages)
    return (total_chars / len(pages)) >= MIN_CHARS_PER_PAGE
