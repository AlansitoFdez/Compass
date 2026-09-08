"""Async database engine, session factory, and declarative base for ORM models."""

import logging
from collections.abc import AsyncIterator
from typing import Any

import psycopg
from pgvector.psycopg import register_vector_async
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from compass.core.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base every ORM model inherits from.

    Its `metadata` is the single registry of tables that Alembic's
    `--autogenerate` diffs against the live database, which is why
    `alembic/env.py` must import each model module for its table to be seen.
    """


def _async_database_url(database_url: str) -> str:
    """SQLAlchemy needs the psycopg3 dialect explicit, or it defaults to psycopg2."""
    return database_url.replace("postgresql://", "postgresql+psycopg://", 1)


def _register_vector_codec(engine: AsyncEngine) -> AsyncEngine:
    """Registers pgvector's `vector` type codec on every new connection `engine` opens.

    Without this, psycopg doesn't know how to read/write Postgres's `vector`
    type at all -- not a pgvector-specific quirk, every custom Postgres type
    needs its codec registered before psycopg can use it -- and any query
    touching `Tender.title_embedding` fails with `UnknownTypeError`. The
    `connect` event fires once per new DBAPI connection, so this runs on the
    raw connection itself (`dbapi_connection`), not `engine`.

    Tolerates the extension not existing yet: this same engine is what
    Alembic's `env.py` reuses to run migrations, including the very first
    one (2.5) that runs `CREATE EXTENSION vector` in the first place. Without
    the try/except, that bootstrap migration could never connect at all.
    """

    @event.listens_for(engine.sync_engine, "connect")
    def _on_connect(dbapi_connection: Any, _connection_record: Any) -> None:
        try:
            dbapi_connection.run_async(register_vector_async)
        except psycopg.ProgrammingError:
            logger.warning("pgvector extension not installed yet -- skipping type registration")

    return engine


_database_url = _async_database_url(get_settings().database_url)
engine = _register_vector_codec(create_async_engine(_database_url))
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
    task_engine = create_async_engine(
        _async_database_url(get_settings().database_url), poolclass=NullPool
    )
    return _register_vector_codec(task_engine)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, via `Depends(get_db)`."""
    async with async_session_factory() as session:
        yield session
