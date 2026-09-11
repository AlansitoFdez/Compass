"""Serves the API: `uv run python -m compass`.

Exists for one reason, and it isn't convenience. psycopg's async mode refuses to run on
Windows' default `ProactorEventLoop` -- every endpoint that touches Postgres answers 500
with `InterfaceError`. Every other entry point in the project already fixes this by
choosing a selector loop (`alembic/env.py`, the three Celery tasks, `providers.seed`,
`tests/conftest.py`); serving the API was the only one that didn't.

Setting the global event loop policy wouldn't have helped, which is the part worth
writing down: `uvicorn.Server.run()` passes `config.get_loop_factory()` explicitly to
`asyncio.run`, and on Windows that factory is hardcoded to `ProactorEventLoop` unless
uvicorn is spawning a subprocess (`uvicorn/loops/asyncio.py`). An explicit factory beats
any policy, so the only way to choose the loop is to run the server ourselves -- which is
all this module does.

That `use_subprocess` exception is also why `uvicorn compass.main:app --reload` worked
while the same command without `--reload` did not: the reloader spawns a subprocess, and
the subprocess branch returns `SelectorEventLoop`. The API served traffic correctly only
as a side effect of running in development mode.
"""

import argparse
import asyncio
import sys
from collections.abc import Callable

import uvicorn

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def loop_factory(config: uvicorn.Config) -> Callable[[], asyncio.AbstractEventLoop] | None:
    """The event loop `serve()` must run on for this platform.

    Args:
        config: The uvicorn configuration the server was built from.

    Returns:
        `SelectorEventLoop` on Windows -- the only loop psycopg's async mode accepts --
        and whatever uvicorn would have picked for itself everywhere else, so a Linux
        install keeps using uvloop exactly as before.
    """
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop
    return config.get_loop_factory()


def main() -> None:
    """Parses the command line and serves the API until interrupted."""
    parser = argparse.ArgumentParser(prog="compass", description="Serve the Compass API.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--reload", action="store_true", help="Reload on source changes (development)."
    )
    args = parser.parse_args()

    if args.reload:
        # Delegated to uvicorn untouched: the reloader needs to own the process tree, and
        # its subprocess branch already picks a selector loop, so there is nothing to fix
        # on this path.
        uvicorn.run("compass.main:app", host=args.host, port=args.port, reload=True)
        return

    config = uvicorn.Config("compass.main:app", host=args.host, port=args.port)
    server = uvicorn.Server(config)
    asyncio.run(server.serve(), loop_factory=loop_factory(config))


if __name__ == "__main__":
    main()
