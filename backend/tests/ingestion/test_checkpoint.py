"""Tests for the ATOM ingestion checkpoint, against the real Redis instance."""

from collections.abc import Iterator

import pytest

from compass.ingestion.checkpoint import (
    clear_high_water_mark,
    clear_pending_high_water_mark,
    clear_resume_url,
    complete_run,
    get_high_water_mark,
    get_pending_high_water_mark,
    get_resume_url,
    set_pending_high_water_mark,
    set_resume_url,
)


@pytest.fixture(autouse=True)
def _clean_checkpoint() -> Iterator[None]:
    """Wipes every checkpoint key before and after each test.

    So tests can't see each other's leftover state.
    """
    clear_resume_url()
    clear_high_water_mark()
    clear_pending_high_water_mark()
    yield
    clear_resume_url()
    clear_high_water_mark()
    clear_pending_high_water_mark()


def test_get_resume_url_returns_none_when_unset() -> None:
    """Protects a fresh-start read: no key in Redis means `None`, not an exception."""
    assert get_resume_url() is None


def test_set_then_get_returns_the_same_url() -> None:
    """Protects the basic round-trip through Redis, unencoded."""
    set_resume_url("https://example.com/page-2.atom")

    assert get_resume_url() == "https://example.com/page-2.atom"


def test_clear_removes_the_checkpoint() -> None:
    """Protects that clearing actually deletes the key, not just sets it empty."""
    set_resume_url("https://example.com/page-2.atom")
    clear_resume_url()

    assert get_resume_url() is None


def test_get_high_water_mark_returns_none_when_unset() -> None:
    """Protects the very first run ever: no prior checkpoint means `None`, not an exception."""
    assert get_high_water_mark() is None


def test_complete_run_promotes_the_pending_mark_and_clears_per_run_state() -> None:
    """Protects the two-phase commit: pending becomes the real mark, and per-run state is wiped."""
    set_resume_url("https://example.com/page-2.atom")
    set_pending_high_water_mark("2026-08-19T12:00:00+02:00")

    complete_run()

    assert get_high_water_mark() == "2026-08-19T12:00:00+02:00"
    assert get_resume_url() is None
    assert get_pending_high_water_mark() is None


def test_complete_run_without_a_pending_mark_leaves_the_high_water_mark_untouched() -> None:
    """A run that never found any entries (nothing new since last time) has
    nothing to promote — the existing high-water mark, if any, must not move.
    """
    set_pending_high_water_mark("2026-08-19T12:00:00+02:00")
    complete_run()
    assert get_high_water_mark() == "2026-08-19T12:00:00+02:00"

    set_resume_url("https://example.com/page-2.atom")
    complete_run()

    assert get_high_water_mark() == "2026-08-19T12:00:00+02:00"
    assert get_resume_url() is None
