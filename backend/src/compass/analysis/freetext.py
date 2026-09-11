"""Builds the samples a free-text faithfulness eval scores -- the half `scoring.py` leaves out.

`scoring.score_extraction` compares nine numeric/boolean/list subfields against a
hand-annotated golden-set entry, character for character where it can. The seven
`description` fields can't be checked that way: two correct summaries of the same clause
share almost no substrings, so a string comparison would fail every one of them.

What *can* be checked is whether each description is grounded in the pliego at all --
and every description arrives with a citation saying which page grounds it. So a sample
is the description, the question it answers, and the text of the cited page plus its
neighbours. Scoring those samples is `freetext_eval.py`'s job (it needs a judge model);
building them needs nothing but the extraction and the pages, which is why it lives here
and is tested without a network.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from compass.analysis.extraction_schema import Citation, PliegoExtraction

# How many pages on either side of the cited one go into a sample's context. A PCAP
# clause routinely starts near the foot of one page and finishes on the next, and the
# model cites where the clause *begins*, so the page alone would leave half the
# requirement outside the context and score a correct description as unfaithful.
#
# Deliberately not the whole pliego: a judge handed 20-120 pages finds some sentence
# somewhere that supports nearly any claim, and the metric saturates at 1.0 without
# distinguishing a good description from a bad one.
CONTEXT_RADIUS_PAGES = 1


class SkipReason(StrEnum):
    """Why a description couldn't be scored -- never the same thing as scoring badly."""

    NO_CITATION = "sin cita"
    PAGE_OUT_OF_RANGE = "la página citada no existe en el documento"


@dataclass(frozen=True)
class DescriptionField:
    """One free-text field of the extraction, and how to reach it.

    `question` is what the description is treated as answering. A faithfulness judge
    splits the response into claims with the question as context, so it has to name the
    same thing the pliego does -- in Spanish, like the descriptions themselves.
    """

    name: str
    question: str
    description_of: Callable[[PliegoExtraction], str]
    citation_of: Callable[[PliegoExtraction], Citation | None]


DESCRIPTION_FIELDS: tuple[DescriptionField, ...] = (
    DescriptionField(
        "economic_solvency.description",
        "¿Qué solvencia económica y financiera exige el pliego para poder licitar?",
        lambda e: e.economic_solvency.description,
        lambda e: e.economic_solvency.citation,
    ),
    DescriptionField(
        "technical_solvency.description",
        "¿Qué solvencia técnica o profesional exige el pliego para poder licitar?",
        lambda e: e.technical_solvency.description,
        lambda e: e.technical_solvency.citation,
    ),
    DescriptionField(
        "guarantees.description",
        "¿Qué garantías exige el pliego, provisional y definitiva?",
        lambda e: e.guarantees.description,
        lambda e: e.guarantees.citation,
    ),
    DescriptionField(
        "execution_deadline.description",
        "¿Cuál es el plazo de ejecución del contrato y qué prórrogas admite?",
        lambda e: e.execution_deadline.description,
        lambda e: e.execution_deadline.citation,
    ),
    DescriptionField(
        "submission_deadline.description",
        "¿Cuál es la fecha límite para presentar ofertas?",
        lambda e: e.submission_deadline.description,
        lambda e: e.submission_deadline.citation,
    ),
    DescriptionField(
        "subcontracting.description",
        "¿En qué condiciones admite el pliego la subcontratación?",
        lambda e: e.subcontracting.description,
        lambda e: e.subcontracting.citation,
    ),
    DescriptionField(
        "lots.description",
        "¿Está el contrato dividido en lotes y en qué términos se puede licitar a ellos?",
        lambda e: e.lots.description,
        lambda e: e.lots.citation,
    ),
)


@dataclass(frozen=True)
class FreeTextSample:
    """One description ready to be judged against the pages that should support it."""

    field: str
    question: str
    description: str
    contexts: list[str]
    cited_page: int


@dataclass(frozen=True)
class SkippedDescription:
    """A description left unscored, with the reason it couldn't be judged."""

    field: str
    reason: SkipReason


def context_window(
    pages: list[str], cited_page: int, *, radius: int = CONTEXT_RADIUS_PAGES
) -> list[str]:
    """The text of the cited page and its neighbours, in document order.

    Args:
        pages: Per-page extracted text, 1-indexed the way `Citation.page` is
            (from `document.extract_pages`).
        cited_page: The page the citation claims, 1-indexed.
        radius: How many pages to include on either side.

    Returns:
        The pages inside the window that actually exist, clipped at both ends of the
        document. Empty if `cited_page` is outside the document altogether.
    """
    if not (1 <= cited_page <= len(pages)):
        return []
    first = max(1, cited_page - radius)
    last = min(len(pages), cited_page + radius)
    return pages[first - 1 : last]


def build_samples(
    extraction: PliegoExtraction, pages: list[str]
) -> tuple[list[FreeTextSample], list[SkippedDescription]]:
    """Splits an extraction's seven descriptions into what can be judged and what can't.

    A description with no citation isn't a failure: the field's citation is `None`
    exactly when the pliego doesn't address that point, and there is then nothing to be
    faithful *to*. Scoring it 0.0 would read as "the model made this up", which is a
    different claim, so it is reported separately instead.

    Args:
        extraction: A validated extraction, as stored in `TenderAnalysis.extraction`.
        pages: Per-page text of that same pliego.

    Returns:
        The scoreable samples, and the descriptions skipped with their reason.
    """
    samples: list[FreeTextSample] = []
    skipped: list[SkippedDescription] = []

    for field in DESCRIPTION_FIELDS:
        citation = field.citation_of(extraction)
        if citation is None:
            skipped.append(SkippedDescription(field.name, SkipReason.NO_CITATION))
            continue

        contexts = context_window(pages, citation.page)
        if not contexts:
            skipped.append(SkippedDescription(field.name, SkipReason.PAGE_OUT_OF_RANGE))
            continue

        samples.append(
            FreeTextSample(
                field=field.name,
                question=field.question,
                description=field.description_of(extraction),
                contexts=contexts,
                cited_page=citation.page,
            )
        )

    return samples, skipped
