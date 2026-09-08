"""Loads the embedding model chosen in 2.4 and encodes text into vectors.

Shared by `matching.tasks.generate_embeddings_task` (embeds tender titles for
storage) and `matching.vector` (embeds a provider description at query time)
-- one place owns the model name and how it's invoked, so both stay in sync.
"""

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
    assert all(len(vector) == EMBEDDING_DIMENSIONS for vector in result), (
        f"expected {EMBEDDING_DIMENSIONS}-dim vectors from {EMBEDDING_MODEL_NAME}"
    )
    return result
