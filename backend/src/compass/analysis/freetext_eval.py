"""Scores the extraction's free-text descriptions for faithfulness (5.6), with RAGAS.

The companion to `regression_eval.py`, and deliberately not part of it: that script gates
the nine mechanically-checkable fields plus citation verification, all of it in Python, so
it can afford the whole 25-pliego golden set. This one needs a judge model for every
sample, so it runs by hand over a handful of pliegos -- never in CI, never inside
`pytest`.

What it measures is the one question Python can't answer about a description: *is this in
the pliego, or did the model write it?* `verification.verify_citation` already proves the
quote is real; nothing proves the prose around it is. Faithfulness decomposes each
description into atomic claims and checks them one by one against the cited pages.

Extractions come from `tender_analyses`, already paid for -- re-extracting would spend the
day's quota on the half that isn't being evaluated. The pages come from the PCAP itself,
which costs nothing but a download.

**Two judge calls per sample**, by construction (statement generation, then NLI verdicts),
so the free tier's 50 requests/day is about three pliegos' worth of descriptions. The run
counts its own HTTP requests and prints the total, instructor's retries included.

Runs RAGAS' own `Faithfulness` prompts and its own ratio, but drives the two steps here
instead of calling `metric.ascore`: that returns the aggregate alone, and an eval nobody
can calibrate is not an eval. The per-statement verdicts and reasons -- which claim failed
and why -- are what let a person open the pliego and tell whether the judge was right.
"""

import argparse
import asyncio
import math
from dataclasses import dataclass, field
from typing import cast

import httpx2
from openai import AsyncOpenAI
from pydantic import ValidationError
from ragas.llms import llm_factory
from ragas.llms.base import InstructorBaseRagasLLM
from ragas.metrics.collections import Faithfulness
from ragas.metrics.collections.faithfulness.util import (
    NLIStatementInput,
    NLIStatementOutput,
    StatementGeneratorInput,
    StatementGeneratorOutput,
)
from sqlalchemy import select

from compass.analysis.document import download_pcap, extract_pages
from compass.analysis.enums import AnalysisStatus
from compass.analysis.extraction_schema import PliegoExtraction
from compass.analysis.freetext import FreeTextSample, SkippedDescription, build_samples
from compass.analysis.models import TenderAnalysis
from compass.core.config import require_openrouter_key
from compass.core.db import async_session_factory
from compass.tenders.models import Tender

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Not the extraction model (`graph.EXTRACTION_MODEL`): a model grading its own output
# tends to agree with itself. This is the other finalist of the 3.4 comparison, so it is
# already known to handle Spanish PCAP prose, and it is free -- the whole eval has to fit
# inside the same 50-requests/day budget as everything else.
DEFAULT_JUDGE_MODEL = "nex-agi/nex-n2.5-pro:free"

# A judge call reasons over ~3 pages of clause text on a free-tier queue; a stuck request
# would otherwise hang the run with nothing to show for the quota already spent.
JUDGE_TIMEOUT_SECONDS = 300.0

# Roughly what one pliego costs: 7 descriptions, 2 calls each, minus whatever the pliego
# doesn't address. Printed in `--help` so the budget is visible before spending it.
REQUESTS_PER_PLIEGO = 14

_QUOTA_ERROR_MARKER = "429"


class QuotaExhaustedError(Exception):
    """OpenRouter refused the call because the day's free-tier requests are gone."""


class RequestCounter:
    """Counts real HTTP requests to the judge, not the calls we meant to make.

    Instructor retries a malformed completion on its own, so counting `agenerate` calls
    would under-report exactly when the quota is draining fastest. Hooked into the OpenAI
    client's own transport instead, where every attempt is visible.
    """

    def __init__(self) -> None:
        self.count = 0

    async def __call__(self, request: httpx2.Request) -> None:
        self.count += 1


