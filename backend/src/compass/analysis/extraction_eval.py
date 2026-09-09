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
import re
import time
from dataclasses import dataclass, field

import httpx2
from pydantic import ValidationError
from sqlalchemy import select

from compass.analysis.document import extract_pages
from compass.analysis.extraction_schema import PliegoExtraction
from compass.analysis.golden_set import GOLDEN_SET
from compass.analysis.openrouter import OpenRouterError, extract_structured
from compass.core.config import get_settings
from compass.core.db import async_session_factory
from compass.tenders.models import Tender

CANDIDATE_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b:free",
    "nex-agi/nex-n2.5-pro:free",
]

SYSTEM_PROMPT = (
    "Eres un analista experto en contratación pública española (LCSP). Se te da el "
    "texto completo de un pliego de cláusulas administrativas particulares (PCAP), "
    "página a página. Extrae únicamente lo que el texto dice explícitamente, con su "
    "cita exacta (número/identificador de cláusula tal como aparece en el texto, "
    "número de página, y una cita textual verbatim copiada del pliego). Si el pliego "
    "no aborda un campo, déjalo en null o lista vacía según corresponda -- no inventes "
    "ni asumas valores típicos de otros pliegos que no conoces."
)

CERT_TOKEN_RE = re.compile(r"ISO\s?\d{4,5}|CMMI|ENS\b|IEC\s?\d+|CCN-?CERT", re.IGNORECASE)


def build_prompt(pages: list[str]) -> str:
    """The full PCAP text, one labeled block per page -- see module docstring for why
    this is used instead of `chunk_by_clause`'s output here."""
    return "\n\n".join(f"===== PÁGINA {i} =====\n{page}" for i, page in enumerate(pages, start=1))


def _cert_tokens(certifications: list[str]) -> set[str]:
    joined = " | ".join(certifications)
    return {m.group(0).upper().replace(" ", "") for m in CERT_TOKEN_RE.finditer(joined)}


def _price_points(extraction: PliegoExtraction) -> float | None:
    for criterion in extraction.award_criteria.criteria:
        if criterion.is_price:
            return criterion.points
    return None


def _nums_match(expected: float | None, got: float | None, *, tol: float = 1.0) -> bool:
    if expected is None or got is None:
        return expected is None and got is None
    return abs(expected - got) <= tol


@dataclass
class FieldCheck:
    """One scored field: whether the model's value matches the hand-annotated one."""

    name: str
    correct: bool
    expected: object
    got: object


@dataclass
class DocumentResult:
    expediente: str
    model: str
    checks: list[FieldCheck] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: float | None = None
    error: str | None = None


def score_extraction(expected: PliegoExtraction, got: PliegoExtraction) -> list[FieldCheck]:
    """The 9 objectively-checkable subfields -- the numeric/boolean/list data a verdict
    (3.7) actually computes from, not the free-text descriptions (see phase3.4.md for
    why those aren't scored mechanically).
    """
    expected_cert_tokens = _cert_tokens(expected.certifications)
    got_cert_tokens = _cert_tokens(got.certifications)
    certifications_correct = (
        expected_cert_tokens.issubset(got_cert_tokens)
        if expected_cert_tokens
        else not got_cert_tokens
    )

    return [
        FieldCheck(
            "economic_solvency.minimum_annual_turnover_eur",
            _nums_match(
                expected.economic_solvency.minimum_annual_turnover_eur,
                got.economic_solvency.minimum_annual_turnover_eur,
            ),
            expected.economic_solvency.minimum_annual_turnover_eur,
            got.economic_solvency.minimum_annual_turnover_eur,
        ),
        FieldCheck(
            "technical_solvency.minimum_amount_eur",
            _nums_match(
                expected.technical_solvency.minimum_amount_eur,
                got.technical_solvency.minimum_amount_eur,
            ),
            expected.technical_solvency.minimum_amount_eur,
            got.technical_solvency.minimum_amount_eur,
        ),
        FieldCheck(
            "certifications",
            certifications_correct,
            sorted(expected_cert_tokens),
            sorted(got_cert_tokens),
        ),
        FieldCheck(
            "award_criteria.total_points",
            _nums_match(
                expected.award_criteria.total_points, got.award_criteria.total_points, tol=0.5
            ),
            expected.award_criteria.total_points,
            got.award_criteria.total_points,
        ),
        FieldCheck(
            "award_criteria.price_points",
            _nums_match(_price_points(expected), _price_points(got), tol=0.5),
            _price_points(expected),
            _price_points(got),
        ),
        FieldCheck(
            "guarantees.provisional_required",
            expected.guarantees.provisional_required == got.guarantees.provisional_required,
            expected.guarantees.provisional_required,
            got.guarantees.provisional_required,
        ),
        FieldCheck(
            "guarantees.definitive_percentage",
            _nums_match(
                expected.guarantees.definitive_percentage,
                got.guarantees.definitive_percentage,
                tol=0.5,
            ),
            expected.guarantees.definitive_percentage,
            got.guarantees.definitive_percentage,
        ),
        FieldCheck(
            "subcontracting.allowed",
            expected.subcontracting.allowed == got.subcontracting.allowed,
            expected.subcontracting.allowed,
            got.subcontracting.allowed,
        ),
        FieldCheck(
            "lots.divided_into_lots",
            expected.lots.divided_into_lots == got.lots.divided_into_lots,
            expected.lots.divided_into_lots,
            got.lots.divided_into_lots,
        ),
    ]


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
