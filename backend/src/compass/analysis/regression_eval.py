"""Regression gate for the 4.3 golden set (25 pliegos): extraction correctness
(`scoring.score_extraction`, 3.4) and citation faithfulness (`verification.
citation_faithfulness`, 3.5) against the production model, over the real
`analyze_pliego` graph (3.6) -- not a hand-rolled `extract_structured` call like
`extraction_eval.py`'s 3.4 candidate comparison.

Running the real graph, not a parallel reimplementation, is the point: this script
exists to catch a regression the next time the prompt, the model, or the chunking
changes (phase4.md), and a hand-rolled call could pass while the actual production
path (retry policy, timeout, `NOT_ANALYZABLE` routing) silently regressed. Calls
`analyze_pliego` directly rather than `tasks.analyze_tender`, whose `pdf_hash` cache
would return the *previous* run's cached result for an unchanged PCAP -- exactly the
kind of change this script needs to see.

Not RAGAS the library: both metrics are already built by hand (3.4/3.5) and
generalized here to the full set, per phase4.md's planning decision -- the library's
own metrics (context precision/recall) don't apply without a retrieval step.
"""

import asyncio
import time
from dataclasses import dataclass, field

import httpx2
from sqlalchemy import select

from compass.analysis.enums import AnalysisStatus
from compass.analysis.extraction_schema import PliegoExtraction
from compass.analysis.golden_set import GOLDEN_SET
from compass.analysis.graph import analyze_pliego
from compass.analysis.scoring import FieldCheck, score_extraction
from compass.core.config import require_openrouter_key
from compass.core.db import async_session_factory
from compass.tenders.models import Tender

# Strictly sequential, not merely "limited": a first version ran 4 in flight and
# 10/25 documents timed out at the production 300s cap. The real cause (confirmed
# against OpenRouter's own request log, 4.4) turned out to be the free `:free` tier's
# 50-requests/day cap, not contention -- but concurrency also has nothing to
# recommend it here: Celery's own `--pool=solo` on Windows runs one task at a time,
# so a concurrent eval never reflects production load anyway.
_QUOTA_ERROR_MARKER = "429"


@dataclass
class DocumentResult:
    expediente: str
    status: AnalysisStatus | None = None
    checks: list[FieldCheck] = field(default_factory=list)
    faithfulness: float | None = None
    error: str | None = None


async def _fetch_pcap_urls(expedientes: list[str]) -> dict[str, str | None]:
    async with async_session_factory() as session:
        result = await session.execute(
            select(Tender.expediente, Tender.pcap_url).where(Tender.expediente.in_(expedientes))
        )
        return {row.expediente: row.pcap_url for row in result}


async def _evaluate_one(
    expediente: str,
    expected: PliegoExtraction,
    pcap_url: str | None,
    api_key: str,
    client: httpx2.AsyncClient,
) -> DocumentResult:
    if pcap_url is None:
        return DocumentResult(expediente=expediente, error="no pcap_url found in the database")

    started = time.monotonic()
    print(f"  {expediente}: starting...", flush=True)
    state = await analyze_pliego(pcap_url, api_key=api_key, client=client)
    elapsed = time.monotonic() - started
    print(f"  {expediente}: done in {elapsed:.0f}s (status={state['status']})", flush=True)

    result = DocumentResult(expediente=expediente, status=state["status"])
    if state["status"] == AnalysisStatus.COMPLETED:
        extraction = state["extraction"]
        assert extraction is not None
        result.checks = score_extraction(expected, extraction)
        result.faithfulness = state["citation_faithfulness"]
    else:
        result.error = state.get("error_message") or f"status={state['status']}"
    return result


async def _main() -> None:
    pcap_urls = await _fetch_pcap_urls(list(GOLDEN_SET.keys()))
    results: list[DocumentResult] = []
    skipped: list[str] = []

    async with httpx2.AsyncClient(timeout=300.0, follow_redirects=True) as client:
        items = list(GOLDEN_SET.items())
        for index, (expediente, expected) in enumerate(items):
            result = await _evaluate_one(
                expediente, expected, pcap_urls.get(expediente), require_openrouter_key(), client
            )
            results.append(result)
            if result.error and _QUOTA_ERROR_MARKER in result.error:
                skipped = [e for e, _ in items[index + 1 :]]
                print(
                    f"\n  {expediente} hit a {_QUOTA_ERROR_MARKER} response -- OpenRouter's "
                    f"free-tier daily quota is almost certainly exhausted (4.4's finding: "
                    f"50 requests/day on `:free` models). Stopping here instead of burning "
                    f"through the remaining {len(skipped)} documents on more of the same "
                    f"error; re-run tomorrow once the quota resets.",
                    flush=True,
                )
                break

    print(f"\n{'=' * 60}\nPER-DOCUMENT RESULTS\n{'=' * 60}")
    for r in sorted(results, key=lambda r: r.expediente):
        if r.error:
            print(f"  {r.expediente}: ERROR {r.error}")
            continue
        correct = sum(1 for c in r.checks if c.correct)
        print(
            f"  {r.expediente}: {correct}/{len(r.checks)} fields correct, "
            f"faithfulness={r.faithfulness:.0%}"
        )
        for c in r.checks:
            if not c.correct:
                print(f"    WRONG {c.name}: expected={c.expected!r} got={c.got!r}")

    completed = [r for r in results if r.status == AnalysisStatus.COMPLETED]
    total_correct = sum(1 for r in completed for c in r.checks if c.correct)
    total_checks = sum(len(r.checks) for r in completed)
    faithfulness_scores = [r.faithfulness for r in completed if r.faithfulness is not None]
    errored = [r for r in results if r.error]

    print(f"\n{'=' * 60}\nAGGREGATE\n{'=' * 60}")
    print(f"  documents completed: {len(completed)}/{len(GOLDEN_SET)}")
    if total_checks:
        pct = total_correct / total_checks
        print(f"  EXTRACTION CORRECTNESS: {total_correct}/{total_checks} ({pct:.0%})")
    if faithfulness_scores:
        avg_faithfulness = sum(faithfulness_scores) / len(faithfulness_scores)
        print(
            f"  CITATION FAITHFULNESS: {avg_faithfulness:.0%} avg over "
            f"{len(faithfulness_scores)} documents"
        )
    if errored:
        print(f"  {len(errored)}/{len(GOLDEN_SET)} documents errored or were not analyzable:")
        for r in errored:
            print(f"    {r.expediente}: {r.error}")
    if skipped:
        print(f"  {len(skipped)}/{len(GOLDEN_SET)} documents skipped (quota exhausted): {skipped}")


if __name__ == "__main__":
    asyncio.run(_main(), loop_factory=asyncio.SelectorEventLoop)
