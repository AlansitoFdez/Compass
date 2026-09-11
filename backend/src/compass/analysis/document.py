"""Downloads a pliego (PCAP) PDF, hashes it, and detects whether it has a real text layer.

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

# Hard ceiling on a PCAP download. A pliego with a real text layer -- the only kind this
# analyzes -- runs a few megabytes; PLACSP also publishes attachments with scanned plans
# that run into the hundreds. Both the task and the graph used to read `response.content`
# with no bound at all, and the worker runs with `--pool=solo`, so one oversized document
# taking the process down takes the daily ingestion with it, not just this analysis.
MAX_PCAP_BYTES = 50 * 1024 * 1024


class PcapTooLargeError(Exception):
    """The document exceeded `MAX_PCAP_BYTES` and was abandoned mid-download."""


async def download_pcap(
    url: str, client: httpx2.AsyncClient, *, max_bytes: int = MAX_PCAP_BYTES
) -> bytes:
    """Downloads a pliego, refusing to buffer more than `max_bytes` of it.

    Streamed and checked as it arrives rather than after the fact: a `Content-Length`
    header is advisory (PLACSP doesn't always send one, and a chunked response has none),
    so the only bound that actually holds is counting the bytes while reading them.

    Args:
        url: A tender's `pcap_url`.
        client: The async HTTP client to fetch with.
        max_bytes: Ceiling on the buffered document.

    Raises:
        PcapTooLargeError: The response exceeded `max_bytes`.
        httpx2.HTTPStatusError: The server answered with an error status.

    Returns:
        The raw PDF bytes.
    """
    chunks: list[bytes] = []
    size = 0
    async with client.stream("GET", url) as response:
        response.raise_for_status()
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > max_bytes:
                raise PcapTooLargeError(
                    f"el pliego supera el límite de {max_bytes // (1024 * 1024)} MB"
                )
            chunks.append(chunk)
    return b"".join(chunks)


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
