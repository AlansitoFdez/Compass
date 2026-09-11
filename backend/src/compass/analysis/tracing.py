"""The process-wide Langfuse client for the pliego analysis graph (Fase 4)."""

import logging
from functools import lru_cache

from langfuse import Langfuse

from compass.core.config import get_settings

logger = logging.getLogger(__name__)

# Not a confidentiality control -- a PCAP is a public PLACSP document, nothing this
# graph handles is secret. It exists because LangGraph's CallbackHandler (4.1) traces
# every node's full input/output automatically, and `PliegoAnalysisState["pages"]`
# carries the entire page-by-page PCAP text -- without this, every trace would
# duplicate tens of thousands of characters of PDF text per node, for no benefit over
# reading the actual PDF. Citation quotes and descriptions in the final extraction
# (a few hundred characters at most) pass through untouched.
_MAX_TRACED_STRING_LENGTH = 500


def _mask_long_text(*, data: object, **_: object) -> object:
    """Langfuse `mask` hook (4.5): truncates long strings anywhere in a traced payload.

    Recurses into dicts/lists so a truncation applies wherever a long string is
    nested (e.g. `PliegoAnalysisState["pages"]`, a list of one string per page),
    not just at the top level of whatever Langfuse hands this.
    """
    if isinstance(data, str):
        if len(data) <= _MAX_TRACED_STRING_LENGTH:
            return data
        return f"{data[:_MAX_TRACED_STRING_LENGTH]}... [{len(data)} caracteres, truncado]"
    if isinstance(data, dict):
        return {key: _mask_long_text(data=value) for key, value in data.items()}
    if isinstance(data, list):
        return [_mask_long_text(data=item) for item in data]
    return data


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

    Tracing is optional (5.4). Compass is downloaded and run on the user's own machine,
    and asking someone who just wants to see it work for a second account somewhere else
    is a tax on curiosity -- so with no `LANGFUSE_*` keys the client is built with tracing
    disabled instead of the process refusing to start. Every observation then becomes a
    no-op, which is why `analysis.graph` can go on calling this unconditionally and knows
    nothing about whether tracing is configured.

    Returns:
        The shared Langfuse client for this process, tracing disabled if unconfigured.
    """
    settings = get_settings()
    configured = bool(settings.langfuse_public_key and settings.langfuse_secret_key)
    if not configured:
        logger.info(
            "Langfuse no está configurado: el análisis funciona igual, sin trazas. "
            "Añade LANGFUSE_PUBLIC_KEY y LANGFUSE_SECRET_KEY al .env para activarlas."
        )
    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        base_url=settings.langfuse_base_url,
        mask=_mask_long_text,
        tracing_enabled=configured,
    )
