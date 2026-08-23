"""Tests for the PLACSP CODICE code lookup tables."""

import pytest

from compass.ingestion.codice_codes import get_contract_type, get_procedure_type_label, get_status
from compass.tenders.enums import ContractType, TenderStatus


def test_get_contract_type_resolves_known_code() -> None:
    assert get_contract_type("2") is ContractType.SERVICES


def test_get_contract_type_rejects_unknown_code() -> None:
    with pytest.raises(ValueError, match="Unknown contract type code"):
        get_contract_type("999999")


def test_get_status_resolves_known_code() -> None:
    assert get_status("ANUL") is TenderStatus.CANCELLED


def test_get_status_rejects_unknown_code() -> None:
    with pytest.raises(ValueError, match="Unknown status code"):
        get_status("XYZ")


def test_get_procedure_type_label_resolves_known_code() -> None:
    assert get_procedure_type_label("9") == "Abierto simplificado"


def test_get_procedure_type_label_rejects_unknown_code() -> None:
    with pytest.raises(ValueError, match="Unknown procedure type code"):
        get_procedure_type_label("777")
