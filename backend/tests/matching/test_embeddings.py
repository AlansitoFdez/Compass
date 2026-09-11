"""Tests for embed_texts -- the real model (already cached locally from 2.4), not a stand-in:
a fake embedding would validate nothing about whether the vectors it produces are actually
useful for ranking.
"""

import asyncio
import math
import threading
from unittest.mock import patch

import pytest

from compass.matching import embeddings as embeddings_module
from compass.matching.embedding_model import EMBEDDING_DIMENSIONS
from compass.matching.embeddings import embed_query, embed_texts


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


@pytest.fixture(autouse=True)
def _clear_query_cache() -> None:
    """Keeps `embed_query`'s cache from leaking a hit between tests -- it's module state,
    deliberately shared by the whole process, so a test that asserts on a miss has to
    start from empty.
    """
    embeddings_module._query_cache.clear()


async def test_embed_query_matches_embed_texts_for_the_same_string() -> None:
    """Protects that the cached/threaded path returns the same vector as the direct one --
    it exists to move the work, not to change the answer.
    """
    (expected,) = embed_texts(["Mantenimiento de portal web institucional"])

    assert await embed_query("Mantenimiento de portal web institucional") == expected


async def test_embed_query_encodes_once_per_distinct_text() -> None:
    """Protects the cache: there is exactly one provider profile, so `GET /matches` embeds
    the same paragraph on every request -- ~0.3s of CPU each time, for a byte-for-byte
    identical result.
    """
    with patch.object(embeddings_module, "embed_texts", wraps=embeddings_module.embed_texts) as spy:
        first = await embed_query("Portal web municipal")
        second = await embed_query("Portal web municipal")
        await embed_query("Suministro de mobiliario")

    assert first == second
    assert spy.call_count == 2


async def test_embed_query_runs_the_model_off_the_event_loop() -> None:
    """Protects the other half of the fix: `SentenceTransformer.encode` is synchronous CPU
    work, and calling it straight from a coroutine froze the whole API process, not just
    the request that asked for it.

    The tell is the thread it runs on -- `asyncio.to_thread` hands it to the executor, so
    it must not be the thread the event loop is running on.
    """
    loop_thread = threading.current_thread().ident
    seen: list[int | None] = []

    def recording_embed_texts(texts: list[str]) -> list[list[float]]:
        seen.append(threading.current_thread().ident)
        return [[0.0] * EMBEDDING_DIMENSIONS for _ in texts]

    with patch.object(embeddings_module, "embed_texts", recording_embed_texts):
        await embed_query("Un texto cualquiera")

    assert seen == [seen[0]]
    assert seen[0] != loop_thread
    assert loop_thread == threading.current_thread().ident
    assert asyncio.get_running_loop().is_running()


def test_embed_texts_raises_instead_of_asserting_on_a_wrong_dimension() -> None:
    """Protects the dimension check surviving `python -O`, which strips `assert` outright.

    A vector of the wrong length written to the `Vector(768)` column fails in Postgres,
    far from whatever actually produced it, so this has to fail at the source.
    """

    class _WrongSizeModel:
        def encode(self, texts: list[str], normalize_embeddings: bool) -> object:
            class _Array:
                def tolist(self) -> list[list[float]]:
                    return [[0.0] * (EMBEDDING_DIMENSIONS - 1) for _ in texts]

            return _Array()

    with (
        patch.object(embeddings_module, "_get_model", _WrongSizeModel),
        pytest.raises(ValueError, match=str(EMBEDDING_DIMENSIONS)),
    ):
        embed_texts(["lo que sea"])
