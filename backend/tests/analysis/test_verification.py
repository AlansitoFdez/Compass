"""Tests for citation verification -- against the real `sample_pliego.pdf` fixture
from Phase 3.2/3.3, not synthetic strings: whitespace behavior from real pdfplumber
output is exactly the thing being protected here.
"""

from pathlib import Path

from compass.analysis.document import extract_pages
from compass.analysis.extraction_schema import (
    AwardCriteria,
    AwardCriterion,
    Citation,
    EconomicSolvency,
    ExecutionDeadline,
    Guarantees,
    Lots,
    PliegoExtraction,
    Subcontracting,
    SubmissionDeadline,
    TechnicalSolvency,
)
from compass.analysis.verification import (
    CitationCheck,
    check_citation,
    citation_faithfulness,
    citation_report,
    verify_citation,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
PAGES = extract_pages((FIXTURES_DIR / "sample_pliego.pdf").read_bytes())

# `pdfplumber`'s real output for the guarantees block of `040-2026-0075`, page 4, copied
# verbatim from the parser in 5.8. Not simplified: the point of this page is that the
# left column's label ("Garantía complementaria:") is split in two and the right
# column's checkbox row lands between its halves, which is precisely what no
# substring test can survive. A hand-written approximation would prove nothing.
CUADRO_PAGE = (
    "H. GARANTÍAS\n"
    "Garantía provisional: ☒No ☐Sí\n"
    "Garantía definitiva: ☒No ☐Sí\n"
    "Garantía\n"
    "☒No ☐Sí\n"
    "complementaria:\n"
)


def _extraction_with_citations(*citations: Citation | None) -> PliegoExtraction:
    """A syntactically valid `PliegoExtraction` carrying exactly the given citations,
    one per field in schema order, for `citation_faithfulness` tests that only care
    about which citations verify.
    """
    (
        economic_citation,
        technical_citation,
        certifications_citation,
        award_citation,
        guarantees_citation,
        execution_citation,
        submission_citation,
        subcontracting_citation,
        lots_citation,
    ) = citations
    return PliegoExtraction(
        economic_solvency=EconomicSolvency(
            minimum_annual_turnover_eur=None, description="", citation=economic_citation
        ),
        technical_solvency=TechnicalSolvency(
            minimum_amount_eur=None, description="", citation=technical_citation
        ),
        certifications=[],
        certifications_citation=certifications_citation,
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[AwardCriterion(name="Precio", points=60, is_price=True)],
            citation=award_citation,
        ),
        guarantees=Guarantees(
            provisional_required=False,
            definitive_percentage=None,
            description="",
            citation=guarantees_citation,
        ),
        execution_deadline=ExecutionDeadline(description="", citation=execution_citation),
        submission_deadline=SubmissionDeadline(description="", citation=submission_citation),
        subcontracting=Subcontracting(
            allowed=True, description="", citation=subcontracting_citation
        ),
        lots=Lots(
            divided_into_lots=False,
            can_bid_partial_lots=None,
            description="",
            citation=lots_citation,
        ),
    )


def test_verify_citation_true_for_an_exact_quote_on_the_right_page() -> None:
    """Protects the base case: a quote copied straight from its cited page verifies."""
    citation = Citation(clause="3", page=2, quote="Se exige la certificacion ISO 27001")

    assert verify_citation(citation, PAGES) is True


def test_verify_citation_true_when_the_quote_re_flows_a_pdf_line_wrap() -> None:
    """Protects the real finding from 3.4/3.5: `extract_pages` embeds a newline
    wherever the PDF wrapped a line mid-sentence, but a model naturally re-flows that
    into plain prose with a single space. Both must verify as the same text.
    """
    # Real fixture text: "cifra de negocio\nminima de 100000 euros" (embedded newline).
    citation = Citation(
        clause="2", page=1, quote="cifra de negocio minima de 100000 euros en alguno de los tres"
    )

    assert verify_citation(citation, PAGES) is True


def test_verify_citation_false_for_a_fabricated_quote() -> None:
    """Protects against a false positive: text that simply isn't in the pliego at all."""
    citation = Citation(clause="2", page=1, quote="cifra de negocio minima de 500000 euros")

    assert verify_citation(citation, PAGES) is False


def test_verify_citation_false_for_a_real_quote_on_the_wrong_page() -> None:
    """Protects against a model citing real pliego text but attributing it to the
    wrong page -- attributing clause 3's content to page 1, where it doesn't appear.
    """
    citation = Citation(clause="3", page=1, quote="Se exige la certificacion ISO 27001")

    assert verify_citation(citation, PAGES) is False


def test_verify_citation_false_for_a_page_number_out_of_range() -> None:
    """Protects against an out-of-bounds page crashing verification instead of
    just failing it.
    """
    citation = Citation(clause="1", page=99, quote="Objeto del contrato")

    assert verify_citation(citation, PAGES) is False


def test_citation_faithfulness_is_one_when_no_citations_are_present() -> None:
    """Protects the vacuous case: nothing to verify isn't the same as unfaithful."""
    extraction = _extraction_with_citations(None, None, None, None, None, None, None, None, None)

    assert citation_faithfulness(extraction, PAGES) == 1.0


