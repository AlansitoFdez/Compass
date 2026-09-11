"""Verifies that a citation the model claims actually exists in the parsed pliego text.

The model is asked for a verbatim quote, but "verbatim" in practice means the words
are exact -- not the whitespace. A real PCAP wraps a sentence across PDF lines,
`extract_pages` preserves that as an embedded newline, and a model naturally re-flows
the same sentence into plain prose. Confirmed against a full real extraction (3.4,
`nex-agi/nex-n2.5-pro:free` over `1276564F`): all 8 of its citations matched their
cited page exactly once whitespace is collapsed -- no accent or currency-symbol
normalization was needed, that suspicion came from an earlier test contaminated by a
hand-typed, unaccented snippet rather than the real PDF text.
"""

import re

from compass.analysis.extraction_schema import Citation, PliegoExtraction

_WHITESPACE_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    """Collapses any run of whitespace (including embedded newlines from a PDF's own
    line wrapping) to a single space, so a re-flowed quote can match its source.
    """
    return _WHITESPACE_RE.sub(" ", text).strip()


def verify_citation(citation: Citation, pages: list[str]) -> bool:
    """Whether `citation.quote` actually appears on the page it claims.

    Args:
        citation: A citation from a `PliegoExtraction`.
        pages: Per-page extracted text, in the same order/indexing `Clause.page`
            and `Citation.page` use (1-indexed, from `document.extract_pages`).

    Returns:
        `False` if the page number is out of range, or the quote (after whitespace
        normalization) isn't a substring of that page's text.
    """
    if not (1 <= citation.page <= len(pages)):
        return False
    return _normalize(citation.quote) in _normalize(pages[citation.page - 1])


def citation_faithfulness(extraction: PliegoExtraction, pages: list[str]) -> float:
    """The fraction of `extraction`'s present citations that verify -- tracked over time
    by `regression_eval` (4.4), in Python.

    Not what RAGAS measures here: 5.6 pointed it at the *descriptions*, whose prose no
    string comparison can check, and left citation faithfulness where it already was --
    a judge model deciding whether a quote appears on a page would be slower, costlier
    and less certain than this substring test.

    Fields with no citation (the pliego genuinely doesn't address that point) aren't
    counted at all: there's nothing to verify, so they neither help nor hurt the score.

    Args:
        extraction: A validated model output.
        pages: Per-page extracted text for the same pliego, from `document.extract_pages`.

    Returns:
        1.0 if every present citation verifies (or none are present), down to 0.0 if
        none do.
    """
    citations = [
        extraction.economic_solvency.citation,
        extraction.technical_solvency.citation,
        extraction.certifications_citation,
        extraction.award_criteria.citation,
        extraction.guarantees.citation,
        extraction.execution_deadline.citation,
        extraction.submission_deadline.citation,
        extraction.subcontracting.citation,
        extraction.lots.citation,
    ]
    present = [c for c in citations if c is not None]
    if not present:
        return 1.0
    verified = sum(1 for c in present if verify_citation(c, pages))
    return verified / len(present)
