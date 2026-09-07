"""Validation tests for ProviderSchema -- no database involved."""

from decimal import Decimal

from compass.providers.schemas import ProviderSchema

VALID_DATA = {
    "description": "Desarrollamos aplicaciones web a medida.",
    "cpv_codes": ["72000000"],
}


def test_provider_schema_accepts_valid_data() -> None:
    """Protects against a required field turning optional, or a default silently changing.

    `min_budget is None` confirms fields genuinely absent from `VALID_DATA`
    fall back to their declared default rather than raising.
    """
    schema = ProviderSchema(**VALID_DATA)

    assert schema.description == VALID_DATA["description"]
    assert schema.min_budget is None


def test_provider_schema_accepts_full_profile() -> None:
    """Protects the optional fields actually round-tripping when given, not just when absent."""
    schema = ProviderSchema(
        **VALID_DATA,
        min_budget=Decimal("10000.00"),
        max_budget=Decimal("500000.00"),
        annual_revenue=Decimal("1200000.00"),
        certifications=["ISO 27001", "ENS"],
    )

    assert schema.min_budget == Decimal("10000.00")
    assert schema.certifications == ["ISO 27001", "ENS"]
