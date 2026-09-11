"""Tests for the pure shaping/averaging logic behind the 4.2 cost report -- not the
live Langfuse queries, which `uv run python -m compass.analysis.cost_report` makes on
demand to refresh the README's real numbers.
"""

from compass.analysis.cost_report import (
    AnalysisCostSummary,
    _build_summary,
    average,
    merge_attempts,
)


def test_build_summary_reads_the_real_fields() -> None:
    """Protects the field mapping against Langfuse's own key names -- usage_details
    uses input/output/total, not prompt_tokens/completion_tokens/total_tokens.
    """
    summary = _build_summary(
        trace_id="t1",
        usage_details={"input": 100, "output": 20, "total": 120},
        cost_details={"total": 0.0042},
        end_to_end_latency_s=190.5,
    )

    assert summary == AnalysisCostSummary(
        trace_id="t1",
        input_tokens=100,
        output_tokens=20,
        total_tokens=120,
        cost_eur=0.0042,
        end_to_end_latency_s=190.5,
    )


def test_build_summary_zeroes_missing_data_instead_of_raising() -> None:
    """Protects against a generation with no usage/cost recorded (shouldn't happen for
    a real completed run, but this report has no business crashing over it) and a
    trace with no matching `analyze_pliego` span found.
    """
    summary = _build_summary(
        trace_id="t2", usage_details=None, cost_details=None, end_to_end_latency_s=None
    )

    assert summary == AnalysisCostSummary(
        trace_id="t2",
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
        cost_eur=0.0,
        end_to_end_latency_s=0.0,
    )


def test_average_is_a_real_mean_not_a_sum() -> None:
    """Protects that averaging two different real runs lands on their actual mean."""
    summaries = [
        AnalysisCostSummary(
            trace_id="t1",
            input_tokens=32985,
            output_tokens=8739,
            total_tokens=41724,
            cost_eur=0.0,
            end_to_end_latency_s=194.4,
        ),
        AnalysisCostSummary(
            trace_id="t2",
            input_tokens=93834,
            output_tokens=12693,
            total_tokens=106527,
            cost_eur=0.0,
            end_to_end_latency_s=285.1,
        ),
    ]

    stats = average(summaries)

    assert stats["total_tokens"] == (41724 + 106527) / 2
    assert stats["cost_eur"] == 0.0
    assert stats["end_to_end_latency_s"] == (194.4 + 285.1) / 2


def test_average_of_no_summaries_is_empty_not_a_division_by_zero() -> None:
    """Protects the empty-corpus case: nothing to average yet, not a crash."""
    assert average([]) == {}


def test_merge_attempts_sums_a_retried_extraction_into_one_analysis() -> None:
    """Protects the 4.7 fix: the `extract` node retries once, and Langfuse records each
    attempt as its own generation -- so without merging, one analysis showed up twice
    and the "coste medio por análisis" was really a mean per model call.

    Tokens and cost add up (both attempts were really spent); latency is the trace's
    own end-to-end figure, which already covers both, so it is taken, not summed.
    """
    attempts = [
        AnalysisCostSummary(
            trace_id="t1",
            input_tokens=30000,
            output_tokens=5000,
            total_tokens=35000,
            cost_eur=0.002,
            end_to_end_latency_s=280.0,
        ),
        AnalysisCostSummary(
            trace_id="t1",
            input_tokens=30000,
            output_tokens=7000,
            total_tokens=37000,
            cost_eur=0.003,
            end_to_end_latency_s=280.0,
        ),
    ]

    merged = merge_attempts(attempts)

    assert merged == AnalysisCostSummary(
        trace_id="t1",
        input_tokens=60000,
        output_tokens=12000,
        total_tokens=72000,
        cost_eur=0.005,
        end_to_end_latency_s=280.0,
        attempts=2,
    )


def test_produced_usage_separates_real_analyses_from_calls_that_never_returned() -> None:
    """Protects the honesty of the headline number (4.7).

    43 of 77 real `extract` generations in the project had no tokens recorded -- the
    timeouts and OpenRouter 429s of 4.4's regression runs. Averaging their zeros in
    dragged the reported mean cost per analysis down to a meaningless figure.
    """
    completed = AnalysisCostSummary(
        trace_id="t1",
        input_tokens=32985,
        output_tokens=8739,
        total_tokens=41724,
        cost_eur=0.0,
        end_to_end_latency_s=194.4,
    )
    never_returned = AnalysisCostSummary(
        trace_id="t2",
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
        cost_eur=0.0,
        end_to_end_latency_s=309.0,
    )

    assert completed.produced_usage
    assert not never_returned.produced_usage