@dataclass
class FieldScore:
    """One description's faithfulness, with the per-claim verdicts behind the number."""

    field: str
    cited_page: int
    verdicts: NLIStatementOutput

    @property
    def total(self) -> int:
        return len(self.verdicts.statements)

    @property
    def supported(self) -> int:
        return sum(1 for statement in self.verdicts.statements if statement.verdict)

    @property
    def score(self) -> float:
        """The RAGAS faithfulness ratio: claims supported over claims made.

        `nan` when the judge found no claims at all -- the library's own convention, and
        a different thing from a description that made claims and failed them.
        """
        if not self.total:
            return math.nan
        return self.supported / self.total


@dataclass
class DocumentResult:
    """Everything one pliego contributed to the run."""

    expediente: str
    scores: list[FieldScore] = field(default_factory=list)
    skipped: list[SkippedDescription] = field(default_factory=list)
    error: str | None = None


@dataclass
class StoredAnalysis:
    """A completed analysis to evaluate, with the document it was extracted from."""

    expediente: str
    extraction: dict[str, object]
    pcap_url: str | None


async def _fetch_completed_analyses(limit: int, expediente: str | None) -> list[StoredAnalysis]:
    """The stored extractions to evaluate, most recently analyzed first."""
    stmt = (
        select(TenderAnalysis.expediente, TenderAnalysis.extraction, Tender.pcap_url)
        .join(Tender, Tender.expediente == TenderAnalysis.expediente)
        .where(
            TenderAnalysis.status == AnalysisStatus.COMPLETED,
            TenderAnalysis.extraction.is_not(None),
        )
        .order_by(TenderAnalysis.updated_at.desc())
    )
    if expediente is not None:
        stmt = stmt.where(TenderAnalysis.expediente == expediente)

    async with async_session_factory() as session:
        result = await session.execute(stmt.limit(limit))
        return [
            StoredAnalysis(row.expediente, row.extraction or {}, row.pcap_url) for row in result
        ]


async def _judge(
    llm: InstructorBaseRagasLLM, metric: Faithfulness, sample: FreeTextSample
) -> FieldScore:
    """Scores one description: split it into claims, then check each against the pages."""
    # RAGAS declares its own type variable as `t.TypeVar("T", bound=BaseModel)` under the
    # name `InstructorTypeVar` (ragas/llms/base.py:36). A TypeVar whose name doesn't match
    # the variable it's bound to is unsolvable, so mypy can't see through `agenerate`'s
    # signature even though the call really is generic in `response_model`. The casts say
    # what the library's own signature already promises.
    generated = cast(
        StatementGeneratorOutput,
        await llm.agenerate(
            metric.statement_generator_prompt.to_string(
                StatementGeneratorInput(question=sample.question, answer=sample.description)
            ),
            StatementGeneratorOutput,
        ),
    )
    if not generated.statements:
        return FieldScore(sample.field, sample.cited_page, NLIStatementOutput(statements=[]))

    verdicts = cast(
        NLIStatementOutput,
        await llm.agenerate(
            metric.nli_statement_prompt.to_string(
                NLIStatementInput(
                    context="\n".join(sample.contexts), statements=generated.statements
                )
            ),
            NLIStatementOutput,
        ),
    )
    return FieldScore(sample.field, sample.cited_page, verdicts)


async def _evaluate_document(
    analysis: StoredAnalysis,
    llm: InstructorBaseRagasLLM,
    metric: Faithfulness,
    client: httpx2.AsyncClient,
) -> DocumentResult:
    """Downloads a pliego, builds its samples and judges every one of them.

    Raises:
        QuotaExhaustedError: The judge answered 429; the rest of the run is pointless.
    """
    result = DocumentResult(analysis.expediente)

    if analysis.pcap_url is None:
        result.error = "no pcap_url found in the database"
        return result
    try:
        extraction = PliegoExtraction.model_validate(analysis.extraction)
    except ValidationError as exc:
        # A stored extraction predating a schema change, not a model failure.
        result.error = f"stored extraction no longer validates: {exc.error_count()} errors"
        return result

    print(f"  {analysis.expediente}: downloading pliego...", flush=True)
    pages = extract_pages(await download_pcap(analysis.pcap_url, client))
    samples, result.skipped = build_samples(extraction, pages)
    print(
        f"  {analysis.expediente}: {len(pages)} pages, {len(samples)} descriptions to judge",
        flush=True,
    )

    for sample in samples:
        try:
            score = await _judge(llm, metric, sample)
        except Exception as exc:  # noqa: BLE001 -- one judge failure must not lose the rest
            if _QUOTA_ERROR_MARKER in str(exc):
                raise QuotaExhaustedError(str(exc)) from exc
            print(f"    {sample.field}: judge failed -- {exc}", flush=True)
            continue
        result.scores.append(score)
        print(f"    {sample.field}: {score.supported}/{score.total} claims", flush=True)
    return result


