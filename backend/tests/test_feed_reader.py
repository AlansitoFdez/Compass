"""Integration tests for ingest_atom_feed — mocked HTTP pages + real Redis checkpoint."""

import httpx2
import pytest

from compass.ingestion.checkpoint import (
    clear_last_processed_atom_url,
    get_last_processed_atom_url,
    set_last_processed_atom_url,
)
from compass.ingestion.feed_reader import ingest_atom_feed

PAGE_1 = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry><id>1</id></entry>
  <entry><id>2</id></entry>
  <link rel="next" href="https://fake/page-2.atom"/>
</feed>
"""

PAGE_2 = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry><id>3</id></entry>
</feed>
"""

PAGES = {
    "https://fake/page-1.atom": PAGE_1,
    "https://fake/page-2.atom": PAGE_2,
}


@pytest.fixture(autouse=True)
def _clean_checkpoint():
    clear_last_processed_atom_url()
    yield
    clear_last_processed_atom_url()


def _mocked_client() -> httpx2.Client:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, content=PAGES[str(request.url)])

    return httpx2.Client(transport=httpx2.MockTransport(handler))


def test_ingest_atom_feed_yields_all_entries_and_clears_checkpoint_at_the_end() -> None:
    set_last_processed_atom_url("https://fake/page-1.atom")
    client = _mocked_client()

    entries = list(ingest_atom_feed(client))

    assert len(entries) == 3
    assert get_last_processed_atom_url() is None


def test_ingest_atom_feed_resumes_from_an_existing_checkpoint() -> None:
    set_last_processed_atom_url("https://fake/page-2.atom")
    client = _mocked_client()

    entries = list(ingest_atom_feed(client))

    assert len(entries) == 1


def test_checkpoint_reflects_completed_page_even_if_the_next_fetch_then_fails() -> None:
    set_last_processed_atom_url("https://fake/page-1.atom")

    def handler(request: httpx2.Request) -> httpx2.Response:
        if str(request.url) == "https://fake/page-1.atom":
            return httpx2.Response(200, content=PAGE_1)
        return httpx2.Response(500)

    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    generator = ingest_atom_feed(client)

    next(generator)
    next(generator)

    with pytest.raises(httpx2.HTTPStatusError):
        next(generator)

    assert get_last_processed_atom_url() == "https://fake/page-2.atom"
