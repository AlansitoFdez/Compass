"""Tests for which settings are required and which are not.

That split is a product decision, not a detail: Compass is downloaded and run on the
user's own machine, so every extra key it demands before starting is a reason for someone
to give up before seeing it work.
"""

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from compass.analysis.tracing import get_langfuse_client
from compass.core.config import Settings

_MINIMUM_ENVIRONMENT = {
    "DATABASE_URL": "postgresql://u:p@localhost:5432/db",
    "REDIS_URL": "redis://localhost:6379/0",
    "OPENROUTER_API_KEY": "test-key",
}


def _settings(**environment: str) -> Settings:
    """Builds `Settings` from exactly `environment`, ignoring the developer's own .env."""
    with patch.dict("os.environ", {**_MINIMUM_ENVIRONMENT, **environment}, clear=True):
        # _env_file=None: without it pydantic-settings would read the real .env sitting in
        # backend/, and the test would pass because of Alan's own keys rather than because
        # of what it asserts.
        return Settings(_env_file=None)


def test_langfuse_is_optional() -> None:
    """Protects the decision itself: someone who only wants to try Compass must not be
    asked for a second account somewhere else before the process will start.
    """
    settings = _settings()

    assert settings.langfuse_public_key is None
    assert settings.langfuse_secret_key is None


def test_the_openrouter_key_is_required() -> None:
    """The other half of the same decision: this one *is* demanded, because without it the
    analyst agent has nothing to call and the product cannot do what it promises.
    """
    with patch.dict("os.environ", {}, clear=True), pytest.raises(ValidationError) as error:
        Settings(
            _env_file=None,
            database_url="postgresql://u:p@localhost:5432/db",
            redis_url="redis://localhost:6379/0",
        )

    assert "openrouter_api_key" in str(error.value)


def _tracing_enabled_for(**environment: str) -> bool:
    """What `get_langfuse_client` decides to pass the SDK for this environment.

    Asserted on the argument rather than on the built client's state, because
    `conftest.py` sets `LANGFUSE_TRACING_ENABLED=false` for the whole session -- so no
    test run can ever produce an enabled client, and reading one back would only be
    re-testing that safeguard.
    """
    get_langfuse_client.cache_clear()
    try:
        settings = _settings(**environment)
        with (
            patch("compass.analysis.tracing.get_settings", return_value=settings),
            patch("compass.analysis.tracing.Langfuse") as langfuse,
        ):
            get_langfuse_client()
        enabled: bool = langfuse.call_args.kwargs["tracing_enabled"]
        return enabled
    finally:
        # The client is process-wide and cached; leaving this test's mock behind would
        # hand a `MagicMock` to whatever ran after it.
        get_langfuse_client.cache_clear()


def test_tracing_is_off_when_langfuse_is_unconfigured() -> None:
    """Protects what "optional" has to mean in practice: not a crash, and not a client
    that quietly tries to reach Langfuse anyway.

    `analysis.graph` opens observations unconditionally and knows nothing about whether
    tracing is configured, so the no-op has to be decided here or not at all.
    """
    assert _tracing_enabled_for() is False


def test_tracing_is_on_when_both_keys_are_present() -> None:
    """The other direction: with the keys configured tracing must actually come on --
    otherwise "optional" would silently mean "never".
    """
    assert _tracing_enabled_for(LANGFUSE_PUBLIC_KEY="pk-test", LANGFUSE_SECRET_KEY="sk-test")


def test_half_a_langfuse_configuration_stays_off() -> None:
    """One key without the other can't authenticate, so it must read as unconfigured
    rather than as an attempt that fails later, mid-analysis.
    """
    assert _tracing_enabled_for(LANGFUSE_PUBLIC_KEY="pk-test") is False
