"""Aggregates real cost/token/latency numbers from Langfuse, for the README's "coste
real de analizar un pliego" figure (Fase 4).

Not part of the analysis pipeline -- a reporting tool, run by hand whenever that
number needs refreshing against more accumulated production traces. Same spirit as
`extraction_eval.py`'s repeatable comparison script for the 3.4 model decision: a
script, not a subphase of the funnel itself.

Reads `observations.get_many` (the v2 API), not `trace.get`/`trace.list`: Langfuse's
own dashboard flagged those as deprecated during the 4.2 investigation, in favor of
this one. The default `fields` group on that endpoint omits `usageDetails`/
`costDetails`/`totalCost` entirely (it returns `core`+`basic` unless asked otherwise)
-- passing `fields="core,basic,usage,model,metrics"` explicitly is what makes those
appear at all; querying without it is why an earlier attempt in this same subphase
looked like the numbers were missing server-side, when they were just never requested.
"""

from dataclasses import dataclass

from compass.analysis.tracing import get_langfuse_client


@dataclass
class AnalysisCostSummary:
    """The real cost/tokens/latency of one production `analyze_pliego` run.

    One per *trace*, not per model call: the `extract` node retries once
    (`graph._EXTRACT_RETRY_POLICY`), and both attempts are part of what that single
    analysis cost. `attempts` says how many calls went into these numbers.
    """

    trace_id: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_eur: float
    end_to_end_latency_s: float
    attempts: int = 1

    @property
    def produced_usage(self) -> bool:
        """Whether any attempt in this trace came back with tokens recorded.

        False means the extraction never returned: the 4.7 review found 43 of 77
        `extract` generations in the real project like this, every one of them marked
        `level=ERROR` by Langfuse -- the timeouts and OpenRouter 429s of 4.4's
        regression runs. They are real attempts, but averaging their zeros into "what
        an analysis costs" answers a different question than the one the README asks.
        """
        return self.total_tokens > 0


def _build_summary(
    *,
    trace_id: str,
    usage_details: dict[str, int] | None,
    cost_details: dict[str, float] | None,
    end_to_end_latency_s: float | None,
) -> AnalysisCostSummary:
    """Shapes one `extract` generation's raw fields into a summary.

    Pure function over already-fetched primitives (not the SDK's response objects
    directly), so it's testable without a fake standing in for Langfuse's exact
    pydantic schema -- only the handful of fields this report actually uses.

    Args:
        trace_id: The parent `analyze_pliego` trace this generation belongs to.
        usage_details: `{"input": ..., "output": ..., "total": ...}`, or `None` if
            the generation somehow has none recorded.
        cost_details: `{"total": ...}`, or `None`.
        end_to_end_latency_s: The root `analyze_pliego` span's own latency, looked
            up by `trace_id` -- `None` if that span wasn't found (shouldn't happen
            for a real trace, but this report has no business crashing over it).

    Returns:
        The shaped summary, zeroed wherever the source data was missing.
    """
    usage = usage_details or {}
    cost = cost_details or {}
    return AnalysisCostSummary(
        trace_id=trace_id,
        input_tokens=usage.get("input", 0),
        output_tokens=usage.get("output", 0),
        total_tokens=usage.get("total", 0),
        cost_eur=cost.get("total", 0.0),
        end_to_end_latency_s=end_to_end_latency_s or 0.0,
    )


def merge_attempts(attempts: list[AnalysisCostSummary]) -> AnalysisCostSummary:
    """Folds every `extract` call of one trace into a single analysis summary.

    Args:
        attempts: Summaries sharing a `trace_id`, in any order. Never empty.

    Returns:
        One summary whose tokens and cost are the sum across attempts -- a retried
        extraction really did spend both -- and whose latency is the trace's own
        end-to-end figure, which already covers all of them (so it is taken, not
        added up).
    """
    first = attempts[0]
    return AnalysisCostSummary(
        trace_id=first.trace_id,
        input_tokens=sum(a.input_tokens for a in attempts),
        output_tokens=sum(a.output_tokens for a in attempts),
        total_tokens=sum(a.total_tokens for a in attempts),
        cost_eur=sum(a.cost_eur for a in attempts),
        end_to_end_latency_s=max(a.end_to_end_latency_s for a in attempts),
        attempts=len(attempts),
    )


