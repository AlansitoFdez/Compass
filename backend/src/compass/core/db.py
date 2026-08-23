"""Async database engine, session factory, and declarative base for ORM models."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from compass.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base every ORM model inherits from.

    Its `metadata` is the single registry of tables that Alembic's
    `--autogenerate` diffs against the live database, which is why
    `alembic/env.py` must import each model module for its table to be seen.
    """


def _async_database_url(database_url: str) -> str:
    """SQLAlchemy needs the psycopg3 dialect explicit, or it defaults to psycopg2."""
    return database_url.replace("postgresql://", "postgresql+psycopg://", 1)


engine = create_async_engine(_async_database_url(get_settings().database_url))
async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, expire_on_commit=False
)


def create_task_engine() -> AsyncEngine:
    """Fresh NullPool engine for a single asyncio.run() call inside a Celery task.

    `engine` above pools connections for FastAPI's one long-lived event loop.
    Celery tasks get a brand new event loop per asyncio.run() call — a
    connection pooled under one event loop is invalid in another — so tasks
    need their own unpooled engine, built fresh each time, not this shared one.
    """
    return create_async_engine(_async_database_url(get_settings().database_url), poolclass=NullPool)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, via `Depends(get_db)`."""
    async with async_session_factory() as session:
        yield session
