"""Pydantic schema for a parsed tender — used by the ingestion pipeline and (later) the API."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from compass.tenders.enums import ContractType, TenderStatus


class TenderSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    expediente: str
    contracting_body: str
    title: str
    cpv_codes: list[str]

    budget_with_vat: Decimal | None = None
    budget_without_vat: Decimal | None = None
    estimated_value: Decimal | None = None

    contract_type: ContractType
    procedure_type: str
    status: TenderStatus

    submission_deadline: datetime | None = None
    location: str | None = None

    pcap_url: str | None = None
    ppt_url: str | None = None
    platform_url: str | None = None

    published_at: datetime
    updated_at_source: datetime
