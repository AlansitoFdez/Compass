"""Tests for the IT-services CPV vertical filter — pure functions, no database."""

from compass.tenders.vertical import (
    is_it_services_cpv,
    matches_it_vertical,
    normalize_cpv_code,
)


def test_normalize_cpv_code_strips_check_digit() -> None:
    """Protects the format PLACSP actually sends: an 8-digit code with a trailing check digit."""
    assert normalize_cpv_code("72212730-0") == "72212730"


def test_normalize_cpv_code_without_check_digit_is_unchanged() -> None:
    """Protects idempotency: normalizing an already-normalized code is a no-op."""
    assert normalize_cpv_code("72212730") == "72212730"


def test_is_it_services_cpv_matches_division_72() -> None:
    """Protects the prefix match.

    A subgroup code within division 72 must count, not just "72" exactly.
    """
    assert is_it_services_cpv("72212730-0")


def test_is_it_services_cpv_rejects_other_division() -> None:
    """Protects against a false positive from an unrelated division (45 = construction works)."""
    assert not is_it_services_cpv("45000000")


def test_matches_it_vertical_true_if_any_code_matches() -> None:
    """Protects the "any code, not all" rule.

    One IT-services code is enough, even if the other codes aren't.
    """
    assert matches_it_vertical(["45000000", "72200000-5"])


def test_matches_it_vertical_false_if_no_code_matches() -> None:
    """Protects against a tender with zero IT-services codes slipping into the vertical."""
    assert not matches_it_vertical(["45000000", "50000000"])


def test_matches_it_vertical_false_for_empty_list() -> None:
    """Protects the empty-list edge case: no codes at all must not default to a match."""
    assert not matches_it_vertical([])
