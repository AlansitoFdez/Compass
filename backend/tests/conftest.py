import asyncio
import sys
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from compass.core.db import async_session_factory
from compass.main import app

if sys.platform == "win32":
    # psycopg's async mode requires a selector-based event loop; Windows'
    # default ProactorEventLoop is incompatible with it (see alembic/env.py
    # for the same fix applied to migrations). Not a concern in production
    # (Linux containers use a selector-based loop already).
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    """A real DB session, rolled back after the test so nothing persists."""
    async with async_session_factory() as session:
        yield session
        await session.rollback()