def _report(results: list[DocumentResult], requests_made: int) -> None:
    """Prints every claim the judge rejected, then the aggregate and what it cost."""
    print(f"\n{'=' * 70}\nPER-DOCUMENT RESULTS\n{'=' * 70}")
    for result in results:
        print(f"\n  {result.expediente}")
        if result.error:
            print(f"    ERROR {result.error}")
            continue
        for score in result.scores:
            if math.isnan(score.score):
                print(f"    {score.field}: no claims extracted (cites page {score.cited_page})")
                continue
            print(
                f"    {score.field}: {score.score:.0%} "
                f"({score.supported}/{score.total} claims, cites page {score.cited_page})"
            )
            for statement in score.verdicts.statements:
                if not statement.verdict:
                    print(f"      UNSUPPORTED: {statement.statement}")
                    print(f"        judge: {statement.reason}")
        for skipped in result.skipped:
            print(f"    {skipped.field}: not scored -- {skipped.reason}")

    scored = [score for result in results for score in result.scores if not math.isnan(score.score)]
    skipped_total = sum(len(result.skipped) for result in results)

    print(f"\n{'=' * 70}\nAGGREGATE\n{'=' * 70}")
    if scored:
        claims = sum(score.total for score in scored)
        supported = sum(score.supported for score in scored)
        mean = sum(score.score for score in scored) / len(scored)
        print(f"  descriptions scored: {len(scored)}")
        print(f"  FAITHFULNESS (mean over descriptions): {mean:.0%}")
        print(f"  claims supported by their cited pages: {supported}/{claims}")
    if skipped_total:
        print(f"  descriptions not scored (nothing to judge against): {skipped_total}")
    print(f"  judge HTTP requests spent: {requests_made} (the free tier allows 50/day)")


async def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help=f"how many stored analyses to evaluate; each costs ~{REQUESTS_PER_PLIEGO} requests",
    )
    parser.add_argument("--expediente", help="evaluate only this tender")
    parser.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL)
    args = parser.parse_args()

    analyses = await _fetch_completed_analyses(args.limit, args.expediente)
    if not analyses:
        print("No completed analysis in the database -- nothing to evaluate.")
        return

    counter = RequestCounter()
    openai_client = AsyncOpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=require_openrouter_key(),
        # One retry, not the SDK's default two: the 429 this run actually meets is the
        # daily cap, which no amount of retrying resolves, and each attempt is a real
        # request -- the first dry run spent three of them on a single doomed call.
        max_retries=1,
        http_client=httpx2.AsyncClient(
            timeout=JUDGE_TIMEOUT_SECONDS, event_hooks={"request": [counter]}
        ),
    )
    llm = llm_factory(args.judge_model, client=openai_client)
    metric = Faithfulness(llm=llm)

    print(f"Judge: {args.judge_model}; evaluating {len(analyses)} pliego(s)\n")
    results: list[DocumentResult] = []
    async with httpx2.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        for analysis in analyses:
            try:
                results.append(await _evaluate_document(analysis, llm, metric, client))
            except QuotaExhaustedError as exc:
                print(
                    f"\n  Stopping: OpenRouter answered {_QUOTA_ERROR_MARKER} -- the free "
                    f"tier's 50 requests/day are spent ({exc}). The quota resets at 00:00 "
                    f"UTC; re-run after that.",
                    flush=True,
                )
                break

    _report(results, counter.count)


if __name__ == "__main__":
    asyncio.run(_main(), loop_factory=asyncio.SelectorEventLoop)
