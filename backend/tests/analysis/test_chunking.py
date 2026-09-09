"""Tests for chunk_by_clause/chunk_fixed_size -- against the real sample_pliego.pdf fixture
from Phase 3.2, not synthetic strings: what pdfplumber actually hands back matters here.
"""

from pathlib import Path

from compass.analysis.chunking import CLAUSE_HEADER, chunk_by_clause, chunk_fixed_size
from compass.analysis.document import extract_pages

FIXTURES_DIR = Path(__file__).parent / "fixtures"
PAGES = extract_pages((FIXTURES_DIR / "sample_pliego.pdf").read_bytes())


def test_chunk_by_clause_extracts_every_clause_with_number_title_and_page() -> None:
    """Protects the core behavior: all 4 real clauses, correctly numbered, titled, and
    attributed to the page their header actually starts on.
    """
    clauses = chunk_by_clause(PAGES)

    assert [(c.number, c.title, c.page) for c in clauses] == [
        ("1", "Objeto del contrato", 1),
        ("2", "Solvencia economica y financiera", 1),
        ("3", "Certificaciones requeridas", 2),
        ("4", "Criterios de adjudicacion", 2),
    ]


def test_chunk_by_clause_keeps_each_clause_whole() -> None:
    """Protects the actual point of clause-aware chunking: a clause's own text always starts
    with its own header, never with another clause's body.
    """
    clauses = chunk_by_clause(PAGES)

    for clause in clauses:
        assert clause.text.startswith(f"Clausula {clause.number}")


def test_chunk_fixed_size_can_sever_a_clause_from_its_own_header() -> None:
    """Protects the "before" side of the comparison the design doc asks for: a blind
    size-based split can leave a chunk holding a clause's body with no header in it at all --
    exactly what chunk_by_clause exists to avoid, demonstrated against the real fixture, not
    asserted in the abstract.
    """
    naive_chunks = chunk_fixed_size(PAGES, size=100)

    headerless_with_clause_3_body = [
        chunk
        for chunk in naive_chunks
        if not CLAUSE_HEADER.search(chunk) and "certificacion" in chunk.lower()
    ]

    assert headerless_with_clause_3_body, (
        "expected at least one naive 100-char chunk to carry clause 3's body "
        "without its own header -- if this fails, the fixture or chunk size "
        "changed and no longer demonstrates the failure mode"
    )
