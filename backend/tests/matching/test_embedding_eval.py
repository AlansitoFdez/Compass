"""Tests for recall_at_k -- pure function, no database or model involved."""

from compass.matching.embedding_eval import recall_at_k
from compass.matching.golden_set import RELEVANT_EXPEDIENTES


def test_recall_at_k_is_zero_with_no_relevant_hits() -> None:
    """Protects the floor: a ranking with none of the golden set's relevant tenders scores 0."""
    assert recall_at_k(["not-a-real-expediente"], k=10) == 0.0


def test_recall_at_k_is_one_when_every_relevant_tender_is_within_k() -> None:
    """Protects the ceiling: every relevant tender present within the top k scores 1.0."""
    ranked = list(RELEVANT_EXPEDIENTES) + ["padding"] * 5

    assert recall_at_k(ranked, k=len(ranked)) == 1.0


def test_recall_at_k_only_counts_hits_within_the_top_k() -> None:
    """Protects that a relevant tender ranked below k doesn't count, only ones within it."""
    relevant_one = next(iter(RELEVANT_EXPEDIENTES))
    ranked = ["irrelevant-1", "irrelevant-2", relevant_one]

    assert recall_at_k(ranked, k=2) == 0.0
    assert recall_at_k(ranked, k=3) == 1.0 / len(RELEVANT_EXPEDIENTES)
