"""Drains the PLACSP ATOM feed end to end, combining atom_client and checkpoint."""

from collections.abc import Iterator
from datetime import datetime
from xml.etree.ElementTree import Element

import httpx2

from compass.ingestion.atom_client import ATOM_NS, FEED_URL, fetch_atom_page
from compass.ingestion.checkpoint import (
    get_high_water_mark,
    get_resume_url,
    set_pending_high_water_mark,
    set_resume_url,
)


def _entry_updated_at(entry: Element) -> datetime:
    updated = entry.findtext(f"{ATOM_NS}updated")
    if updated is None:
        raise ValueError("Entry is missing atom:updated")
    return datetime.fromisoformat(updated)


def ingest_atom_feed(client: httpx2.Client) -> Iterator[Element]:
    """Yields raw <entry> elements, newest-first, following `next` from a
    resume point (or FEED_URL).

    Stops once an entry at or older than the high-water mark left by the
    last fully completed run is reached, instead of always walking the
    feed's pagination to the very end. Real PLACSP pagination cursors are
    re-derived fresh on every request to FEED_URL (verified against the live
    feed: the `next` URL embeds the fetch timestamp) and can span months of
    backlog, so a plain "walk until next is None" run repeats that whole
    backlog on every single call — the bug found in the 1.11 review. What's
    stable across runs is content, not cursors: entries are strictly ordered
    newest-first by `atom:updated` within a page (also verified against the
    live feed), so a high-water mark on that field is a safe stopping point
    — including across republished tenders, which simply reappear near the
    top with a newer `atom:updated` and are picked up again.

    The caller is responsible for calling checkpoint.complete_run() once,
    after its own writes are durably committed — this generator only leaves
    the per-run breadcrumbs (pending high-water mark, resume URL) needed to
    do that safely, it never promotes or clears them itself.
    """
    is_fresh_start = get_resume_url() is None
    url: str | None = get_resume_url() or FEED_URL
    high_water_mark = get_high_water_mark()
    high_water_dt = datetime.fromisoformat(high_water_mark) if high_water_mark else None

    while url is not None:
        page = fetch_atom_page(url, client)

        if is_fresh_start and page.entries:
            set_pending_high_water_mark(_entry_updated_at(page.entries[0]).isoformat())
            is_fresh_start = False

        for entry in page.entries:
            if high_water_dt is not None and _entry_updated_at(entry) <= high_water_dt:
                return
            yield entry

        if page.next_url is not None:
            set_resume_url(page.next_url)
        url = page.next_url
