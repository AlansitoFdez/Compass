"""LangGraph orchestration for a full pliego analysis -- fetch, detect, extract, verify.

Assembles the pure steps built in 3.2-3.5 (`document`, `extraction_schema`, `openrouter`,
`verification`) into one graph with its own state and its own error handling, instead of
the ad-hoc procedural chaining `extraction_eval.py` uses for the 3.4 model comparison.

Least privilege (see docs/phases/phase3/phase3.md): the `extract` node makes a single
structured-output call and has no tools bound at all -- no `bind_tools`, no file or
write access of any kind. It is not a ReAct-style tool-calling loop, so the "no write
tools" rule is trivially satisfied today; it is written down here so it stays true when
a future subphase gives the reader agent anything to call.

`analyze_pliego` never raises. `RetryPolicy` on the `extract` node retries the exact
transient failures `extraction_eval.py` retried by hand in 3.4/3.5 (a malformed
completion, an inline OpenRouter error, an HTTP error -- see phase3.5.md's real Nvidia
502 during that investigation); everything else -- a dead `pcap_url`, retries exhausted
-- is caught once at the graph's own boundary in `analyze_pliego` and turned into
`status=FAILED` with `error_message`, so a caller (the Celery task in 3.8) doesn't need
its own catch-all around this.
"""

import json
from dataclasses import dataclass
from typing import TypedDict, cast

import httpx2
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from langgraph.types import RetryPolicy
from pydantic import ValidationError

from compass.analysis.document import extract_pages, has_text_layer, hash_document
from compass.analysis.enums import AnalysisStatus
from compass.analysis.extraction_schema import PliegoExtraction
from compass.analysis.openrouter import OpenRouterError, extract_structured
from compass.analysis.verification import citation_faithfulness

# Decided in 3.4 against a real golden set: 100% of the 36 checks, faster than the
# other free-tier candidate on the same document (phase3.4.md).
EXTRACTION_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"

SYSTEM_PROMPT = (
    "Eres un analista experto en contratación pública española (LCSP). Se te da el "
    "texto completo de un pliego de cláusulas administrativas particulares (PCAP), "
    "página a página. Extrae únicamente lo que el texto dice explícitamente, con su "
    "cita exacta (número/identificador de cláusula tal como aparece en el texto, "
    "número de página, y una cita textual verbatim copiada del pliego). Si el pliego "
    "no aborda un campo, déjalo en null o lista vacía según corresponda -- no inventes "
    "ni asumas valores típicos de otros pliegos que no conoces."
)


def build_prompt(pages: list[str]) -> str:
    """The full PCAP text, one labeled block per page.

    Feeds the model the raw pages rather than `chunking.chunk_by_clause`'s output:
    3.4 found clause headers detected reliably in only 2 of 4 real golden-set PCAPs
    (see `extraction_eval.py`'s module docstring) -- a future chunking improvement,
    not something this step needs solved first.
    """
    return "\n\n".join(f"===== PÁGINA {i} =====\n{page}" for i, page in enumerate(pages, start=1))


class PliegoAnalysisState(TypedDict, total=False):
    """The graph's state -- built up one field at a time as each node runs.

    `total=False`: only `pcap_url` is present at `START`; every other field exists
    only once the node responsible for it has run, which is also why reads of a
    later field always follow the edge that guarantees it was set first.
    """

    pcap_url: str
    pdf_hash: str
    pages: list[str]
    status: AnalysisStatus
    extraction: PliegoExtraction | None
    citation_faithfulness: float | None
    error_message: str | None


@dataclass
class AnalysisContext:
    """Runtime dependencies for the graph, injected via LangGraph's `context` mechanism.

    Keeps `client`/`api_key` out of module-level state, which is what lets tests swap
    in an `httpx2.AsyncClient` backed by a `MockTransport` with no monkeypatching.
    """

    client: httpx2.AsyncClient
    api_key: str
    model: str = EXTRACTION_MODEL


async def _fetch(
    state: PliegoAnalysisState, runtime: Runtime[AnalysisContext]
) -> PliegoAnalysisState:
    """Downloads the pliego and extracts its per-page text.

    A dead/erroring `pcap_url` raises `httpx2.HTTPStatusError` here, uncaught -- it
    isn't retried (a 404 pcap_url won't start working on a second try), so it reaches
    `analyze_pliego`'s boundary and becomes `status=FAILED` directly.
    """
    response = await runtime.context.client.get(state["pcap_url"])
    response.raise_for_status()
    content = response.content
    return {"pdf_hash": hash_document(content), "pages": extract_pages(content)}


