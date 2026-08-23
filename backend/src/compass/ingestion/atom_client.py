"""Fetches and parses a single page of the PLACSP ATOM feed (structure only, not CODICE content)."""

from dataclasses import dataclass
from xml.etree.ElementTree import Element, fromstring

import httpx2

ATOM_NS = "{http://www.w3.org/2005/Atom}"

FEED_URL = (
    "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_643/"
    "licitacionesPerfilesContratanteCompleto3.atom"
)


@dataclass
class AtomPage:
    """One page of the PLACSP ATOM feed.

    Attributes:
        entries: The `<entry>` elements on this page, each with its CODICE
            content inline -- unparsed at this point, just XML elements.
        next_url: URL of the next page, or `None` when this is the last one.
    """

    entries: list[Element]
    next_url: str | None


def parse_atom_page(xml_content: bytes) -> AtomPage:
    """Pure parsing: no network involved, easy to test with a local XML fixture."""
    root = fromstring(xml_content)
    entries = root.findall(f"{ATOM_NS}entry")
    next_url = next(
        (link.get("href") for link in root.findall(f"{ATOM_NS}link") if link.get("rel") == "next"),
        None,
    )
    return AtomPage(entries=entries, next_url=next_url)


def fetch_atom_page(url: str, client: httpx2.Client) -> AtomPage:
    """Fetches one page over HTTP and parses it."""
    response = client.get(url)
    response.raise_for_status()
    return parse_atom_page(response.content)
