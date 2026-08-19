"""Tests for the ATOM ingestion checkpoint, against the real Redis instance."""

from collections.abc import Iterator

import pytest

from compass.ingestion.checkpoint import (
    clear_high_water_mark,
    clear_last_processed_atom_url,
    clear_pending_high_water_mark,
    complete_run,
    get_high_water_mark,
    get_last_processed_atom_url,
    get_pending_high_water_mark,
    set_last_processed_atom_url,
    set_pending_high_water_mark,
)


@pytest.fixture(autouse=True)
def _clean_checkpoint() -> Iterator[None]:
    clear_last_processed_atom_url()
    clear_high_water_mark()
    clear_pending_high_water_mark()
    yield
    clear_last_processed_atom_url()
    clear_high_water_mark()
    clear_pending_high_water_mark()


def test_get_last_processed_atom_url_returns_none_when_unset() -> None:
    assert get_last_processed_atom_url() is None


def test_set_then_get_returns_the_same_url() -> None:
    set_last_processed_atom_url("https://example.com/page-2.atom")

    assert get_last_processed_atom_url() == "https://example.com/page-2.atom"


def test_clear_removes_the_checkpoint() -> None:
    set_last_processed_atom_url("https://example.com/page-2.atom")
    clear_last_processed_atom_url()

    assert get_last_processed_atom_url() is None


def test_get_high_water_mark_returns_none_when_unset() -> None:
    assert get_high_water_mark() is None


def test_complete_run_promotes_the_pending_mark_and_clears_per_run_state() -> None:
    set_last_processed_atom_url("https://example.com/page-2.atom")
    set_pending_high_water_mark("2026-08-19T12:00:00+02:00")

    complete_run()

    assert get_high_water_mark() == "2026-08-19T12:00:00+02:00"
    assert get_last_processed_atom_url() is None
    assert get_pending_high_water_mark() is None


def test_complete_run_without_a_pending_mark_leaves_the_high_water_mark_untouched() -> None:
    """A run that never found any entries (nothing new since last time) has
    nothing to promote — the existing high-water mark, if any, must not move.
    """
    set_pending_high_water_mark("2026-08-19T12:00:00+02:00")
    complete_run()
    assert get_high_water_mark() == "2026-08-19T12:00:00+02:00"

    set_last_processed_atom_url("https://example.com/page-2.atom")
    complete_run()

    assert get_high_water_mark() == "2026-08-19T12:00:00+02:00"
    assert get_last_processed_atom_url() is None
