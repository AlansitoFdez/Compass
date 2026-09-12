"""Scores a model's `PliegoExtraction` against a hand-annotated golden-set entry.

Built in 3.4 to pick the extraction model by comparing two OpenRouter candidates;
reused as-is in 4.4 to generalize the same field-by-field check to the full 25-pliego
golden set as a regression gate (`regression_eval.py`), instead of duplicating this
logic between the two scripts.
"""

import re
import unicodedata
from dataclasses import dataclass

from compass.analysis.enums import CertificationRole
from compass.analysis.extraction_schema import PliegoExtraction, RequiredCertification

_WORD_RE = re.compile(r"[a-z0-9]+")


def _normalized_name(name: str) -> str:
    """A certification's name reduced to lowercase, accent-free words joined by spaces,
    so 'ISO/IEC 27001:2013' and 'ISO IEC 27001 2013' compare equal.
    """
    decomposed = unicodedata.normalize("NFKD", name)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(_WORD_RE.findall(without_accents.lower()))


def _blocking_names(certifications: list[RequiredCertification]) -> set[str]:
    """The certifications that can actually fail a bid, normalized for comparison.

    Only `REQUIRED_TO_BID` ones, because those are exactly what `verdict.compute_verdict`
    blocks on -- scoring anything else would measure a field the verdict never reads.

    Until 5.8 this scored a regex over the raw strings (`ISO\\d+|CMMI|ENS|IEC\\d+|
    CCN-CERT`), and that made the gate blind to the failure mode that mattered. The
    garbage a real extraction put in this field -- "Certificación positiva, expedida por
    la Agencia Estatal de Administración Tributaria...", and in one case the literal
    string "citation" -- contains no such token, so it reduced to the empty set; against
    a golden-set entry annotated `[]` the comparison then said **correct**. The field
    that produced false NO APTO verdicts was passing its own regression gate, because
    what the verdict acted on and what the gate measured were not the same thing.
    """
    return {
        _normalized_name(certification.name)
        for certification in certifications
        if certification.role is CertificationRole.REQUIRED_TO_BID
    }


def _price_points(extraction: PliegoExtraction) -> float | None:
    for criterion in extraction.award_criteria.criteria:
        if criterion.is_price:
            return criterion.points
    return None


def _nums_match(expected: float | None, got: float | None, *, tol: float = 1.0) -> bool:
    if expected is None or got is None:
        return expected is None and got is None
    return abs(expected - got) <= tol


@dataclass
class FieldCheck:
    """One scored field: whether the model's value matches the hand-annotated one."""

    name: str
    correct: bool
    expected: object
    got: object


def score_extraction(expected: PliegoExtraction, got: PliegoExtraction) -> list[FieldCheck]:
    """The 10 objectively-checkable subfields -- the numeric/boolean/list data a verdict
    (3.7) actually computes from, not the free-text descriptions (see phase3.4.md for
    why those aren't scored mechanically).
    """
    expected_certifications = _blocking_names(expected.certifications)
    got_certifications = _blocking_names(got.certifications)
    # Set equality, not containment. Containment was the other half of the blindness:
    # it only asked "did the model find what the annotator found", never "did it demand
    # something the pliego doesn't", and an extra blocking certification is precisely
    # what turns into a false NO APTO.
    certifications_correct = expected_certifications == got_certifications

    return [
        FieldCheck(
            "economic_solvency.minimum_annual_turnover_eur",
            _nums_match(
                expected.economic_solvency.minimum_annual_turnover_eur,
                got.economic_solvency.minimum_annual_turnover_eur,
            ),
            expected.economic_solvency.minimum_annual_turnover_eur,
            got.economic_solvency.minimum_annual_turnover_eur,
        ),
        FieldCheck(
            "technical_solvency.minimum_amount_eur",
            _nums_match(
                expected.technical_solvency.minimum_amount_eur,
                got.technical_solvency.minimum_amount_eur,
            ),
            expected.technical_solvency.minimum_amount_eur,
            got.technical_solvency.minimum_amount_eur,
        ),
        FieldCheck(
            "certifications",
            certifications_correct,
            sorted(expected_certifications),
            sorted(got_certifications),
        ),
        FieldCheck(
            "execution_deadline.extensions_allowed",
            expected.execution_deadline.extensions_allowed
            == got.execution_deadline.extensions_allowed,
            expected.execution_deadline.extensions_allowed,
            got.execution_deadline.extensions_allowed,
        ),
        FieldCheck(
            "award_criteria.total_points",
            _nums_match(
                expected.award_criteria.total_points, got.award_criteria.total_points, tol=0.5
            ),
            expected.award_criteria.total_points,
            got.award_criteria.total_points,
        ),
        FieldCheck(
            "award_criteria.price_points",
            _nums_match(_price_points(expected), _price_points(got), tol=0.5),
            _price_points(expected),
            _price_points(got),
        ),
        FieldCheck(
            "guarantees.provisional_required",
            expected.guarantees.provisional_required == got.guarantees.provisional_required,
            expected.guarantees.provisional_required,
            got.guarantees.provisional_required,
        ),
        FieldCheck(
            "guarantees.definitive_percentage",
            _nums_match(
                expected.guarantees.definitive_percentage,
                got.guarantees.definitive_percentage,
                tol=0.5,
            ),
            expected.guarantees.definitive_percentage,
            got.guarantees.definitive_percentage,
        ),
        FieldCheck(
            "subcontracting.allowed",
            expected.subcontracting.allowed == got.subcontracting.allowed,
            expected.subcontracting.allowed,
            got.subcontracting.allowed,
        ),
        FieldCheck(
            "lots.divided_into_lots",
            expected.lots.divided_into_lots == got.lots.divided_into_lots,
            expected.lots.divided_into_lots,
            got.lots.divided_into_lots,
        ),
    ]
