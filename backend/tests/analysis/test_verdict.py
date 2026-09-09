"""Tests for `compute_verdict` -- pure comparison logic, no database and no PDF fixture:
`PliegoExtraction` and `Provider` are both plain Python objects here.
"""

from decimal import Decimal

from compass.analysis.enums import Verdict
from compass.analysis.extraction_schema import (
    AwardCriteria,
    AwardCriterion,
    Citation,
    EconomicSolvency,
    ExecutionDeadline,
    Guarantees,
    Lots,
    PliegoExtraction,
    Subcontracting,
    SubmissionDeadline,
    TechnicalSolvency,
)
from compass.analysis.verdict import compute_verdict
from compass.providers.models import PROVIDER_ID, Provider

TURNOVER_CITATION = Citation(clause="12.2", page=3, quote="cifra de negocio minima de 300000 euros")
CERTIFICATIONS_CITATION = Citation(clause="9", page=2, quote="Se exige la certificacion ISO 27001")


def _provider(
    *,
    annual_revenue: Decimal | None = None,
    certifications: list[str] | None = None,
) -> Provider:
    """A `Provider` with only the fields `compute_verdict` reads set explicitly --
    the rest take the model's own defaults, irrelevant to a verdict comparison.
    """
    return Provider(
        id=PROVIDER_ID,
        description="Consultora de desarrollo de software",
        cpv_codes=["72000000"],
        annual_revenue=annual_revenue,
        certifications=certifications,
    )


def _extraction(
    *,
    minimum_annual_turnover_eur: float | None = None,
    minimum_amount_eur: float | None = None,
    certifications: list[str] | None = None,
) -> PliegoExtraction:
    """A syntactically valid `PliegoExtraction` with only the fields `compute_verdict`
    reads set to a non-default value -- every other field is informational and
    doesn't gate the verdict (see `verdict.py`'s module docstring).
    """
    return PliegoExtraction(
        economic_solvency=EconomicSolvency(
            minimum_annual_turnover_eur=minimum_annual_turnover_eur,
            description="",
            citation=TURNOVER_CITATION if minimum_annual_turnover_eur is not None else None,
        ),
        technical_solvency=TechnicalSolvency(
            minimum_amount_eur=minimum_amount_eur,
            description="",
            citation=None,
        ),
        certifications=certifications or [],
        certifications_citation=CERTIFICATIONS_CITATION if certifications else None,
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[AwardCriterion(name="Precio", points=60, is_price=True)],
            citation=None,
        ),
        guarantees=Guarantees(
            provisional_required=False,
            definitive_percentage=None,
            description="",
            citation=None,
        ),
        execution_deadline=ExecutionDeadline(description="", citation=None),
        submission_deadline=SubmissionDeadline(description="", citation=None),
        subcontracting=Subcontracting(allowed=True, description="", citation=None),
        lots=Lots(
            divided_into_lots=False, can_bid_partial_lots=None, description="", citation=None
        ),
    )


def test_apto_when_the_profile_clears_every_stated_requirement() -> None:
    """Protects the ceiling: turnover covered, certification held -> APTO, no reasons."""
    extraction = _extraction(minimum_annual_turnover_eur=100_000, certifications=["ISO 27001"])
    provider = _provider(annual_revenue=Decimal("200000"), certifications=["ISO 27001:2013"])

    result = compute_verdict(extraction, provider)

    assert result.verdict == Verdict.APTO
    assert result.reasons == []


def test_apto_when_the_pliego_states_no_solvency_or_certification_requirements() -> None:
    """Protects the vacuous case: nothing to check isn't the same as a reservation."""
    extraction = _extraction()
    provider = _provider()

    result = compute_verdict(extraction, provider)

    assert result.verdict == Verdict.APTO
    assert result.reasons == []


def test_no_apto_when_required_turnover_exceeds_declared_revenue() -> None:
    """Protects the design doc's own worked example: a stated shortfall blocks the bid,
    citing the clause that stated it.
    """
    extraction = _extraction(minimum_annual_turnover_eur=300_000)
    provider = _provider(annual_revenue=Decimal("180000"))

    result = compute_verdict(extraction, provider)

    assert result.verdict == Verdict.NO_APTO
    assert len(result.reasons) == 1
    assert result.reasons[0].citation == TURNOVER_CITATION
    assert "300.000" in result.reasons[0].detail
    assert "180.000" in result.reasons[0].detail


def test_no_apto_when_a_required_certification_is_missing() -> None:
    """Protects the second blocking path: an unmet certification blocks on its own,
    even with turnover otherwise satisfied.
    """
    extraction = _extraction(
        minimum_annual_turnover_eur=50_000, certifications=["ISO 27001", "ENS"]
    )
    provider = _provider(annual_revenue=Decimal("500000"), certifications=["ISO 27001"])

    result = compute_verdict(extraction, provider)

    assert result.verdict == Verdict.NO_APTO
    assert len(result.reasons) == 1
    assert "ENS" in result.reasons[0].detail


def test_certification_match_is_tolerant_of_naming_variants() -> None:
    """Protects against a false NO_APTO from phrasing alone: the pliego's short form
    and the profile's fuller form of the same certification must match.
    """
    extraction = _extraction(certifications=["ISO 27001"])
    provider = _provider(certifications=["ISO/IEC 27001:2013"])

    result = compute_verdict(extraction, provider)

    assert result.verdict == Verdict.APTO


def test_apto_con_reservas_when_technical_solvency_states_an_unverifiable_amount() -> None:
    """Protects the structural gap: `Provider` has no field for past-work amounts, so
    a stated requirement there can only ever be a reservation, never a pass or a block.
    """
    extraction = _extraction(minimum_amount_eur=150_000)
    provider = _provider()

    result = compute_verdict(extraction, provider)

    assert result.verdict == Verdict.APTO_CON_RESERVAS
    assert len(result.reasons) == 1
    assert "trabajos previos" in result.reasons[0].detail


def test_apto_con_reservas_when_turnover_is_required_but_profile_declares_none() -> None:
    """Protects the other unverifiable case: a stated requirement against a profile
    that simply hasn't declared the number needed to check it.
    """
    extraction = _extraction(minimum_annual_turnover_eur=100_000)
    provider = _provider(annual_revenue=None)

    result = compute_verdict(extraction, provider)

    assert result.verdict == Verdict.APTO_CON_RESERVAS
    assert len(result.reasons) == 1
    assert result.reasons[0].citation == TURNOVER_CITATION


def test_no_apto_outranks_a_simultaneous_reservation() -> None:
    """Protects the aggregation rule: a blocking reason always wins over a merely
    unverifiable one, and both are reported together rather than the reservation
    getting dropped.
    """
    extraction = _extraction(minimum_annual_turnover_eur=300_000, minimum_amount_eur=150_000)
    provider = _provider(annual_revenue=Decimal("180000"))

    result = compute_verdict(extraction, provider)

    assert result.verdict == Verdict.NO_APTO
    assert len(result.reasons) == 2
