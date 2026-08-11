"""Async database engine, session factory, and declarative base for ORM models."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from compass.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _async_database_url(database_url: str) -> str:
    """SQLAlchemy needs the psycopg3 dialect explicit, or it defaults to psycopg2."""
    return database_url.replace("postgresql://", "postgresql+psycopg://", 1)


engine = create_async_engine(_async_database_url(get_settings().database_url))
async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, expire_on_commit=False
)
