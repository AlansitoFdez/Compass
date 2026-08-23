"""Validation tests for TenderSchema — no database involved."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from compass.tenders.enums import ContractType, TenderStatus
from compass.tenders.schemas import TenderSchema

VALID_DATA = {
    "expediente": "TEST-0001",
    "contracting_body": "Ayuntamiento de Prueba",
    "title": "Servicio de desarrollo de prueba",
    "cpv_codes": ["72000000"],
    "contract_type": ContractType.SERVICES,
    "procedure_type": "open",
    "status": TenderStatus.OPEN_FOR_SUBMISSION,
    "published_at": datetime.now(UTC),
    "updated_at_source": datetime.now(UTC),
}


def test_tender_schema_accepts_valid_data() -> None:
    """Protects against a required field turning optional, or a default silently changing.

    `budget_with_vat is None` confirms fields genuinely absent from
    `VALID_DATA` fall back to their declared default rather than raising.
    """
    schema = TenderSchema(**VALID_DATA)

    assert schema.contract_type is ContractType.SERVICES
    assert schema.budget_with_vat is None


def test_tender_schema_rejects_invalid_status() -> None:
    """Protects the closed `TenderStatus` set.

    An unrecognized value must fail loud, not slip in as a plain string.
    """
    with pytest.raises(ValidationError):
        TenderSchema(**{**VALID_DATA, "status": "not_a_real_status"})
