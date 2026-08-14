"""Drains the PLACSP ATOM feed end to end, combining atom_client and checkpoint."""

from collections.abc import Iterator
from xml.etree.ElementTree import Element

import httpx2

from compass.ingestion.atom_client import FEED_URL, fetch_atom_page
from compass.ingestion.checkpoint import (
    clear_last_processed_atom_url,
    get_last_processed_atom_url,
    set_last_processed_atom_url,
)


def ingest_atom_feed(client: httpx2.Client) -> Iterator[Element]:
    """Yields raw <entry> elements, following `next` from the last checkpoint (or FEED_URL)."""
    url = get_last_processed_atom_url() or FEED_URL

    while url is not None:
        page = fetch_atom_page(url, client)
        yield from page.entries

        if page.next_url is None:
            clear_last_processed_atom_url()
        else:
            set_last_processed_atom_url(page.next_url)

        url = page.next_url
