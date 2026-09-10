"""Shared pytest fixtures: a real-app test client and a rollback-backed real DB session."""

import asyncio
import os
import sys
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from compass.core.db import async_session_factory
from compass.main import app

# Set before any test can construct compass.analysis.tracing.get_langfuse_client():
# the Langfuse SDK ANDs its own `tracing_enabled` constructor default with this env
# var, so this disables real network activity for the whole test session without
# touching how the client is built. Same reasoning as mocking every OpenRouter call
# in tests instead of hitting it for real -- a test run shouldn't write synthetic
# traces into Alan's real Langfuse project.
os.environ.setdefault("LANGFUSE_TRACING_ENABLED", "false")

if sys.platform == "win32":
    # psycopg's async mode requires a selector-based event loop; Windows'
    # default ProactorEventLoop is incompatible with it (see alembic/env.py
    # for the same fix applied to migrations). Not a concern in production
    # (Linux containers use a selector-based loop already).
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture
def client() -> TestClient:
    """A client against the real app -- routes exercised end-to-end, nothing mocked out."""
    return TestClient(app)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    """A real DB session, rolled back after the test so nothing persists."""
    async with async_session_factory() as session:
        yield session
        await session.rollback()
