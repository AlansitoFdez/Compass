"""Tests for the golden-set field-scoring logic -- built in 3.4 for the model
comparison, reused as-is in 4.4's regression gate over the full golden set.
"""

from compass.analysis.enums import CertificationRole
from compass.analysis.extraction_schema import (
    AwardCriteria,
    AwardCriterion,
    EconomicSolvency,
    ExecutionDeadline,
    Guarantees,
    Lots,
    PliegoExtraction,
    RequiredCertification,
    Subcontracting,
    SubmissionDeadline,
    TechnicalSolvency,
)
from compass.analysis.scoring import (
    _blocking_names,
    _nums_match,
    _price_points,
    score_extraction,
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
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[AwardCriterion(name="Precio", points=60, is_price=True)],
            citation=None,
        ),
        guarantees=Guarantees(
            provisional_required=False, definitive_percentage=5.0, description="", citation=None
        ),
        execution_deadline=ExecutionDeadline(
            description="", extensions_allowed=None, extensions_description=None, citation=None
        ),
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


def _required(name: str) -> RequiredCertification:
    """A certification the pliego demands to bid -- the only kind scoring looks at."""
    return RequiredCertification(name=name, role=CertificationRole.REQUIRED_TO_BID, citation=None)


def test_blocking_names_ignores_phrasing_around_a_standard() -> None:
    """Protects the tolerance the old regex bought and 5.8 kept: the family prefix and
    the trimmings around a standard are wording, the number is the requirement.
    """
    assert _blocking_names([_required("ISO 27001")]) == _blocking_names(
        [_required("UNE-EN ISO 27001:2013 o equivalente, en vigor")]
    )


def test_blocking_names_keeps_a_name_that_matches_no_known_standard() -> None:
    """Protects against the exact blindness that let false NO APTO verdicts through the
    gate: the old helper discarded anything without an ISO/CMMI/ENS token, so real
    garbage -- the tax-compliance certificates of `2026/20`, the literal string
    "citation" of `1276564F` -- reduced to the empty set and scored as correct.
    """
    garbage = [
        _required(
            "Certificación positiva, expedida por la Agencia Estatal de Administración "
            "Tributaria de hallarse al corriente en el cumplimiento de sus obligaciones "
            "tributarias."
        ),
        _required("citation"),
    ]

    assert len(_blocking_names(garbage)) == 2


def test_blocking_names_counts_only_what_can_block_a_bid() -> None:
    """Protects the gate from measuring a field the verdict never reads: a scored or
    paperwork certification changes no verdict, so it must change no score either.
    """
    certifications = [
        _required("ISO 27001"),
        RequiredCertification(
            name="ISO 20000", role=CertificationRole.AWARD_CRITERION, citation=None
        ),
        RequiredCertification(
            name="Declaración responsable",
            role=CertificationRole.ADMINISTRATIVE_PAPERWORK,
            citation=None,
        ),
    ]

    assert _blocking_names(certifications) == {"27001"}


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
    expected = _minimal_extraction(certifications=[_required("ISO 27000"), _required("ENS")])
    got_partial = _minimal_extraction(certifications=[_required("ISO 27000")])
    got_full = _minimal_extraction(
        certifications=[_required("ISO 27000 o equivalente"), _required("ENS nivel medio")]
    )

    partial_checks = {c.name: c.correct for c in score_extraction(expected, got_partial)}
    full_checks = {c.name: c.correct for c in score_extraction(expected, got_full)}

    assert partial_checks["certifications"] is False
    assert full_checks["certifications"] is True


def test_score_extraction_catches_a_certification_the_pliego_never_required() -> None:
    """The regression this whole subphase exists for. `2026/20` was annotated with no
    certifications at all and the model returned three tax-compliance certificates,
    producing a false NO APTO -- and the gate called the field correct, because the old
    comparison only asked whether the model had found what the annotator found.
    """
    expected = _minimal_extraction(certifications=[])
    got = _minimal_extraction(
        certifications=[
            _required(
                "Certificación positiva, expedida por la Agencia Estatal de Administración "
                "Tributaria de hallarse al corriente en el cumplimiento de sus obligaciones "
                "tributarias."
            )
        ]
    )

    checks = {c.name: c.correct for c in score_extraction(expected, got)}

    assert checks["certifications"] is False


def test_score_extraction_ignores_a_certification_that_only_scores_points() -> None:
    """Protects the other direction: `INN 26 002` was rejected over an ISO/IEC 20000 the
    pliego merely awards 6 points for. Extracting it is right -- treating it as a
    requirement is what was wrong -- so finding it with the correct role must score clean
    against a golden entry that demands nothing.
    """
    expected = _minimal_extraction(certifications=[])
    got = _minimal_extraction(
        certifications=[
            RequiredCertification(
                name="ISO/IEC 20000", role=CertificationRole.AWARD_CRITERION, citation=None
            )
        ]
    )

    checks = {c.name: c.correct for c in score_extraction(expected, got)}

    assert checks["certifications"] is True


def test_score_extraction_checks_whether_extensions_were_reported() -> None:
    """Protects the 5.6 finding from recurring unmeasured: on `INN 26 002` the model
    described "Durada del contracte: 1 any" for a contract with five prórrogas, and no
    scored field looked at the deadline at all.
    """
    expected = _minimal_extraction(
        execution_deadline=ExecutionDeadline(
            description="1 año",
            extensions_allowed=True,
            extensions_description="Hasta 4 años adicionales.",
            citation=None,
        )
    )
    got = _minimal_extraction(
        execution_deadline=ExecutionDeadline(
            description="1 año",
            extensions_allowed=False,
            extensions_description=None,
            citation=None,
        )
    )

    checks = {c.name: c.correct for c in score_extraction(expected, got)}

    assert checks["execution_deadline.extensions_allowed"] is False