def test_citation_faithfulness_is_one_when_every_present_citation_verifies() -> None:
    """Protects the ceiling: a fully faithful extraction scores 1.0."""
    real = Citation(clause="1", page=1, quote="Objeto del contrato")
    extraction = _extraction_with_citations(real, real, None, None, None, None, None, None, None)

    assert citation_faithfulness(extraction, PAGES) == 1.0


def test_citation_faithfulness_is_the_correct_fraction_with_a_mix() -> None:
    """Protects that the score is a real fraction, not a pass/fail flag -- one
    verified citation out of two present scores exactly 0.5.
    """
    real = Citation(clause="1", page=1, quote="Objeto del contrato")
    fabricated = Citation(clause="1", page=1, quote="texto que no existe en el pliego")
    extraction = _extraction_with_citations(
        real, fabricated, None, None, None, None, None, None, None
    )

    assert citation_faithfulness(extraction, PAGES) == 0.5


def test_check_citation_verified_for_a_contiguous_quote() -> None:
    """Protects the strongest outcome staying distinguishable from the other two: a
    quote copied straight off its page is `VERIFIED`, not merely supported.
    """
    citation = Citation(clause="3", page=2, quote="Se exige la certificacion ISO 27001")

    assert check_citation(citation, PAGES) is CitationCheck.VERIFIED


def test_check_citation_reordered_when_the_parser_split_the_label_it_quotes() -> None:
    """Protects the 5.8 finding: a model that reads a two-column Cuadro de
    Características correctly quotes text the parser never emits contiguously, because
    the right column's checkboxes land inside the left column's label. That is a
    parsing artifact, not an invented quote, and it must not read as one.
    """
    citation = Citation(
        clause="H",
        page=1,
        quote="Garantía complementaria: ☒No ☐Sí",
    )

    assert check_citation(citation, [CUADRO_PAGE]) is CitationCheck.VERIFIED_REORDERED


def test_verify_citation_true_for_a_reordered_quote() -> None:
    """Protects the behavior change the boolean callers see: before 5.8 this same
    citation -- every word of it on the cited page -- counted as unfaithful.
    """
    citation = Citation(clause="H", page=1, quote="Garantía complementaria: ☒No ☐Sí")

    assert verify_citation(citation, [CUADRO_PAGE]) is True


def test_check_citation_unverified_when_the_page_lacks_a_word_of_the_quote() -> None:
    """Protects what the looser rule must still catch. Taken from a real failure
    (`1583900M`, 5.8): the model cited "3 meses" to page 1, which contains neither
    word. Reordering can excuse a scrambled page; it cannot conjure absent text.
    """
    citation = Citation(clause="N.- PLAZO DE ENTREGA", page=1, quote="3 meses")

    assert check_citation(citation, [CUADRO_PAGE]) is CitationCheck.UNVERIFIED


def test_check_citation_keeps_checkbox_glyphs_as_tokens() -> None:
    """Protects the tokenizer decision: in a Cuadro de Características the ☒/☐ glyphs
    carry the answer, so quoting one against a page that has none is unverified --
    dropping them as punctuation would let that pass.
    """
    citation = Citation(clause="H", page=1, quote="Objeto del contrato ☒")

    assert check_citation(citation, PAGES) is CitationCheck.UNVERIFIED


def test_check_citation_unverified_for_a_page_number_out_of_range() -> None:
    """Protects the out-of-bounds page reaching the same outcome as absent text,
    rather than crashing on the token comparison the reordered check adds.
    """
    citation = Citation(clause="1", page=99, quote="Objeto del contrato")

    assert check_citation(citation, PAGES) is CitationCheck.UNVERIFIED


def test_citation_report_names_the_outcome_of_every_present_citation() -> None:
    """Protects per-field auditability: the score alone can't say *which* citation the
    pliego doesn't support, and that is the question a reader actually has.
    """
    real = Citation(clause="1", page=1, quote="Objeto del contrato")
    fabricated = Citation(clause="1", page=1, quote="texto que no existe en el pliego")
    extraction = _extraction_with_citations(
        real, fabricated, None, None, None, None, None, None, None
    )

    assert citation_report(extraction, PAGES) == {
        "economic_solvency": CitationCheck.VERIFIED,
        "technical_solvency": CitationCheck.UNVERIFIED,
    }


def test_citation_faithfulness_counts_a_reordered_citation_as_supported() -> None:
    """Protects the number the README publishes from measuring the PDF's layout: on
    `040-2026-0075` four of nine citations only matched reordered, and counting them as
    failures reported 56% for an extraction that was faithful nine times out of nine.
    """
    reordered = Citation(clause="H", page=1, quote="Garantía complementaria: ☒No ☐Sí")
    extraction = _extraction_with_citations(
        reordered, None, None, None, None, None, None, None, None
    )

    assert citation_faithfulness(extraction, [CUADRO_PAGE]) == 1.0
