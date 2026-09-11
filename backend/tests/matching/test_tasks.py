"""Tests for the embedding-generation task -- `generate_embeddings` (real DB, real model) split
from `generate_embeddings_task` (event-loop/Celery plumbing, mocked generation), same split as
`tests/ingestion/test_daily_ingestion.py` / `test_daily_ingestion_task.py`.
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from compass.matching.embedding_model import EMBEDDING_DIMENSIONS
from compass.matching.tasks import BATCH_SIZE, generate_embeddings, generate_embeddings_task
from compass.tenders.enums import ContractType, TenderStatus
from compass.tenders.models import Tender

# A prefix outside PLACSP's real expediente format: isolates these tests'
# synthetic rows for the explicit cleanup below, same reasoning as
# tests/ingestion/test_daily_ingestion.py's "CS2026/94-%" prefix.
TASK_PREFIX = "TEST-TASKS-EMBED"


def _unembedded_tender(expediente: str, title: str) -> Tender:
    """A minimal valid `Tender` with `title_embedding` left at its default (`None`)."""
    return Tender(
        expediente=expediente,
        contracting_body="Ayuntamiento de Prueba",
        title=title,
        cpv_codes=["99888888"],
        contract_type=ContractType.SERVICES,
        procedure_type="Abierto",
        status=TenderStatus.OPEN_FOR_SUBMISSION,
        budget_with_vat=Decimal("50000.00"),
        published_at=datetime.now(UTC),
        updated_at_source=datetime.now(UTC),
    )


async def _cleanup(session: AsyncSession) -> None:
    """`generate_embeddings` commits internally, so the `db_session` fixture's rollback can't
    undo it -- same reasoning as `test_daily_ingestion.py`'s explicit cleanup.
    """
    await session.execute(delete(Tender).where(Tender.expediente.like(f"{TASK_PREFIX}%")))
    await session.commit()


async def test_generate_embeddings_embeds_every_tender_missing_one(
    db_session: AsyncSession,
) -> None:
    """Protects the core behavior: a NULL `title_embedding` gets populated, with the right shape."""
    db_session.add(
        _unembedded_tender(f"{TASK_PREFIX}-1", "Mantenimiento de portal web institucional")
    )
    db_session.add(_unembedded_tender(f"{TASK_PREFIX}-2", "Suministro de mobiliario de oficina"))
    await db_session.flush()

    try:
        count = await generate_embeddings(db_session)

        assert count == 2
        result = await db_session.execute(
            select(Tender).where(Tender.expediente.like(f"{TASK_PREFIX}%"))
        )
        for tender in result.scalars().all():
            assert tender.title_embedding is not None
            assert len(tender.title_embedding) == EMBEDDING_DIMENSIONS
    finally:
        await _cleanup(db_session)


async def test_generate_embeddings_skips_tenders_that_already_have_one(
    db_session: AsyncSession,
) -> None:
    """Protects against re-embedding rows that don't need it -- wasted model calls, and (with a
    non-deterministic model) a value that drifts for no reason.
    """
    already_embedded = _unembedded_tender(f"{TASK_PREFIX}-DONE", "Ya embebido")
    already_embedded.title_embedding = [0.1] * EMBEDDING_DIMENSIONS
    db_session.add(already_embedded)
    await db_session.flush()

    try:
        count = await generate_embeddings(db_session)

        assert count == 0
        await db_session.refresh(already_embedded)
        # pgvector stores float32, not Python's float64 -- an exact 0.1 comes
        # back as 0.10000000149011612, so the comparison needs a tolerance.
        assert already_embedded.title_embedding == pytest.approx([0.1] * EMBEDDING_DIMENSIONS)
    finally:
        await _cleanup(db_session)


async def test_generate_embeddings_drains_a_backlog_larger_than_one_batch(
    db_session: AsyncSession,
) -> None:
    """Protects the while-loop actually looping -- with `BATCH_SIZE` patched down to 2, 5 tenders
    require 3 batches, not just the first one.
    """
    for i in range(5):
        db_session.add(
            _unembedded_tender(f"{TASK_PREFIX}-BATCH-{i}", f"Servicio de prueba numero {i}")
        )
    await db_session.flush()

    try:
        with patch("compass.matching.tasks.BATCH_SIZE", 2):
            count = await generate_embeddings(db_session)

        assert count == 5
    finally:
        await _cleanup(db_session)


def test_batch_size_is_a_sane_positive_bound() -> None:
    """Protects against `BATCH_SIZE` being edited down to something pathological (0, negative)."""
    assert BATCH_SIZE > 0


def test_generate_embeddings_task_runs_end_to_end_with_mocked_generation() -> None:
    """Protects the end-to-end wiring: the real event-loop/engine plumbing, mocked generation.

    The task must return whatever `generate_embeddings` reports.
    """

    async def fake_generate_embeddings(session: AsyncSession) -> int:
        """Stands in for the real batching loop: reports 4 tenders embedded."""
        return 4

    with patch("compass.matching.tasks.generate_embeddings", side_effect=fake_generate_embeddings):
        result = generate_embeddings_task()

    assert result == 4


def test_generate_embeddings_task_propagates_a_failure() -> None:
    """Protects against a crash mid-run being silently swallowed instead of surfacing to Celery."""

    async def failing_generate_embeddings(session: AsyncSession) -> int:
        """Stands in for the real batching loop: simulates a run that crashes."""
        raise RuntimeError("boom")

    with (
        patch(
            "compass.matching.tasks.generate_embeddings", side_effect=failing_generate_embeddings
        ),
        pytest.raises(RuntimeError),
    ):
        generate_embeddings_task()
