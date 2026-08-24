"""Tests for the ATOM feed page fetcher and parser — no real network calls."""

import httpx2
import pytest

from compass.ingestion.atom_client import fetch_atom_page, parse_atom_page

ATOM_WITH_NEXT = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry><id>1</id></entry>
  <entry><id>2</id></entry>
  <link rel="next" href="https://example.com/page-2.atom"/>
</feed>
"""

ATOM_LAST_PAGE = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry><id>3</id></entry>
</feed>
"""


def test_parse_atom_page_extracts_entries_and_next_url() -> None:
    """Protects the happy path: both `entries` and the `rel="next"` link are read out."""
    page = parse_atom_page(ATOM_WITH_NEXT)

    assert len(page.entries) == 2
    assert page.next_url == "https://example.com/page-2.atom"


def test_parse_atom_page_without_next_link() -> None:
    """Protects the last-page case.

    No `rel="next"` link means `next_url` is `None`, not an error.
    """
    page = parse_atom_page(ATOM_LAST_PAGE)

    assert len(page.entries) == 1
    assert page.next_url is None


def test_fetch_atom_page_uses_mocked_transport() -> None:
    """Protects that `fetch_atom_page` requests the given URL and delegates parsing correctly."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        """Confirms the requested URL, then serves a canned two-entry page."""
        assert str(request.url) == "https://fake/page-1.atom"
        return httpx2.Response(200, content=ATOM_WITH_NEXT)

    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    page = fetch_atom_page("https://fake/page-1.atom", client)

    assert len(page.entries) == 2
    assert page.next_url == "https://example.com/page-2.atom"


def test_fetch_atom_page_raises_on_http_error() -> None:
    """Protects against a 404/5xx being silently parsed as an empty page instead of raising."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        """Serves a 404 for any request, standing in for a dead or missing feed page."""
        return httpx2.Response(404)

    client = httpx2.Client(transport=httpx2.MockTransport(handler))

    with pytest.raises(httpx2.HTTPStatusError):
        fetch_atom_page("https://fake/missing.atom", client)
