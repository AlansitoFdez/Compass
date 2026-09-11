"""Tests for the historical backfill task -- the one that fills an empty corpus.

Its lock and event-loop plumbing are the same shape as `daily_ingestion_task`'s, already
covered in `test_daily_ingestion_task.py`. What is specific here is what a *first* run has
to leave behind, which is not just rows.
"""

from unittest.mock import patch

from compass.core.redis_client import get_redis_client
from compass.ingestion.tasks import BACKFILL_LOCK_KEY, backfill_historical_task


def test_the_backfill_queues_the_embeddings_once_it_finishes() -> None:
    """Protects the first-run experience, not the loading.

    A freshly loaded corpus has no embeddings, and the vector half of the ranking skips
    every row that lacks one -- so without this chaining, someone who just set up Compass
    would watch thousands of tenders arrive and still see a thin, lexical-only list of
    matches until beat's own tick came round up to fifteen minutes later, with nothing on
    screen explaining the wait.

    Found by walking the whole first-run path end to end, which is the only way a gap
    between two separately-correct tasks shows up at all.
    """
    with (
        patch("compass.ingestion.tasks._run_backfill", return_value=1234),
        patch("compass.ingestion.tasks.generate_embeddings_task") as embeddings,
    ):
        persisted = backfill_historical_task()

    assert persisted == 1234
    embeddings.delay.assert_called_once_with()


def test_a_second_backfill_is_dropped_while_one_is_running() -> None:
    """Protects against downloading ~600MB twice over.

    Two concurrent backfills would fetch the same three monthly archives and upsert the
    same rows over each other -- harmless, but slow enough to matter on the one path where
    a user is watching a number and waiting.
    """
    lock = get_redis_client().lock(BACKFILL_LOCK_KEY, timeout=30)
    assert lock.acquire(blocking=False)
    try:
        with patch("compass.ingestion.tasks._run_backfill") as run:
            persisted = backfill_historical_task()

        assert persisted == 0
        run.assert_not_called()
    finally:
        lock.release()


def test_the_backfill_does_not_queue_embeddings_when_it_was_skipped() -> None:
    """The other side of the lock: a run that did nothing must not chain work either."""
    lock = get_redis_client().lock(BACKFILL_LOCK_KEY, timeout=30)
    assert lock.acquire(blocking=False)
    try:
        with patch("compass.ingestion.tasks.generate_embeddings_task") as embeddings:
            backfill_historical_task()

        embeddings.delay.assert_not_called()
    finally:
        lock.release()
