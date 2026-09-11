"""Alembic migration runner, wired to the app's own async engine and models."""

import asyncio
import sys
from logging.config import fileConfig

from sqlalchemy.engine import Connection

from alembic import context
from compass.analysis import models as analysis_models  # noqa: F401 — registers TenderAnalysis
from compass.core.db import Base, engine
from compass.providers import models as providers_models  # noqa: F401 — registers Provider
from compass.tenders import models  # noqa: F401 — registers Tender on Base.metadata

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    # render_as_string(hide_password=False), not str(): str() masks the password as
    # "***", so the SQL this mode emits would carry a URL that cannot connect.
    url = engine.url.render_as_string(hide_password=False)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Runs pending migrations synchronously over an already-open connection.

    Alembic's migration machinery is sync; `run_async_migrations()` bridges
    into it via `AsyncConnection.run_sync`, which is what hands this function
    a plain sync `Connection` despite the app using an async engine.
    """
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Reuse the app's own engine (compass.core.db) instead of building a
    second one from alembic.ini — one source of truth for the connection.
    """

    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await engine.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    if sys.platform == "win32":
        # psycopg's async mode requires a selector-based event loop; Windows'
        # default ProactorEventLoop is incompatible with it. Not a concern in
        # production (Linux containers use a selector-based loop already).
        asyncio.run(run_async_migrations(), loop_factory=asyncio.SelectorEventLoop)
    else:
        asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
