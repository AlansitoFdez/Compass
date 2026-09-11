"""Tests for `python -m compass`, the entry point that serves the API.

Lives at the root of `tests/` rather than in a subpackage because `compass.__main__`
isn't part of any domain -- it's how the process starts, the same way `conftest.py` sits
here for being shared by all four.
"""

import asyncio
from unittest.mock import patch

import uvicorn

from compass.__main__ import loop_factory


def test_windows_gets_a_selector_loop() -> None:
    """Protects the reason this module exists at all: psycopg's async mode refuses to run
    on Windows' default `ProactorEventLoop`, so every endpoint touching Postgres answered
    500 when the API was served as `uvicorn compass.main:app` without `--reload`.

    Asserted against `sys.platform` patched to win32 rather than skipped off Windows: the
    choice is what's under test, and it has to stay pinned when CI runs on Linux -- which
    is precisely where nobody would notice it regressing.
    """
    config = uvicorn.Config("compass.main:app")

    with patch("compass.__main__.sys.platform", "win32"):
        factory = loop_factory(config)

    assert factory is asyncio.SelectorEventLoop


def test_other_platforms_keep_uvicorns_own_choice() -> None:
    """Protects the other half: the Windows fix must not take uvloop away from a Linux
    install, which is where this actually runs in production.
    """
    config = uvicorn.Config("compass.main:app")
    sentinel = object()

    with (
        patch("compass.__main__.sys.platform", "linux"),
        patch.object(config, "get_loop_factory", return_value=sentinel),
    ):
        factory = loop_factory(config)

    assert factory is sentinel


def test_the_default_host_is_loopback_only() -> None:
    """Protects a deliberate default: Compass runs on the machine of whoever uses it, so
    the API has no reason to accept connections from the rest of the network -- and it
    has no authentication to survive doing so.
    """
    from compass.__main__ import DEFAULT_HOST

    assert DEFAULT_HOST == "127.0.0.1"
