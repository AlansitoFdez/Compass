"""Integration tests for ingest_atom_feed — mocked HTTP pages + real Redis checkpoint."""

from collections.abc import Iterator
from unittest.mock import patch

import httpx2
import pytest

from compass.ingestion.checkpoint import (
    clear_high_water_mark,
    clear_pending_high_water_mark,
    clear_resume_url,
    complete_run,
    get_pending_high_water_mark,
    get_resume_url,
    set_pending_high_water_mark,
    set_resume_url,
)
from compass.ingestion.feed_reader import ingest_atom_feed

# atom:updated strictly descending across and within pages -- the real order
# confirmed against the live feed during the 1.11 investigation.
PAGE_1 = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry><id>1</id><updated>2026-08-19T12:00:00+02:00</updated></entry>
  <entry><id>2</id><updated>2026-08-19T11:00:00+02:00</updated></entry>
  <link rel="next" href="https://fake/page-2.atom"/>
</feed>
"""

PAGE_2 = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry><id>3</id><updated>2026-08-19T10:00:00+02:00</updated></entry>
</feed>
"""

PAGES = {
    "https://fake/page-1.atom": PAGE_1,
    "https://fake/page-2.atom": PAGE_2,
}


@pytest.fixture(autouse=True)
def _clean_checkpoint() -> Iterator[None]:
    """Wipes every checkpoint key before and after each test.

    So tests can't see each other's leftover state.
    """
    clear_resume_url()
    clear_high_water_mark()
    clear_pending_high_water_mark()
    yield
    clear_resume_url()
    clear_high_water_mark()
    clear_pending_high_water_mark()


def _mocked_client(requested: list[str] | None = None) -> httpx2.Client:
    """A client serving `PAGES` from memory; `requested` records every URL asked for, if given."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        """Serves the requested page from `PAGES`, recording the URL if `requested` was given."""
        if requested is not None:
            requested.append(str(request.url))
        return httpx2.Response(200, content=PAGES[str(request.url)])

    return httpx2.Client(transport=httpx2.MockTransport(handler))


def test_ingest_atom_feed_yields_all_entries_on_a_fresh_start() -> None:
    """Protects a cold start: every entry across every page is yielded, in order."""
    with patch("compass.ingestion.feed_reader.FEED_URL", "https://fake/page-1.atom"):
        entries = list(ingest_atom_feed(_mocked_client()))

    assert len(entries) == 3
    # The newest entry across the whole run (entry 1) is left pending, not yet
    # promoted to the real high-water mark -- that's complete_run()'s job.
    assert get_pending_high_water_mark() == "2026-08-19T12:00:00+02:00"


def test_ingest_atom_feed_resumes_from_an_existing_checkpoint() -> None:
    """Protects resuming from `resume_url` instead of walking from `FEED_URL` again."""
    set_resume_url("https://fake/page-2.atom")

    entries = list(ingest_atom_feed(_mocked_client()))

    assert len(entries) == 1
    # Resuming (not a fresh start) must not set a pending mark -- that would
    # lose track of the real newest entry, seen before the earlier cutoff.
    assert get_pending_high_water_mark() is None


def test_checkpoint_reflects_completed_page_even_if_the_next_fetch_then_fails() -> None:
    """Protects that `resume_url` advances per page consumed, even if a later page's fetch fails."""
    set_resume_url("https://fake/page-1.atom")

    def handler(request: httpx2.Request) -> httpx2.Response:
        """Serves page 1 normally, then a 500 for any further request (page 2)."""
        if str(request.url) == "https://fake/page-1.atom":
            return httpx2.Response(200, content=PAGE_1)
        return httpx2.Response(500)

    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    generator = ingest_atom_feed(client)

    next(generator)
    next(generator)

    with pytest.raises(httpx2.HTTPStatusError):
        next(generator)

    assert get_resume_url() == "https://fake/page-2.atom"


def test_ingest_atom_feed_stops_at_the_high_water_mark_without_walking_further() -> None:
    """Set up a high-water mark equal to entry 2's timestamp (from a
    previously completed run) — only entry 1 (newer) should come back, and
    page 2 must never even be requested.
    """
    set_pending_high_water_mark("2026-08-19T11:00:00+02:00")
    complete_run()

    requested: list[str] = []
    with patch("compass.ingestion.feed_reader.FEED_URL", "https://fake/page-1.atom"):
        entries = list(ingest_atom_feed(_mocked_client(requested)))

    assert len(entries) == 1
    assert requested == ["https://fake/page-1.atom"]
