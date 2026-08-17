"""Tests for parsing a real CODICE entry into a TenderSchema."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from xml.etree.ElementTree import Element, fromstring

from compass.ingestion.codice_parser import parse_codice_entry
from compass.tenders.enums import ContractType, TenderStatus

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "codice_entry_sample.xml"


def _load_sample_entry() -> Element:
    return fromstring(FIXTURE_PATH.read_bytes())


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
    assert tender.platform_url.startswith("https://contrataciondelestado.es")
    assert tender.published_at == tender.updated_at_source
