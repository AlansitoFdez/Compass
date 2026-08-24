"""Tests for the historical archive loader — synthetic zips, no real downloads."""

import io
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

import httpx2
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from compass.ingestion.historical_loader import (
    download_archive,
    iter_entries_from_url,
    iter_entries_from_zip,
    load_month,
    monthly_archive_url,
    recent_months,
)
from compass.tenders.models import Tender

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "codice_entry_sample.xml"
XML_HEADER = b'<?xml version="1.0" encoding="UTF-8"?>\n'


def _atom_feed(entry_xml: bytes) -> bytes:
    """Wraps a raw `<entry>` XML fragment in a single-page ATOM feed document."""
    return XML_HEADER + b'<feed xmlns="http://www.w3.org/2005/Atom">' + entry_xml + b"</feed>"


def _matching_entry() -> bytes:
    """The real fixture, with one CPV swapped to fall inside our IT-services vertical.

    Targets `>CS2026/94<` (an element's exact value, closed by a tag) rather
    than the bare text "CS2026/94" — that also appears earlier, as free text
    inside <summary> ("Id licitación: CS2026/94; ..."), which isn't what our
    parser reads for `expediente` and must NOT be the one that gets replaced.
    """
    content = FIXTURE_PATH.read_bytes().replace(XML_HEADER, b"")
    content = content.replace(b">CS2026/94<", b">CS2026/94-MATCH<", 1)
    return content.replace(b"30231320", b"72000000")


def _non_matching_entry() -> bytes:
    """The real fixture, unmodified -- outside the IT-services vertical."""
    return FIXTURE_PATH.read_bytes().replace(XML_HEADER, b"")


def _malformed_entry() -> bytes:
    """A matching entry whose status code is one PLACSP has never used —
    parse_codice_entry() raises for it; try_parse_codice_entry() must not.
    """
    content = _matching_entry().replace(
        b">PUB</ns3:ContractFolderStatusCode>", b">ZZZZ</ns3:ContractFolderStatusCode>", 1
    )
    return content.replace(b">CS2026/94-MATCH<", b">CS2026/94-MALFORMED<", 1)


def _build_zip(entries: list[bytes]) -> bytes:
    """Packs each entry as its own `.atom` page inside an in-memory monthly-archive ZIP."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for i, entry in enumerate(entries):
            zf.writestr(f"file_{i}.atom", _atom_feed(entry))
    return buffer.getvalue()


def test_monthly_archive_url() -> None:
    """Protects the URL format PLACSP actually serves monthly archives at."""
    assert monthly_archive_url(2026, 6) == (
        "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_643/"
        "licitacionesPerfilesContratanteCompleto3_202606.zip"
    )


def test_recent_months_within_same_year() -> None:
    """Protects the simple case: three consecutive months, all within the same year."""
    assert recent_months(3, today=date(2026, 8, 17)) == [(2026, 6), (2026, 7), (2026, 8)]


def test_recent_months_crosses_year_boundary() -> None:
    """Protects the December-into-January rollover: the year must decrement, not go to month 0."""
    assert recent_months(3, today=date(2026, 1, 15)) == [(2025, 11), (2025, 12), (2026, 1)]


def test_iter_entries_from_zip_reads_only_atom_files(tmp_path: Path) -> None:
    """Protects against a non-`.atom` file inside the archive being parsed as feed content."""
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("a.atom", _atom_feed(_matching_entry()))
        zf.writestr("b.atom", _atom_feed(_non_matching_entry()))
        zf.writestr("readme.txt", "ignorame")

    assert len(list(iter_entries_from_zip(zip_path))) == 2


def test_iter_entries_from_url_cleans_up_temp_file() -> None:
    """Protects against the downloaded temp ZIP surviving past the generator's use of it."""
    zip_content = _build_zip([_matching_entry()])

    def handler(request: httpx2.Request) -> httpx2.Response:
        """Serves the in-memory ZIP for any request, standing in for PLACSP's archive endpoint."""
        return httpx2.Response(200, content=zip_content)

    client = httpx2.Client(transport=httpx2.MockTransport(handler))

    # A side_effect that's a real function: lets download_archive actually
    # run, but also records what it returned in `captured_paths`, so we can
    # later check the file was deleted.
    captured_paths: list[Path] = []

    def _spy_download(url: str, client: httpx2.Client) -> Path:
        """Calls the real `download_archive`, recording the temp path it returns."""
        path = download_archive(url, client)
        captured_paths.append(path)
        return path

    with patch("compass.ingestion.historical_loader.download_archive", side_effect=_spy_download):
        list(iter_entries_from_url("https://fake/archive.zip", client))

    assert not captured_paths[0].exists()


async def test_load_month_persists_only_vertical_matches(db_session: AsyncSession) -> None:
    """Protects the vertical filter inside `load_month`.

    Only the IT-services entry must get persisted.
    """
    zip_content = _build_zip([_matching_entry(), _non_matching_entry()])

    def handler(request: httpx2.Request) -> httpx2.Response:
        """Serves the in-memory ZIP for any request, standing in for PLACSP's archive endpoint."""
        return httpx2.Response(200, content=zip_content)

    client = httpx2.Client(transport=httpx2.MockTransport(handler))

    count = await load_month(2026, 6, client, db_session)
    await db_session.flush()

    assert count == 1

    result = await db_session.execute(select(Tender).where(Tender.expediente == "CS2026/94-MATCH"))
    assert result.scalar_one().cpv_codes[0] == "72000000"


async def test_load_month_skips_a_malformed_entry_without_losing_the_rest(
    db_session: AsyncSession,
) -> None:
    """A malformed entry ahead of a valid one in the archive must not sink the
    valid one — the real bug found in the 1.11 review (one bad entry crashed
    the whole run).
    """
    zip_content = _build_zip([_malformed_entry(), _matching_entry()])

    def handler(request: httpx2.Request) -> httpx2.Response:
        """Serves the in-memory ZIP for any request, standing in for PLACSP's archive endpoint."""
        return httpx2.Response(200, content=zip_content)

    client = httpx2.Client(transport=httpx2.MockTransport(handler))

    count = await load_month(2026, 6, client, db_session)
    await db_session.flush()

    assert count == 1

    result = await db_session.execute(select(Tender).where(Tender.expediente == "CS2026/94-MATCH"))
    assert result.scalar_one_or_none() is not None
    result = await db_session.execute(
        select(Tender).where(Tender.expediente == "CS2026/94-MALFORMED")
    )
    assert result.scalar_one_or_none() is None
