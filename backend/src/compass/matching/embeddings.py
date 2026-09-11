"""Loads the embedding model chosen in 2.4 and encodes text into vectors.

Shared by `matching.tasks.generate_embeddings_task` (embeds tender titles for
storage) and `matching.vector` (embeds a provider description at query time)
-- one place owns the model name and how it's invoked, so both stay in sync.
"""

import asyncio

from sentence_transformers import SentenceTransformer

from compass.tenders.models import EMBEDDING_DIMENSIONS

# Decided in 2.4 by measuring real recall@k against a golden set -- see
# docs/phases/phase2/subphases/phase2.4.md. Its 768-dimensional output is
# what fixes tenders.models.EMBEDDING_DIMENSIONS.
EMBEDDING_MODEL_NAME = "ibm-granite/granite-embedding-278m-multilingual"

# Loaded once per process and reused -- the model's weights are ~500MB, not
# something to reload on every call. A Celery worker (--pool=solo) and a
# FastAPI process each get their own instance, lazily, on first use.
_model: SentenceTransformer | None = None

# Query embeddings, keyed by the exact text. Not `functools.lru_cache`: the value is a
# `list[float]` built inside a coroutine, and lru_cache would cache the coroutine object
# rather than its result. See `embed_query` for why caching this is worth it at all.
_query_cache: dict[str, list[float]] = {}
_QUERY_CACHE_MAX_ENTRIES = 32


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Encodes `texts` into normalized embedding vectors, one batch call for all of them.

    Args:
        texts: The strings to embed -- tender titles, or a provider
            description. Batched together rather than one call per text: the
            whole point of a local model is no per-call network cost, but
            batching still avoids repeated tokenizer/Python overhead.

    Returns:
        One `EMBEDDING_DIMENSIONS`-length vector per input text, in the same
        order, normalized to unit length (so cosine distance and dot product
        agree -- matches how pgvector's `vector_cosine_ops` index is built).
    """
    model = _get_model()
    embeddings = model.encode(texts, normalize_embeddings=True)
    result: list[list[float]] = embeddings.tolist()
    # A `raise`, not an `assert`: asserts vanish under `python -O`, and a wrong dimension
    # is exactly the failure this has to catch at its source -- otherwise it surfaces much
    # later as a Postgres error on the Vector(768) column, far from the cause.
    wrong = next((len(vector) for vector in result if len(vector) != EMBEDDING_DIMENSIONS), None)
    if wrong is not None:
        raise ValueError(
            f"expected {EMBEDDING_DIMENSIONS}-dim vectors from {EMBEDDING_MODEL_NAME}, got {wrong}"
        )
    return result


async def embed_query(text: str) -> list[float]:
    """The embedding of a single query string, cached and off the event loop.

    Both of those matter for `matching.vector`, which runs inside a request handler:

    - **Cached.** The only query this project ever embeds is the provider's own
      description, and there is exactly one provider profile (a singleton row, see
      `providers.models.Provider`). Re-encoding the same paragraph on every call to
      `GET /matches` was measured at ~0.3s of pure CPU per request, for a result that is
      byte-for-byte identical until the profile is edited.
    - **Off the event loop.** `SentenceTransformer.encode` is synchronous CPU work, so
      calling it directly from a coroutine blocks the whole process -- not just the
      caller. Measured before this change: `/health` degraded from 0.21s to 0.33s while
      four `/matches` requests were in flight. `asyncio.to_thread` hands it to the
      default executor, where it blocks a worker thread instead of the loop.

    Args:
        text: The query to embed -- in practice, `Provider.description`.

    Returns:
        Its `EMBEDDING_DIMENSIONS`-length normalized vector.
    """
    cached = _query_cache.get(text)
    if cached is not None:
        return cached

    (embedding,) = await asyncio.to_thread(embed_texts, [text])
    # Bounded so an unexpected caller (an eval script sweeping many texts) can't grow this
    # without limit; with a single provider profile the real occupancy is one entry.
    if len(_query_cache) >= _QUERY_CACHE_MAX_ENTRIES:
        _query_cache.clear()
    _query_cache[text] = embedding
    return embedding
