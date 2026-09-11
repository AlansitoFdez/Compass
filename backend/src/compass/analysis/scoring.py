"""Scores a model's `PliegoExtraction` against a hand-annotated golden-set entry.

Built in 3.4 to pick the extraction model by comparing two OpenRouter candidates;
reused as-is in 4.4 to generalize the same field-by-field check to the full 25-pliego
golden set as a regression gate (`regression_eval.py`), instead of duplicating this
logic between the two scripts.
"""

import re
from dataclasses import dataclass

from compass.analysis.extraction_schema import PliegoExtraction

CERT_TOKEN_RE = re.compile(r"ISO\s?\d{4,5}|CMMI|ENS\b|IEC\s?\d+|CCN-?CERT", re.IGNORECASE)


def _cert_tokens(certifications: list[str]) -> set[str]:
    joined = " | ".join(certifications)
    return {m.group(0).upper().replace(" ", "") for m in CERT_TOKEN_RE.finditer(joined)}


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
    """The 9 objectively-checkable subfields -- the numeric/boolean/list data a verdict
    (3.7) actually computes from, not the free-text descriptions (see phase3.4.md for
    why those aren't scored mechanically).
    """
    expected_cert_tokens = _cert_tokens(expected.certifications)
    got_cert_tokens = _cert_tokens(got.certifications)
    certifications_correct = (
        expected_cert_tokens.issubset(got_cert_tokens)
        if expected_cert_tokens
        else not got_cert_tokens
    )

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
            sorted(expected_cert_tokens),
            sorted(got_cert_tokens),
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
