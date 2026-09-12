"""Verifies that a citation the model claims actually exists in the parsed pliego text.

The model is asked for a verbatim quote, but "verbatim" in practice means the words
are exact -- not the whitespace. A real PCAP wraps a sentence across PDF lines,
`extract_pages` preserves that as an embedded newline, and a model naturally re-flows
the same sentence into plain prose. Confirmed against a full real extraction (3.4,
`nex-agi/nex-n2.5-pro:free` over `1276564F`): all 8 of its citations matched their
cited page exactly once whitespace is collapsed -- no accent or currency-symbol
normalization was needed, that suspicion came from an earlier test contaminated by a
hand-typed, unaccented snippet rather than the real PDF text.

**Contiguity is not enough, and 5.8 measured why.** A PCAP puts everything that decides
a bid in the "Cuadro de Características del Contrato", a two-column table -- and
`pdfplumber` linearizes a table by visual line, not by cell, so the left column's label
lands in the middle of the right column's sentence. On `040-2026-0075` the guarantees
block comes out of the parser like this:

    Garantía provisional: ☒No ☐Sí
    Garantía definitiva: ☒No ☐Sí
    Garantía
    ☒No ☐Sí
    complementaria:

A model that reads that table correctly quotes "Garantía complementaria: ☒No ☐Sí", which
is not a substring of anything -- the label is split around a row of checkboxes that
belongs to it. Four of that pliego's nine citations failed the contiguous test for
exactly this reason, every one of them quoting a table, and every one of them extracting
the right value. The published score said 56% about an extraction that was faithful nine
times out of nine.

So a citation gets one of three outcomes (`CitationCheck`) instead of a boolean:
contiguous, present-but-reordered, or absent. Only the third means the model wrote words
the cited page does not contain -- which is the thing this module exists to catch. The
middle one is deliberately weaker evidence than the first: order-free membership cannot
tell "☒No ☐Sí" from "☐No ☒Sí", so a swapped checkbox would pass it. That is why they stay
separate classes and are reported separately, rather than being blended into one number
that means neither thing (`citation_report`).
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from compass.analysis.extraction_schema import Citation, PliegoExtraction

_WHITESPACE_RE = re.compile(r"\s+")
# Words plus any single non-word, non-space character. The second half is not
# decoration: a PCAP's checkbox glyphs (☒/☐) carry the answer in the Cuadro de
# Características, and dropping them as punctuation would throw away the only part of
# "Garantía provisional: ☒No ☐Sí" that says anything.
_TOKEN_RE = re.compile(r"\w+|[^\w\s]")


class CitationCheck(StrEnum):
    """What checking one citation against its cited page found."""

    VERIFIED = "verified"
    """The quote appears on the cited page, contiguously. The strongest evidence."""

    VERIFIED_REORDERED = "verified_reordered"
    """Every token of the quote appears on the cited page, but not contiguously --
    the signature of a table the parser linearized differently than the model read it.
    Weaker than `VERIFIED`: membership ignores order, so it cannot tell two permutations
    of the same tokens apart.
    """

    UNVERIFIED = "unverified"
    """The cited page is missing at least one token of the quote (or doesn't exist).
    The model wrote something that page does not say.
    """


def _normalize(text: str) -> str:
    """Collapses any run of whitespace (including embedded newlines from a PDF's own
    line wrapping) to a single space, so a re-flowed quote can match its source.
    """
    return _WHITESPACE_RE.sub(" ", text).strip()


def _tokens(text: str) -> list[str]:
    """The quote's or page's comparable units, lowercased.

    Lowercased because a model re-flowing a line routinely re-cases the first word of
    it; accents are kept, because in Spanish they distinguish real words.
    """
    return _TOKEN_RE.findall(_normalize(text).lower())


def check_citation(citation: Citation, pages: list[str]) -> CitationCheck:
    """Which of the three outcomes `citation` gets against the page it claims.

    Args:
        citation: A citation from a `PliegoExtraction`.
        pages: Per-page extracted text, in the same order/indexing `Citation.page`
            uses (1-indexed, from `document.extract_pages`).

    Returns:
        `VERIFIED` if the normalized quote is a substring of the cited page;
        `VERIFIED_REORDERED` if every one of its tokens appears on that page anyway;
        `UNVERIFIED` if the page is out of range or any token is missing from it.
    """
    if not (1 <= citation.page <= len(pages)):
        return CitationCheck.UNVERIFIED

    page = pages[citation.page - 1]
    if _normalize(citation.quote).lower() in _normalize(page).lower():
        return CitationCheck.VERIFIED

    page_tokens = set(_tokens(page))
    if all(token in page_tokens for token in _tokens(citation.quote)):
        return CitationCheck.VERIFIED_REORDERED

    return CitationCheck.UNVERIFIED


def verify_citation(citation: Citation, pages: list[str]) -> bool:
    """Whether `citation.quote` is supported by the page it claims.

    Kept as a boolean for the callers that only need the yes/no (the graph, the tests
    that predate 5.8); `check_citation` is what says *how* it matched.

    Args:
        citation: A citation from a `PliegoExtraction`.
        pages: Per-page extracted text, 1-indexed like `Citation.page`.

    Returns:
        `False` only when the cited page is missing tokens the quote uses -- a
        reordered match still counts as supported, for the reasons in the module
        docstring.
    """
    return check_citation(citation, pages) is not CitationCheck.UNVERIFIED


@dataclass(frozen=True)
class CitationField:
    """One citation of the extraction, and how to reach it."""

    name: str
    citation_of: Callable[[PliegoExtraction], Citation | None]


CITATION_FIELDS: tuple[CitationField, ...] = (
    CitationField("economic_solvency", lambda e: e.economic_solvency.citation),
    CitationField("technical_solvency", lambda e: e.technical_solvency.citation),
    CitationField("certifications", lambda e: e.certifications_citation),
    CitationField("award_criteria", lambda e: e.award_criteria.citation),
    CitationField("guarantees", lambda e: e.guarantees.citation),
    CitationField("execution_deadline", lambda e: e.execution_deadline.citation),
    CitationField("submission_deadline", lambda e: e.submission_deadline.citation),
    CitationField("subcontracting", lambda e: e.subcontracting.citation),
    CitationField("lots", lambda e: e.lots.citation),
)


def citation_report(extraction: PliegoExtraction, pages: list[str]) -> dict[str, CitationCheck]:
    """Every present citation of `extraction`, with what checking it found.

    Fields whose citation is `None` are absent from the result entirely: the pliego
    genuinely doesn't address that point, so there is nothing to verify and no outcome
    to report.

    Args:
        extraction: A validated model output.
        pages: Per-page extracted text for the same pliego.

    Returns:
        Field name -> outcome, for the citations that exist.
    """
    report: dict[str, CitationCheck] = {}
    for field in CITATION_FIELDS:
        citation = field.citation_of(extraction)
        if citation is not None:
            report[field.name] = check_citation(citation, pages)
    return report


def citation_faithfulness(extraction: PliegoExtraction, pages: list[str]) -> float:
    """The fraction of `extraction`'s present citations the pliego actually supports --
    tracked over time by `regression_eval` (4.4), in Python.

    Not what RAGAS measures here: 5.6 pointed it at the *descriptions*, whose prose no
    string comparison can check, and left citation faithfulness where it already was --
    a judge model deciding whether a quote appears on a page would be slower, costlier
    and less certain than this token test.

    Counts a reordered match as supported (see the module docstring): before 5.8 it
    didn't, and the score that produced was mostly a measure of how many tables the
    pliego put its requirements in.

    Args:
        extraction: A validated model output.
        pages: Per-page extracted text for the same pliego, from `document.extract_pages`.

    Returns:
        1.0 if every present citation is supported (or none are present), down to 0.0
        if none are.
    """
    outcomes = list(citation_report(extraction, pages).values())
    if not outcomes:
        return 1.0
    supported = sum(1 for outcome in outcomes if outcome is not CitationCheck.UNVERIFIED)
    return supported / len(outcomes)
