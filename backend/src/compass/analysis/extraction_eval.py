"""Compares the two free-tier OpenRouter candidates against the 3.4 golden set.

Not part of the funnel -- the decision tool for this subphase, kept so the experiment
can be repeated if the OpenRouter catalog or the golden set changes (same pattern as
`matching/embedding_eval.py` in 2.4).

Feeds each candidate the PCAP's full page-labeled text, not `chunk_by_clause`'s output:
on this golden set, `chunk_by_clause` only reliably found headers in 2 of 4 real PCAPs
(0 and 2 clauses on the other two, whose sections are numbered without the word
"Cláusula" at all -- see phase3.4.md). Using the same raw-page input for every
document keeps the two candidates' comparison fair regardless of that gap, which is a
finding for a future chunking improvement, not something this subphase's model
decision needs solved first.
"""

import asyncio
import json
import time
from dataclasses import dataclass, field

import httpx2
from pydantic import ValidationError
from sqlalchemy import select

from compass.analysis.document import extract_pages
from compass.analysis.extraction_schema import PliegoExtraction
from compass.analysis.golden_set import GOLDEN_SET
from compass.analysis.graph import SYSTEM_PROMPT, build_prompt
from compass.analysis.openrouter import OpenRouterError, extract_structured
from compass.analysis.scoring import FieldCheck, score_extraction
from compass.core.config import get_settings
from compass.core.db import async_session_factory
from compass.tenders.models import Tender

CANDIDATE_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b:free",
    "nex-agi/nex-n2.5-pro:free",
]


@dataclass
class DocumentResult:
    expediente: str
    model: str
    checks: list[FieldCheck] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: float | None = None
    error: str | None = None


async def _fetch_pcap_pages(expediente: str, client: httpx2.AsyncClient) -> list[str]:
    async with async_session_factory() as session:
        tender = await session.scalar(select(Tender).where(Tender.expediente == expediente))
    assert tender is not None and tender.pcap_url is not None
    response = await client.get(tender.pcap_url)
    response.raise_for_status()
    return extract_pages(response.content)


async def _evaluate_one(
    expediente: str,
    expected: PliegoExtraction,
    model: str,
    api_key: str,
    client: httpx2.AsyncClient,
) -> DocumentResult:
    result = DocumentResult(expediente=expediente, model=model)
    started = time.monotonic()
    last_logged = 0.0

    def log_progress(content_chars: int, reasoning_chars: int) -> None:
        nonlocal last_logged
        elapsed = time.monotonic() - started
        if elapsed - last_logged < 5.0:  # at most once every 5s -- signal, not spam
            return
        last_logged = elapsed
        print(
            f"    ...{elapsed:.0f}s: {reasoning_chars} chars razonando, "
            f"{content_chars} chars de contenido",
            flush=True,
        )

    try:
        pages = await _fetch_pcap_pages(expediente, client)
        prompt = build_prompt(pages)
        # The free tier occasionally returns an inline error or an empty
        # completion under provider-side load -- one retry absorbs that
        # noise instead of counting a transient hiccup as a model failure.
        try:
            response = await extract_structured(
                model=model,
                system_prompt=SYSTEM_PROMPT,
                user_prompt=prompt,
                schema=PliegoExtraction,
                api_key=api_key,
                client=client,
                on_progress=log_progress,
            )
        except (OpenRouterError, httpx2.HTTPError, ValidationError):
            response = await extract_structured(
                model=model,
                system_prompt=SYSTEM_PROMPT,
                user_prompt=prompt,
                schema=PliegoExtraction,
                api_key=api_key,
                client=client,
                on_progress=log_progress,
            )
        result.prompt_tokens = response.usage.prompt_tokens
        result.completion_tokens = response.usage.completion_tokens
        result.cost = response.usage.cost
        got = PliegoExtraction.model_validate_json(response.content)
        result.checks = score_extraction(expected, got)
    except (
        ValidationError,
        httpx2.HTTPStatusError,
        httpx2.HTTPError,
        OpenRouterError,
        AssertionError,
        json.JSONDecodeError,
    ) as e:
        result.error = repr(e)
    return result


async def _main() -> None:
    settings = get_settings()
    async with httpx2.AsyncClient(timeout=300.0, follow_redirects=True) as client:
        for model in CANDIDATE_MODELS:
            print(f"\n{'=' * 60}\n{model}\n{'=' * 60}", flush=True)
            total_correct = 0
            total_checks = 0
            total_cost = 0.0
            for expediente, expected in GOLDEN_SET.items():
                started = time.monotonic()
                print(f"  {expediente}: calling...", flush=True)
                result = await _evaluate_one(
                    expediente, expected, model, settings.openrouter_api_key, client
                )
                elapsed = time.monotonic() - started
                print(f"  {expediente}: done in {elapsed:.1f}s", flush=True)
                if result.error:
                    print(f"  {expediente}: ERROR {result.error}")
                    continue
                correct = sum(1 for c in result.checks if c.correct)
                total_correct += correct
                total_checks += len(result.checks)
                total_cost += result.cost or 0.0
                print(
                    f"  {expediente}: {correct}/{len(result.checks)} correct "
                    f"(prompt={result.prompt_tokens}, completion={result.completion_tokens}, "
                    f"cost={result.cost})"
                )
                for c in result.checks:
                    if not c.correct:
                        print(f"    WRONG {c.name}: expected={c.expected!r} got={c.got!r}")
            if total_checks:
                pct = total_correct / total_checks
                print(f"\n  TOTAL: {total_correct}/{total_checks} ({pct:.0%})")
                print(f"  cost: {total_cost:.6f}")


if __name__ == "__main__":
    asyncio.run(_main(), loop_factory=asyncio.SelectorEventLoop)