def average(summaries: list[AnalysisCostSummary]) -> dict[str, float]:
    """The mean of every numeric field across `summaries`.

    Args:
        summaries: Real per-analysis summaries, from `collect_cost_summaries`.

    Returns:
        A dict with the same numeric keys as `AnalysisCostSummary`, each averaged --
        empty if `summaries` is empty (nothing to average, not a division by zero).
    """
    if not summaries:
        return {}
    n = len(summaries)
    return {
        "input_tokens": sum(s.input_tokens for s in summaries) / n,
        "output_tokens": sum(s.output_tokens for s in summaries) / n,
        "total_tokens": sum(s.total_tokens for s in summaries) / n,
        "cost_eur": sum(s.cost_eur for s in summaries) / n,
        "end_to_end_latency_s": sum(s.end_to_end_latency_s for s in summaries) / n,
    }


def collect_cost_summaries(limit: int = 100) -> list[AnalysisCostSummary]:
    """Fetches every real `extract` generation from Langfuse, one summary per analysis.

    Args:
        limit: Maximum number of generations to fetch -- the real corpus is small
            (one or two calls per on-demand analysis), so the default is generous,
            not tuned.

    Returns:
        One summary per real `analyze_pliego` trace, with its retries folded in.
    """
    client = get_langfuse_client()
    generations = client.api.observations.get_many(
        type="GENERATION", name="extract", fields="core,basic,usage,model,metrics", limit=limit
    ).data
    end_to_end_latency_by_trace = {
        span.trace_id: span.latency
        for span in client.api.observations.get_many(
            type="SPAN", name="analyze_pliego", fields="core,basic,metrics", limit=limit
        ).data
    }
    attempts_by_trace: dict[str, list[AnalysisCostSummary]] = {}
    for g in generations:
        attempts_by_trace.setdefault(g.trace_id, []).append(
            _build_summary(
                trace_id=g.trace_id,
                usage_details=g.usage_details,
                cost_details=g.cost_details,
                end_to_end_latency_s=end_to_end_latency_by_trace.get(g.trace_id),
            )
        )
    return [merge_attempts(attempts) for attempts in attempts_by_trace.values()]


def _main() -> None:
    summaries = collect_cost_summaries()
    if not summaries:
        print("Sin análisis reales todavía en Langfuse.")
        return

    measured = [s for s in summaries if s.produced_usage]
    unmeasured = [s for s in summaries if not s.produced_usage]

    for s in measured:
        retries = "" if s.attempts == 1 else f" [{s.attempts} intentos]"
        print(
            f"{s.trace_id}: {s.total_tokens} tokens "
            f"({s.input_tokens} in / {s.output_tokens} out), "
            f"{s.cost_eur:.4f} €, {s.end_to_end_latency_s:.0f}s{retries}"
        )

    stats = average(measured)
    print(
        f"\nMedia sobre {len(measured)} análisis con extracción completada: "
        f"{stats['total_tokens']:.0f} tokens, {stats['cost_eur']:.4f} €, "
        f"{stats['end_to_end_latency_s']:.0f}s"
    )
    if unmeasured:
        # Reported, never averaged in: these are real attempts whose call never
        # returned (the 300s cap of `graph._EXTRACT_TOTAL_TIMEOUT_SECONDS`, or
        # OpenRouter's free-tier 429s -- see 4.4). Folding their zeros into the mean
        # would answer "what does an attempt cost on average", not "what does
        # analyzing a pliego cost", which is the number the README quotes.
        print(
            f"Excluidos de la media: {len(unmeasured)} análisis sin tokens registrados "
            f"(la llamada nunca devolvió: tope de 300s o 429 de OpenRouter)."
        )


if __name__ == "__main__":
    _main()
