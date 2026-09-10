"""Closed Pydantic schema for a pliego extraction -- the shape the LLM must fill in.

Real PCAPs vary in whether each field is a hard numeric threshold or only free text (see
the golden set in `analysis/golden_set.py`, hand-annotated from four real PCAPs for
3.4). Every field pairs its value with a `Citation` so the result is verifiable in Python
against the parsed text (3.5) instead of trusted at face value -- `citation` is `None`
only when the pliego genuinely doesn't address that point (e.g. a submission deadline
left to the anuncio de licitación rather than restated in the PCAP itself).

The LLM only ever fills this schema; nothing here computes a verdict -- that's 3.7,
comparing this extraction against a `Provider` in plain Python.
"""

from pydantic import BaseModel, ConfigDict, Field


class Citation(BaseModel):
    """Where an extracted value comes from in the pliego -- what 3.5 verifies against the
    parsed text.
    """

    model_config = ConfigDict(extra="forbid")

    clause: str = Field(
        description="Clause number/heading as it appears in the pliego, e.g. '12.2' or '4.3.1'."
    )
    page: int = Field(description="Page where the clause begins.")
    quote: str = Field(
        description="Verbatim text from the pliego that supports the extracted value."
    )


class EconomicSolvency(BaseModel):
    """Solvencia económica y financiera exigida."""

    model_config = ConfigDict(extra="forbid")

    minimum_annual_turnover_eur: float | None = Field(
        description=(
            "Minimum required annual turnover in euros, if the pliego states one "
            "explicitly. Null if solvency is required only via classification "
            "(grupo/subgrupo) or isn't quantified in euros."
        )
    )
    description: str = Field(
        description="The solvency requirement as stated, summarized in Spanish."
    )
    citation: Citation | None = Field(
        description="Null only if the pliego states no economic solvency requirement at all."
    )


class TechnicalSolvency(BaseModel):
    """Solvencia técnica o profesional exigida."""

    model_config = ConfigDict(extra="forbid")

    minimum_amount_eur: float | None = Field(
        description="Minimum cumulative amount of similar past work required, in euros, if stated."
    )
    description: str = Field(
        description="The solvency requirement as stated, summarized in Spanish."
    )
    citation: Citation | None = Field(
        description="Null only if the pliego states no technical solvency requirement at all."
    )


class AwardCriterion(BaseModel):
    """One line item of the award criteria breakdown."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        description="The criterion's name as stated, e.g. 'Precio' or 'Experiencia del equipo'."
    )
    points: float = Field(description="Points assigned to this criterion.")
    is_price: bool = Field(description="Whether this criterion is the economic/price offer.")


class AwardCriteria(BaseModel):
    """Criterios de adjudicación con sus porcentajes (precio vs. técnica)."""

    model_config = ConfigDict(extra="forbid")

    total_points: float = Field(description="Total points across all criteria, usually 100.")
    criteria: list[AwardCriterion] = Field(
        description="Every award criterion listed, in the order the pliego gives them."
    )
    citation: Citation | None = Field(
        description="Null only if the pliego doesn't specify award criteria at all."
    )


class Guarantees(BaseModel):
    """Garantía provisional y definitiva."""

    model_config = ConfigDict(extra="forbid")

    provisional_required: bool = Field(
        description="Whether a provisional guarantee is required to bid."
    )
    definitive_percentage: float | None = Field(
        description="Definitive guarantee as a percentage of the awarded price, if the pliego "
        "states one."
    )
    description: str = Field(
        description="The guarantee requirements as stated, summarized in Spanish."
    )
    citation: Citation | None = Field(
        description="Null only if the pliego doesn't address guarantees at all."
    )


class ExecutionDeadline(BaseModel):
    """Plazo de ejecución."""

    model_config = ConfigDict(extra="forbid")

    description: str = Field(
        description=(
            "Execution period as stated -- duration and any extensions, or a note that "
            "the PCAP defers this to the PPT/prescripciones técnicas if it does."
        )
    )
    citation: Citation | None = Field(
        description="Null only if the pliego states no execution deadline at all."
    )


class SubmissionDeadline(BaseModel):
    """Fecha y hora límite de presentación."""

    model_config = ConfigDict(extra="forbid")

    description: str = Field(
        description=(
            "Submission deadline as stated in the PCAP -- an explicit date, a relative "
            "period ('15 días naturales desde publicación del anuncio'), or a note that "
            "the PCAP defers this entirely to the anuncio de licitación / plataforma."
        )
    )
    citation: Citation | None = Field(
        description="Null only if the pliego says nothing about the submission deadline."
    )


class Subcontracting(BaseModel):
    """Admisión de subcontratación."""

    model_config = ConfigDict(extra="forbid")

    allowed: bool = Field(description="Whether subcontracting is permitted at all.")
    description: str = Field(
        description="The subcontracting conditions as stated, summarized in Spanish."
    )
    citation: Citation | None = Field(
        description="Null only if the pliego doesn't address subcontracting at all."
    )


class Lots(BaseModel):
    """Lotes y si se puede optar a lotes sueltos."""

    model_config = ConfigDict(extra="forbid")

    divided_into_lots: bool = Field(description="Whether the contract is divided into lots.")
    can_bid_partial_lots: bool | None = Field(
        description="Whether a bidder can bid on individual lots rather than all of "
        "them. Null when divided_into_lots is false."
    )
    description: str = Field(
        description="The lot structure (or its absence, with the pliego's own justification) "
        "summarized in Spanish."
    )
    citation: Citation | None = Field(
        description="Null only if the pliego says nothing about lots at all."
    )


class PliegoExtraction(BaseModel):
    """The full closed extraction for one pliego -- the code decides the verdict from
    this, never the model.
    """

    model_config = ConfigDict(extra="forbid")

    economic_solvency: EconomicSolvency
    technical_solvency: TechnicalSolvency
    certifications: list[str] = Field(
        description=(
            "Formal quality/security certifications or accreditations the provider must "
            "already hold (e.g. ISO 9001, ISO 27001, ENS, CMMI). Do NOT include generic "
            "bidding paperwork or administrative declarations submitted with the offer "
            "itself (DEUC/Documento Europeo Único de Contratación, declaraciones "
            "responsables, declaraciones de protección de datos) -- those aren't "
            "certifications a provider holds in advance, every bidder fills them out. "
            "Empty list if no formal certification is required."
        )
    )
    certifications_citation: Citation | None = Field(
        description="Null only if the pliego requires no certifications at all."
    )
    award_criteria: AwardCriteria
    guarantees: Guarantees
    execution_deadline: ExecutionDeadline
    submission_deadline: SubmissionDeadline
    subcontracting: Subcontracting
    lots: Lots
