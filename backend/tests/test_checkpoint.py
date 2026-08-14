"""Tests for the ATOM ingestion checkpoint, against the real Redis instance."""

from collections.abc import Iterator

import pytest

from compass.ingestion.checkpoint import (
    clear_last_processed_atom_url,
    get_last_processed_atom_url,
    set_last_processed_atom_url,
)


@pytest.fixture(autouse=True)
def _clean_checkpoint() -> Iterator[None]:
    clear_last_processed_atom_url()
    yield
    clear_last_processed_atom_url()


def test_get_last_processed_atom_url_returns_none_when_unset() -> None:
    assert get_last_processed_atom_url() is None


def test_set_then_get_returns_the_same_url() -> None:
    set_last_processed_atom_url("https://example.com/page-2.atom")

    assert get_last_processed_atom_url() == "https://example.com/page-2.atom"


def test_clear_removes_the_checkpoint() -> None:
    set_last_processed_atom_url("https://example.com/page-2.atom")
    clear_last_processed_atom_url()

    assert get_last_processed_atom_url() is None
