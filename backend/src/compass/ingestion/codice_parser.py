"""Maps a single CODICE <entry> to a TenderSchema — the mapping decided in phase1.6.md.

Only the top-level ProcurementProject is used (CPV codes, budget); per-lot
breakdowns under ProcurementProjectLot are deliberately ignored, same
partial-mapping philosophy as the rest of the project.
"""

from datetime import datetime
from decimal import Decimal
from xml.etree.ElementTree import Element
from zoneinfo import ZoneInfo

from compass.ingestion.codice_codes import get_contract_type, get_procedure_type_label, get_status
from compass.tenders.schemas import TenderSchema

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "cac-place-ext": "urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2",
    "cbc-place-ext": "urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonBasicComponents-2",
    "cac": "urn:dgpe:names:draft:codice:schema:xsd:CommonAggregateComponents-2",
}

STATUS_ROOT = "cac-place-ext:ContractFolderStatus"
PROJECT = f"{STATUS_ROOT}/cac:ProcurementProject"
PROCESS = f"{STATUS_ROOT}/cac:TenderingProcess"

MADRID_TZ = ZoneInfo("Europe/Madrid")


def _text(element: Element, path: str) -> str | None:
    return element.findtext(path, namespaces=NS)


def _decimal(entry: Element, path: str) -> Decimal | None:
    text = _text(entry, path)
    return Decimal(text) if text is not None else None


def _cpv_codes(entry: Element) -> list[str]:
    path = f"{PROJECT}/cac:RequiredCommodityClassification/cbc:ItemClassificationCode"
    return [code.text for code in entry.findall(path, NS)]


def _submission_deadline(entry: Element) -> datetime | None:
    period = f"{PROCESS}/cac:TenderSubmissionDeadlinePeriod"
    end_date = _text(entry, f"{period}/cbc:EndDate")
    if end_date is None:
        return None

    end_time = _text(entry, f"{period}/cbc:EndTime") or "00:00:00"
    naive = datetime.fromisoformat(f"{end_date}T{end_time}")
    return naive.replace(tzinfo=MADRID_TZ)


def _document_url(entry: Element, reference_tag: str) -> str | None:
    path = f"{STATUS_ROOT}/cac:{reference_tag}/cac:Attachment/cac:ExternalReference/cbc:URI"
    return _text(entry, path)


def _platform_url(entry: Element) -> str | None:
    link = entry.find("atom:link", NS)
    return link.get("href") if link is not None else None


def _updated_at(entry: Element) -> datetime:
    return datetime.fromisoformat(_text(entry, "atom:updated"))


def parse_codice_entry(entry: Element) -> TenderSchema:
    """Parses one ATOM <entry> (already containing inline CODICE) into a TenderSchema."""
    updated_at = _updated_at(entry)

    return TenderSchema(
        expediente=_text(entry, f"{STATUS_ROOT}/cbc:ContractFolderID"),
        contracting_body=_text(
            entry,
            f"{STATUS_ROOT}/cac-place-ext:LocatedContractingParty/cac:Party/cac:PartyName/cbc:Name",
        ),
        title=_text(entry, f"{PROJECT}/cbc:Name"),
        cpv_codes=_cpv_codes(entry),
        budget_with_vat=_decimal(entry, f"{PROJECT}/cac:BudgetAmount/cbc:TotalAmount"),
        budget_without_vat=_decimal(entry, f"{PROJECT}/cac:BudgetAmount/cbc:TaxExclusiveAmount"),
        estimated_value=_decimal(
            entry, f"{PROJECT}/cac:BudgetAmount/cbc:EstimatedOverallContractAmount"
        ),
        contract_type=get_contract_type(_text(entry, f"{PROJECT}/cbc:TypeCode")),
        procedure_type=get_procedure_type_label(_text(entry, f"{PROCESS}/cbc:ProcedureCode")),
        status=get_status(_text(entry, f"{STATUS_ROOT}/cbc-place-ext:ContractFolderStatusCode")),
        submission_deadline=_submission_deadline(entry),
        location=_text(entry, f"{PROJECT}/cac:RealizedLocation/cbc:CountrySubentity"),
        pcap_url=_document_url(entry, "LegalDocumentReference"),
        ppt_url=_document_url(entry, "TechnicalDocumentReference"),
        platform_url=_platform_url(entry),
        published_at=updated_at,
        updated_at_source=updated_at,
    )
