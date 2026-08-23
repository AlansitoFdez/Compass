"""Tests for parsing a real CODICE entry into a TenderSchema."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from xml.etree.ElementTree import Element, fromstring
from zoneinfo import ZoneInfo

from compass.ingestion.codice_parser import _cpv_codes, parse_codice_entry, try_parse_codice_entry
from compass.tenders.enums import ContractType, TenderStatus

MADRID_TZ = ZoneInfo("Europe/Madrid")

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "codice_entry_sample.xml"


def _load_sample_entry() -> Element:
    return fromstring(FIXTURE_PATH.read_bytes())


def _load_entry_with_empty_cpv_code() -> Element:
    """The real fixture, with its first of 9 CPV codes emptied out — a real
    shape seen in the wild (an <ItemClassificationCode/> with no text).
    """
    raw = FIXTURE_PATH.read_bytes()
    mutated = raw.replace(
        b">30231320</ns2:ItemClassificationCode>", b"></ns2:ItemClassificationCode>", 1
    )
    assert mutated != raw, "fixture no contenía el codigo CPV esperado"
    return fromstring(mutated)


def _load_entry_with_unknown_status_code() -> Element:
    """The real fixture, with its status code replaced by one PLACSP has never
    used — get_status() raises ValueError for it, same as a genuinely new code.
    """
    raw = FIXTURE_PATH.read_bytes()
    mutated = raw.replace(
        b">PUB</ns3:ContractFolderStatusCode>", b">ZZZZ</ns3:ContractFolderStatusCode>", 1
    )
    assert mutated != raw, "fixture no contenía el codigo de estado esperado"
    return fromstring(mutated)


def _load_entry_without_notices() -> Element:
    """The real fixture, with both <ValidNoticeInfo> blocks stripped out —
    a real shape too (very recently opened tenders, or lighter-publicity
    procedures, may not have one yet).
    """
    raw = FIXTURE_PATH.read_bytes().decode("utf-8")
    start = raw.index("<ns1:ValidNoticeInfo>")
    end = raw.rindex("</ns1:ValidNoticeInfo>") + len("</ns1:ValidNoticeInfo>")
    mutated = (raw[:start] + raw[end:]).encode("utf-8")
    assert b"ValidNoticeInfo" not in mutated
    return fromstring(mutated)


def _load_entry_with_an_earlier_second_notice() -> Element:
    """The real fixture's two <ValidNoticeInfo> blocks both date 2026-08-15 —
    this backdates the first one (DOC_CD) to 2020-01-01, so the minimum
    across notices is unambiguous and distinct from atom:updated's day.
    """
    raw = FIXTURE_PATH.read_bytes()
    mutated = raw.replace(
        b"<ns2:IssueDate>2026-08-15</ns2:IssueDate>",
        b"<ns2:IssueDate>2020-01-01</ns2:IssueDate>",
        1,
    )
    assert mutated != raw, "fixture no contenía la fecha de aviso esperada"
    return fromstring(mutated)


def test_parse_codice_entry_extracts_all_fields() -> None:
    tender = parse_codice_entry(_load_sample_entry())

    assert tender.expediente == "CS2026/94"
    assert tender.contracting_body == "Junta de Gobierno del Ayuntamiento de Oviedo"
    assert "tecnológico" in tender.title
    assert len(tender.cpv_codes) == 9
    assert tender.budget_with_vat == Decimal("99474.1")
    assert tender.budget_without_vat == Decimal("82210")
    assert tender.estimated_value == Decimal("89406")
    assert tender.contract_type is ContractType.SUPPLIES
    assert tender.procedure_type == "Abierto"
    assert tender.status is TenderStatus.OPEN_FOR_SUBMISSION
    assert tender.submission_deadline == datetime.fromisoformat("2026-08-31T23:59:00+02:00")
    assert tender.location == "Asturias"
    assert tender.pcap_url is not None
    assert tender.ppt_url is not None
    assert tender.pcap_url != tender.ppt_url
    assert tender.platform_url is not None
    assert tender.platform_url.startswith("https://contrataciondelestado.es")
    # La fecha del aviso publicado (2026-08-15, medianoche) es real,
    # distinta del instante exacto de atom:updated -- bug 3 de la 1.11.
    assert tender.published_at == datetime(2026, 8, 15, tzinfo=MADRID_TZ)
    assert tender.published_at != tender.updated_at_source


def test_parse_codice_entry_published_at_falls_back_to_updated_when_no_notices() -> None:
    tender = parse_codice_entry(_load_entry_without_notices())

    assert tender.published_at == tender.updated_at_source


def test_parse_codice_entry_published_at_uses_the_earliest_notice() -> None:
    tender = parse_codice_entry(_load_entry_with_an_earlier_second_notice())

    assert tender.published_at == datetime(2020, 1, 1, tzinfo=MADRID_TZ)


def test_cpv_codes_skips_empty_elements() -> None:
    codes = _cpv_codes(_load_entry_with_empty_cpv_code())

    assert len(codes) == 8
    assert None not in codes


def test_try_parse_codice_entry_returns_the_tender_for_a_valid_entry() -> None:
    tender = try_parse_codice_entry(_load_sample_entry())

    assert tender is not None
    assert tender.expediente == "CS2026/94"


def test_try_parse_codice_entry_returns_none_for_an_unknown_status_code() -> None:
    assert try_parse_codice_entry(_load_entry_with_unknown_status_code()) is None
