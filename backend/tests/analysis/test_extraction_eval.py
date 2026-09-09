"""Tests for the pure scoring logic behind the 3.4 model comparison -- not the live
OpenRouter calls, which `uv run python -m compass.analysis.extraction_eval` makes on
demand as this subphase's decision tool (see phase3.4.md for the real run's numbers).
"""

from compass.analysis.extraction_eval import (
    _cert_tokens,
    _nums_match,
    _price_points,
    score_extraction,
)
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


def _minimal_extraction(**overrides: object) -> PliegoExtraction:
    """A syntactically valid `PliegoExtraction` with plain defaults, for scoring tests
    that only care about one or two fields at a time.
    """
    base = PliegoExtraction(
        economic_solvency=EconomicSolvency(
            minimum_annual_turnover_eur=100_000.0, description="", citation=None
        ),
        technical_solvency=TechnicalSolvency(
            minimum_amount_eur=None, description="", citation=None
        ),
        certifications=[],
        certifications_citation=None,
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[AwardCriterion(name="Precio", points=60, is_price=True)],
            citation=None,
        ),
        guarantees=Guarantees(
            provisional_required=False, definitive_percentage=5.0, description="", citation=None
        ),
        execution_deadline=ExecutionDeadline(description="", citation=None),
        submission_deadline=SubmissionDeadline(description="", citation=None),
        subcontracting=Subcontracting(allowed=True, description="", citation=None),
        lots=Lots(
            divided_into_lots=False, can_bid_partial_lots=None, description="", citation=None
        ),
    )
    return base.model_copy(update=overrides)


def test_nums_match_treats_both_none_as_a_match() -> None:
    """Protects the "pliego doesn't state a figure" case: null vs null is correct, not a gap."""
    assert _nums_match(None, None) is True


def test_nums_match_requires_both_present_to_count_as_a_match() -> None:
    """Protects against a model inventing a number where the pliego gives none, or vice versa."""
    assert _nums_match(100.0, None) is False
    assert _nums_match(None, 100.0) is False


def test_nums_match_respects_tolerance() -> None:
    """Protects against penalizing harmless floating-point/rounding noise."""
    assert _nums_match(100.0, 100.4, tol=0.5) is True
    assert _nums_match(100.0, 100.6, tol=0.5) is False


def test_cert_tokens_extracts_known_acronyms_case_insensitively() -> None:
    """Protects the certification recall check against phrasing differences that don't
    change the actual requirement -- "ISO 27000 o equivalente" vs "iso27000".
    """
    tokens = _cert_tokens(["ISO 27000 o equivalente", "certificado CCN-CERT (ENS)"])

    assert "ISO27000" in tokens
    assert "ENS" in tokens
    assert "CCN-CERT" in tokens


def test_price_points_finds_the_is_price_criterion() -> None:
    """Protects picking out the price line item from a multi-criterion breakdown."""
    extraction = _minimal_extraction(
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[
                AwardCriterion(name="Experiencia", points=40, is_price=False),
                AwardCriterion(name="Precio", points=60, is_price=True),
            ],
            citation=None,
        )
    )

    assert _price_points(extraction) == 60


def test_price_points_is_none_without_a_price_criterion() -> None:
    """Protects against silently defaulting to 0 when no criterion is marked as price."""
    extraction = _minimal_extraction(
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[AwardCriterion(name="Experiencia", points=100, is_price=False)],
            citation=None,
        )
    )

    assert _price_points(extraction) is None


def test_score_extraction_is_all_correct_for_an_identical_extraction() -> None:
    """Protects the ceiling: a perfect model response scores every check correct."""
    expected = _minimal_extraction()
    got = expected.model_copy(deep=True)

    checks = score_extraction(expected, got)

    assert all(c.correct for c in checks)


def test_score_extraction_flags_a_wrong_economic_solvency_figure() -> None:
    """Protects that a wrong figure is actually caught, not silently passed."""
    expected = _minimal_extraction()
    got = _minimal_extraction(
        economic_solvency=EconomicSolvency(
            minimum_annual_turnover_eur=999_999.0, description="", citation=None
        )
    )

    checks = score_extraction(expected, got)

    wrong = {c.name for c in checks if not c.correct}
    assert wrong == {"economic_solvency.minimum_annual_turnover_eur"}


def test_score_extraction_requires_full_certification_recall() -> None:
    """Protects against a model claiming partial credit for a subset of the required
    certifications -- the golden set's `A41119033-2026/000065-PeAS` entry needs all six.
    """
    expected = _minimal_extraction(
        certifications=["ISO 27000", "ENS"],
        certifications_citation=Citation(clause="6.4", page=3, quote="..."),
    )
    got_partial = _minimal_extraction(
        certifications=["ISO 27000"],
        certifications_citation=Citation(clause="6.4", page=3, quote="..."),
    )
    got_full = _minimal_extraction(
        certifications=["ISO 27000 o equivalente", "ENS nivel medio"],
        certifications_citation=Citation(clause="6.4", page=3, quote="..."),
    )

    partial_checks = {c.name: c.correct for c in score_extraction(expected, got_partial)}
    full_checks = {c.name: c.correct for c in score_extraction(expected, got_full)}

    assert partial_checks["certifications"] is False
    assert full_checks["certifications"] is True
