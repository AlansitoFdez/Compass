"""One-off evaluation script (2.4): measures recall@k for candidate embedding models against
the golden set, alongside the lexical ranking already built in 2.3 -- the decision-making tool
that picks which model 2.5 builds the real pgvector column around.

Not part of the matching funnel's runtime code. Invoked by hand:
`uv run python -m compass.matching.embedding_eval`.
"""

import asyncio
import logging
import sys

from sentence_transformers import SentenceTransformer, util
from sqlalchemy.ext.asyncio import AsyncSession

from compass.matching.golden_set import NOT_RELEVANT_EXPEDIENTES, RELEVANT_EXPEDIENTES
from compass.matching.lexical import lexical_matches
from compass.matching.repository import list_matches
from compass.providers.models import Provider
from compass.providers.repository import get_provider
from compass.tenders.models import Tender

logger = logging.getLogger(__name__)

CANDIDATE_MODELS = [
    "ibm-granite/granite-embedding-278m-multilingual",
    "intfloat/multilingual-e5-base",
]

K_VALUES = [5, 10, 15]

GOLDEN_SET_POPULATION = RELEVANT_EXPEDIENTES | NOT_RELEVANT_EXPEDIENTES


def recall_at_k(ranked_expedientes: list[str], k: int) -> float:
    """Fraction of `RELEVANT_EXPEDIENTES` that land in the first `k` of `ranked_expedientes`.

    Args:
        ranked_expedientes: Expedientes ordered best-match-first.
        k: How many of the top ranked results to look at.

    Returns:
        A value in [0, 1]: 1.0 means every relevant tender in the golden set
        made it into the top `k`.
    """
    top_k = set(ranked_expedientes[:k])
    hits = len(top_k & RELEVANT_EXPEDIENTES)
    return hits / len(RELEVANT_EXPEDIENTES)


def rank_by_semantic_similarity(
    model: SentenceTransformer, query: str, tenders: list[Tender]
) -> list[tuple[Tender, float]]:
    """Ranks `tenders` by cosine similarity between `query`'s embedding and each title's.

    Encodes everything in one batch call per side (query, all titles) rather
    than one call per tender -- the whole point of a local model is that
    there's no per-call network cost, but batching still avoids repeated
    Python/tokenizer overhead.
    """
    query_embedding = model.encode(query, normalize_embeddings=True)
    title_embeddings = model.encode([tender.title for tender in tenders], normalize_embeddings=True)

    scores = util.cos_sim(query_embedding, title_embeddings)[0].tolist()
    ranked = sorted(zip(tenders, scores, strict=True), key=lambda pair: pair[1], reverse=True)
    return ranked


def _print_recall_table(label: str, ranked_expedientes: list[str]) -> None:
    print(f"\n=== {label} ===")
    for k in K_VALUES:
        print(f"  recall@{k}: {recall_at_k(ranked_expedientes, k):.2f}")


async def _golden_set_tenders(session: AsyncSession, provider: Provider) -> list[Tender]:
    """Etapa 1 survivors restricted to the golden set's population (excluded ones dropped)."""
    items, _total = await list_matches(session, provider, limit=1000, offset=0)
    return [tender for tender in items if tender.expediente in GOLDEN_SET_POPULATION]


async def _main() -> None:
    from compass.core.db import async_session_factory

    async with async_session_factory() as session:
        provider = await get_provider(session)
        assert provider is not None

        tenders = await _golden_set_tenders(session, provider)
        logger.info(
            "Golden set population: %d tenders (%d relevant)",
            len(tenders),
            len(RELEVANT_EXPEDIENTES),
        )

        lexical_ranked = await lexical_matches(session, provider, limit=len(tenders))
        lexical_expedientes = [tender.expediente for tender, _rank in lexical_ranked]
        _print_recall_table("Lexical (2.3, ts_rank)", lexical_expedientes)

        for model_name in CANDIDATE_MODELS:
            logger.info("Loading %s ...", model_name)
            model = SentenceTransformer(model_name)
            ranked = rank_by_semantic_similarity(model, provider.description, tenders)
            ranked_expedientes = [tender.expediente for tender, _score in ranked]
            _print_recall_table(model_name, ranked_expedientes)

            print("  Top 5:")
            for tender, score in ranked[:5]:
                marker = "x" if tender.expediente in RELEVANT_EXPEDIENTES else " "
                print(f"    [{marker}] {score:.4f} {tender.expediente} - {tender.title[:70]}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if sys.platform == "win32":
        asyncio.run(_main(), loop_factory=asyncio.SelectorEventLoop)
    else:
        asyncio.run(_main())
