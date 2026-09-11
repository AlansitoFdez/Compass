"""Tests for the free-text eval's sample building -- everything about 5.6 that a judge
model isn't needed for.

The eval itself (`freetext_eval.py`) spends OpenRouter quota on every sample and runs by
hand; what can be protected here is the half that decides *what gets judged at all*: which
descriptions are scoreable, which page text each one is judged against, and that a
description with nothing to judge it against is reported as such instead of scored badly.
"""

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
from compass.analysis.freetext import (
    DESCRIPTION_FIELDS,
    SkipReason,
    build_samples,
    context_window,
)

PAGES = [f"texto de la página {number}" for number in range(1, 11)]


def _citation(page: int) -> Citation:
    return Citation(clause="1", page=page, quote="cita")


def _extraction(
    *,
    economic: Citation | None = None,
    technical: Citation | None = None,
    guarantees: Citation | None = None,
    execution: Citation | None = None,
    submission: Citation | None = None,
    subcontracting: Citation | None = None,
    lots: Citation | None = None,
) -> PliegoExtraction:
    """An extraction whose seven descriptions all differ, carrying the given citations.

    Each description names its own field on purpose: it's what lets a test tell whether
    `DESCRIPTION_FIELDS` reads the field it claims to, which seven near-identical accessor
    lambdas otherwise make easy to get wrong and impossible to see.
    """
    return PliegoExtraction(
        economic_solvency=EconomicSolvency(
            minimum_annual_turnover_eur=None,
            description="solvencia económica",
            citation=economic,
        ),
        technical_solvency=TechnicalSolvency(
            minimum_amount_eur=None, description="solvencia técnica", citation=technical
        ),
        certifications=[],
        certifications_citation=None,
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[AwardCriterion(name="Precio", points=100, is_price=True)],
            citation=None,
        ),
        guarantees=Guarantees(
            provisional_required=False,
            definitive_percentage=None,
            description="garantías",
            citation=guarantees,
        ),
        execution_deadline=ExecutionDeadline(description="plazo de ejecución", citation=execution),
        submission_deadline=SubmissionDeadline(
            description="plazo de presentación", citation=submission
        ),
        subcontracting=Subcontracting(
            allowed=True, description="subcontratación", citation=subcontracting
        ),
        lots=Lots(
            divided_into_lots=False,
            can_bid_partial_lots=None,
            description="lotes",
            citation=lots,
        ),
    )


def test_context_window_surrounds_the_cited_page() -> None:
    """Protects the reason the window exists at all: a clause that starts on the cited
    page routinely finishes on the next one, so both neighbours travel with it.
    """
    assert context_window(PAGES, 5) == [PAGES[3], PAGES[4], PAGES[5]]


def test_context_window_clips_at_both_ends_of_the_document() -> None:
    """A citation on the first or last page must still produce a usable context instead
    of running off the document and losing the cited page itself.
    """
    assert context_window(PAGES, 1) == [PAGES[0], PAGES[1]]
    assert context_window(PAGES, len(PAGES)) == [PAGES[-2], PAGES[-1]]


def test_context_window_is_empty_for_a_page_the_document_does_not_have() -> None:
    """A hallucinated page number has to be distinguishable from a real one: an empty
    window is what makes `build_samples` skip the description instead of judging it
    against whatever text happened to be nearby.
    """
    assert context_window(PAGES, len(PAGES) + 1) == []
    assert context_window(PAGES, 0) == []


def test_build_samples_reads_each_description_from_its_own_field() -> None:
    """Guards the seven accessor pairs against the copy-paste that would make two fields
    read the same value -- silently scoring the same text twice and never the other one.
    """
    extraction = _extraction(
        economic=_citation(1),
        technical=_citation(2),
        guarantees=_citation(3),
        execution=_citation(4),
        submission=_citation(5),
        subcontracting=_citation(6),
        lots=_citation(7),
    )

    samples, skipped = build_samples(extraction, PAGES)

    assert not skipped
    assert len(samples) == len(DESCRIPTION_FIELDS)
    assert {sample.field: sample.description for sample in samples} == {
        "economic_solvency.description": "solvencia económica",
        "technical_solvency.description": "solvencia técnica",
        "guarantees.description": "garantías",
        "execution_deadline.description": "plazo de ejecución",
        "submission_deadline.description": "plazo de presentación",
        "subcontracting.description": "subcontratación",
        "lots.description": "lotes",
    }


def test_build_samples_judges_a_description_against_its_own_cited_pages() -> None:
    """The whole point of citing a page: each description is judged against that page's
    window, not against the pliego at large, where a judge finds support for anything.
    """
    samples, _ = build_samples(_extraction(guarantees=_citation(4)), PAGES)

    (sample,) = samples
    assert sample.field == "guarantees.description"
    assert sample.cited_page == 4
    assert sample.contexts == [PAGES[2], PAGES[3], PAGES[4]]


def test_build_samples_skips_an_uncited_description_instead_of_scoring_it_zero() -> None:
    """A `None` citation means the pliego doesn't address that point, so there is nothing
    to be faithful to. Scoring it 0.0 would claim the model invented the description.
    """
    samples, skipped = build_samples(_extraction(economic=_citation(2)), PAGES)

    assert [sample.field for sample in samples] == ["economic_solvency.description"]
    assert {entry.reason for entry in skipped} == {SkipReason.NO_CITATION}
    assert len(skipped) == len(DESCRIPTION_FIELDS) - 1


def test_build_samples_skips_a_citation_pointing_outside_the_document() -> None:
    """A page number the document doesn't have is reported as unjudgeable rather than
    judged against an empty context, which every claim would fail.
    """
    _, skipped = build_samples(_extraction(lots=_citation(99)), PAGES)

    out_of_range = [entry for entry in skipped if entry.reason == SkipReason.PAGE_OUT_OF_RANGE]
    assert [entry.field for entry in out_of_range] == ["lots.description"]