def _check_text_layer(state: PliegoAnalysisState) -> PliegoAnalysisState:
    """Marks the document `NOT_ANALYZABLE` if it has no real text layer -- v1 does no OCR."""
    if has_text_layer(state["pages"]):
        return {}
    return {"status": AnalysisStatus.NOT_ANALYZABLE}


def _route_after_text_layer_check(state: PliegoAnalysisState) -> str:
    """Ends the run for a scanned pliego instead of paying for an extraction call on it."""
    return END if state.get("status") == AnalysisStatus.NOT_ANALYZABLE else "extract"


async def _extract(
    state: PliegoAnalysisState, runtime: Runtime[AnalysisContext]
) -> PliegoAnalysisState:
    """Calls the extraction model and validates its output against the closed schema.

    Retried by the `extract` node's `RetryPolicy` (see module docstring) on the same
    failure modes `extraction_eval.py` retried by hand; not caught here.
    """
    prompt = build_prompt(state["pages"])
    response = await extract_structured(
        model=runtime.context.model,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=prompt,
        schema=PliegoExtraction,
        api_key=runtime.context.api_key,
        client=runtime.context.client,
    )
    return {"extraction": PliegoExtraction.model_validate_json(response.content)}


def _verify(state: PliegoAnalysisState) -> PliegoAnalysisState:
    """Scores citation faithfulness and marks the analysis complete."""
    extraction = state["extraction"]
    # Guaranteed by the graph's own edges: `verify` only ever runs after `extract`
    # has set this field, never after the `NOT_ANALYZABLE` shortcut.
    assert extraction is not None
    faithfulness = citation_faithfulness(extraction, state["pages"])
    return {"status": AnalysisStatus.COMPLETED, "citation_faithfulness": faithfulness}


# One retry, matching the evidence in phase3.4.md/phase3.5.md -- the free tier's
# observed hiccups (a real Nvidia 502, an occasional empty/malformed completion)
# resolved within a single retry there, so this doesn't guess at a larger budget.
_EXTRACT_RETRY_POLICY = RetryPolicy(
    max_attempts=2,
    retry_on=(OpenRouterError, httpx2.HTTPError, ValidationError, json.JSONDecodeError),
)


def _build_graph() -> CompiledStateGraph[
    PliegoAnalysisState, AnalysisContext, PliegoAnalysisState, PliegoAnalysisState
]:
    graph = StateGraph(PliegoAnalysisState, AnalysisContext)
    graph.add_node("fetch", _fetch)
    graph.add_node("check_text_layer", _check_text_layer)
    graph.add_node("extract", _extract, retry_policy=_EXTRACT_RETRY_POLICY)
    graph.add_node("verify", _verify)
    graph.add_edge(START, "fetch")
    graph.add_edge("fetch", "check_text_layer")
    graph.add_conditional_edges(
        "check_text_layer", _route_after_text_layer_check, {"extract": "extract", END: END}
    )
    graph.add_edge("extract", "verify")
    graph.add_edge("verify", END)
    return graph.compile()


_GRAPH = _build_graph()


async def analyze_pliego(
    pcap_url: str, *, api_key: str, client: httpx2.AsyncClient, model: str = EXTRACTION_MODEL
) -> PliegoAnalysisState:
    """Runs the full pliego analysis graph. Never raises -- see module docstring.

    Args:
        pcap_url: The tender's `pcap_url` to download and analyze.
        api_key: OpenRouter API key.
        client: The async HTTP client to fetch the PDF and call OpenRouter with.
        model: OpenRouter model slug to extract with.

    Returns:
        The graph's final state: `status` is always set, to `COMPLETED` (with
        `extraction`/`citation_faithfulness` populated), `NOT_ANALYZABLE`, or `FAILED`
        (with `error_message`).
    """
    context = AnalysisContext(client=client, api_key=api_key, model=model)
    try:
        result = await _GRAPH.ainvoke({"pcap_url": pcap_url}, context=context)
    except Exception as exc:  # deliberately broad: this call site *is* the graph's error boundary
        return {"pcap_url": pcap_url, "status": AnalysisStatus.FAILED, "error_message": str(exc)}
    # ainvoke's declared return type erases back to `dict[str, Any] | Any` regardless
    # of the state schema passed to `StateGraph` -- safe to narrow back here, since
    # every key it can contain is one our own nodes wrote.
    return cast(PliegoAnalysisState, result)
