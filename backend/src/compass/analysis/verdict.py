"""Computes the deterministic verdict -- `analysis.enums.Verdict` -- for one pliego
extraction against the current provider profile.

The single most important rule in the project (`docs/phases/phase3/phase3.md`, "el
LLM extrae, el código decide"): this module has no LLM calls, no network, no database
session. It's a pure function over two already-validated Pydantic models.

Only two fields of `PliegoExtraction` compare against something `Provider` actually
stores, so only those two can block a bid:

- `economic_solvency.minimum_annual_turnover_eur` against `Provider.annual_revenue`.
- `certifications` against `Provider.certifications`.

`technical_solvency.minimum_amount_eur` (cumulative amount of similar past work) has
no counterpart on `Provider` at all -- the profile doesn't track it (see
`providers/models.py`) -- so a stated requirement there can only ever be a reservation,
never a block: there's nothing to compare it against, so nothing to fail it on.
Likewise a stated turnover requirement against a `Provider` that hasn't declared
`annual_revenue` is a reservation, not a pass or a fail -- the extraction and the
profile are both present, but one of the two numbers needed for the comparison is
missing. Award criteria, guarantees, deadlines, subcontracting and lots don't gate
the verdict at all: the profile has nothing to contrast them against, so they stay
informational, surfaced from `extraction` itself rather than duplicated here.
"""

import re
import unicodedata

from compass.analysis.enums import Verdict
from compass.analysis.extraction_schema import PliegoExtraction
from compass.analysis.schemas import VerdictReason, VerdictResult
from compass.providers.models import Provider

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _format_eur(amount: float) -> str:
    """Spanish-style grouping ('300.000 €'), not Python's own ('300,000.00 €') --
    this text is user-facing product copy, not a log line.
    """
    return f"{amount:,.0f}".replace(",", ".") + " €"


def _tokens(text: str) -> set[str]:
    """Lowercased, accent-stripped alphanumeric tokens, e.g. 'ISO/IEC 27001:2013' ->
    {'iso', 'iec', '27001', '2013'}. Punctuation becomes a token boundary rather than
    being kept or dropped silently, so 'ISO27001' and 'ISO 27001' still tokenize
    differently -- deliberately: the digits are what actually identifies a standard.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return set(_TOKEN_RE.findall(without_accents.lower()))


def _certification_satisfied(required: str, held: list[str]) -> bool:
    """Whether `required` is covered by the provider's declared certifications.

    Token-subset match, not equality or plain substring: a pliego naming 'ISO 27001'
    must match a profile that declares the fuller 'ISO/IEC 27001:2013' -- neither
    string is a substring of the other once 'IEC' sits between them, but
    {'iso', '27001'} is a subset of {'iso', 'iec', '27001', '2013'}. Checked in
    both directions so the shorter side is always the one that must be covered,
    whichever of the two happens to be shorter. Deliberately permissive: a missing
    certification blocks the bid entirely (see module docstring), so a stricter
    match would trade false negatives (blocking a provider who does hold the
    certification, just phrased differently) for a precision this project has no
    evidence it needs yet.
    """
    required_tokens = _tokens(required)
    return any(
        required_tokens <= (held_tokens := _tokens(candidate)) or held_tokens <= required_tokens
        for candidate in held
    )


def compute_verdict(extraction: PliegoExtraction, provider: Provider) -> VerdictResult:
    """Compares a pliego extraction against the current provider profile.

    Args:
        extraction: A validated, citation-carrying extraction (3.4).
        provider: The current, singleton `Provider` profile (Fase 2).

    Returns:
        `NO_APTO` if any blocking reason applies (turnover shortfall, a missing
        required certification); else `APTO_CON_RESERVAS` if any requirement
        couldn't be checked against what the profile declares; else `APTO`.
    """
    blocking: list[VerdictReason] = []
    reserved: list[VerdictReason] = []

    required_turnover = extraction.economic_solvency.minimum_annual_turnover_eur
    if required_turnover is not None:
        if provider.annual_revenue is None:
            reserved.append(
                VerdictReason(
                    detail=(
                        f"El pliego exige una facturación anual mínima de "
                        f"{_format_eur(required_turnover)}, pero tu perfil no declara "
                        "facturación anual -- no se puede verificar."
                    ),
                    citation=extraction.economic_solvency.citation,
                )
            )
        elif float(provider.annual_revenue) < required_turnover:
            blocking.append(
                VerdictReason(
                    detail=(
                        f"Exigen una facturación anual mínima de "
                        f"{_format_eur(required_turnover)} y tu perfil declara "
                        f"{_format_eur(float(provider.annual_revenue))}."
                    ),
                    citation=extraction.economic_solvency.citation,
                )
            )

    required_amount = extraction.technical_solvency.minimum_amount_eur
    if required_amount is not None:
        reserved.append(
            VerdictReason(
                detail=(
                    f"El pliego exige un importe acumulado de trabajos similares de "
                    f"{_format_eur(required_amount)}, pero tu perfil no registra importe de "
                    "trabajos previos -- no se puede verificar."
                ),
                citation=extraction.technical_solvency.citation,
            )
        )

    held_certifications = provider.certifications or []
    for required_certification in extraction.certifications:
        if not _certification_satisfied(required_certification, held_certifications):
            blocking.append(
                VerdictReason(
                    detail=(
                        f"Exigen la certificación '{required_certification}' y tu perfil "
                        "no la declara."
                    ),
                    citation=extraction.certifications_citation,
                )
            )

    if blocking:
        return VerdictResult(verdict=Verdict.NO_APTO, reasons=blocking + reserved)
    if reserved:
        return VerdictResult(verdict=Verdict.APTO_CON_RESERVAS, reasons=reserved)
    return VerdictResult(verdict=Verdict.APTO, reasons=[])
