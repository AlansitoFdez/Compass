"""The process-wide Langfuse client for the pliego analysis graph (Fase 4)."""

from functools import lru_cache

from langfuse import Langfuse

from compass.core.config import get_settings


@lru_cache
def get_langfuse_client() -> Langfuse:
    """Builds (once) the Langfuse client from validated settings.

    Constructed explicitly from `Settings` -- not `langfuse.get_client()` with no
    arguments -- so it reads `LANGFUSE_*` through `compass.core.config`'s already-proven
    `.env` loading path, instead of depending on those same variables also being
    exported into the raw process environment (pydantic-settings reads `.env` into the
    `Settings` model; it doesn't set `os.environ`, and nothing else in this project
    does either).

    Langfuse's own single-project singleton behavior means this is the only place a
    client gets constructed: every later `langfuse.get_client()` call (including the
    one `langfuse.langchain.CallbackHandler()` makes internally) returns this same
    instance instead of building a second one.

    Returns:
        The shared Langfuse client for this process.
    """
    settings = get_settings()
    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        base_url=settings.langfuse_base_url,
    )
