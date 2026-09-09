"""Splits pliego text into clause-aware chunks -- not fixed-size windows.

A pliego is numbered clauses with a title, not continuous prose: chunking by
character/token count would cut a clause in half, splitting exactly the kind
of solvency/certification text a real extraction needs whole (see
docs/phases/phase3/phase3.md). `chunk_fixed_size` exists only as the "before"
half of that comparison -- it is not meant to be used for real extraction.
"""

import re
from dataclasses import dataclass

# Matches a clause header at the start of a line: "Cláusula 12.2.- Título" or
# "Clausula 1. Titulo" (accent optional -- pdfplumber output for a real PCAP
# will have it, this project's own hand-built test fixture doesn't, to avoid
# font-encoding pitfalls in a minimal PDF).
#
# Known limitation, not solved here: doesn't match spelled-out ordinals
# ("CLÁUSULA PRIMERA") or a pliego that numbers clauses without the word
# "Cláusula" at all. Revisited in 3.4 against real PCAPs, not guessed at now.
CLAUSE_HEADER = re.compile(
    r"^Cl[aá]usula\s+(?P<number>\d+(?:\.\d+)*)\s*[.\-:]?\s*(?P<title>.+)$",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass
class Clause:
    """One numbered clause: its header fields, full text (header included), and starting page.

    `page` is where the clause *starts* -- what a citation ("cláusula 12.2,
    página 7") needs -- not every page it might run onto.
    """

    number: str
    title: str
    text: str
    page: int


def chunk_by_clause(pages: list[str]) -> list[Clause]:
    """Splits `pages` into one `Clause` per detected clause header.

    Args:
        pages: Per-page extracted text, in order (from `document.extract_pages`).

    Returns:
        Clauses in document order. Text before the first detected header (a
        cover page, an index) isn't a clause and is dropped -- there's
        nothing to attribute it to.
    """
    combined, page_starts = _combine_with_page_offsets(pages)
    matches = list(CLAUSE_HEADER.finditer(combined))

    clauses = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(combined)
        clauses.append(
            Clause(
                number=match.group("number"),
                title=match.group("title").strip(),
                text=combined[match.start() : end].strip(),
                page=_page_for_offset(match.start(), page_starts),
            )
        )
    return clauses


def chunk_fixed_size(pages: list[str], *, size: int = 500) -> list[str]:
    """Splits `pages` into blind `size`-character windows, ignoring clause structure entirely.

    Exists only to demonstrate, on a real fixture, what `chunk_by_clause`
    avoids -- not a real extraction input.
    """
    combined, _ = _combine_with_page_offsets(pages)
    return [combined[i : i + size] for i in range(0, len(combined), size)]


def _combine_with_page_offsets(pages: list[str]) -> tuple[str, list[int]]:
    """Joins `pages` into one string, plus the character offset each page starts at."""
    combined = ""
    page_starts = []
    for page_text in pages:
        page_starts.append(len(combined))
        combined += page_text + "\n"
    return combined, page_starts


def _page_for_offset(offset: int, page_starts: list[int]) -> int:
    """The 1-indexed page containing character `offset`, given each page's starting offset."""
    page = 0
    for i, start in enumerate(page_starts):
        if start <= offset:
            page = i
        else:
            break
    return page + 1
