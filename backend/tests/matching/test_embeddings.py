"""Tests for embed_texts -- the real model (already cached locally from 2.4), not a stand-in:
a fake embedding would validate nothing about whether the vectors it produces are actually
useful for ranking.
"""

import math

import pytest

from compass.matching.embeddings import embed_texts
from compass.tenders.models import EMBEDDING_DIMENSIONS


def test_embed_texts_returns_unit_normalized_vectors_of_the_right_dimension() -> None:
    """Protects `EMBEDDING_DIMENSIONS` staying in sync with the model's real output, and that
    `normalize_embeddings=True` actually produces unit vectors -- what makes pgvector's
    `vector_cosine_ops` index and `cosine_distance()` agree with a plain dot product.
    """
    vectors = embed_texts(["Mantenimiento de portales web", "Suministro de mobiliario"])

    assert len(vectors) == 2
    for vector in vectors:
        assert len(vector) == EMBEDDING_DIMENSIONS
        norm = math.sqrt(sum(component**2 for component in vector))
        assert norm == pytest.approx(1.0, abs=1e-2)


def test_embed_texts_places_similar_titles_closer_than_unrelated_ones() -> None:
    """Protects against a broken embedding call (e.g. returning constant/zero vectors) passing
    the dimension check above while carrying no real semantic signal.
    """
    query, similar, unrelated = embed_texts(
        [
            "Mantenimiento de portal web institucional con Drupal",
            "Soporte y actualización de portal web en Drupal",
            "Suministro de mobiliario de oficina",
        ]
    )

    def cosine(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b, strict=True))

    assert cosine(query, similar) > cosine(query, unrelated)
