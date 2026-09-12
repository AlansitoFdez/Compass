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

from compass.analysis.enums import CertificationRole


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
    """Plazo de ejecución, con las prórrogas separadas de la duración base.

    Split in 5.8. A single free-text field let the model answer half the question and
    look complete doing it: on `INN 26 002` it wrote "Durada del contracte: 1 any" with a
    correct, verbatim citation, for a contract the same pliego extends with five
    prórrogas. Nothing caught it -- the quote verified, the nine scored fields don't look
    at the deadline, and only the free-text eval (5.6) noticed. The tender's own numbers
    gave it away: 10.679 € of budget against 52.954 € of estimated value, and the
    difference is exactly the extensions. A separate, required field can't be answered by
    omission.
    """

    model_config = ConfigDict(extra="forbid")

    description: str = Field(
        description=(
            "The base execution period as stated -- how long the contract runs before any "
            "extension -- or a note that the PCAP defers this to the PPT/prescripciones "
            "técnicas if it does."
        )
    )
    extensions_allowed: bool | None = Field(
        description=(
            "Whether the pliego provides for prórrogas. True if it does, false if it "
            "states there are none ('no procede prórroga', 'sin posibilidad de "
            "prórroga'), null ONLY if the PCAP doesn't address extensions at all (e.g. it "
            "defers the whole deadline to the PPT). Do not leave this null because the "
            "extensions are merely inconvenient to find."
        )
    )
    extensions_description: str | None = Field(
        description=(
            "The extensions as stated -- how many, how long each, and the maximum total "
            "duration including them, summarized in Spanish. Null when "
            "extensions_allowed is not true."
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


class RequiredCertification(BaseModel):
    """One certification the pliego names, with the role that decides whether it blocks.

    Carries its own citation. Until 5.8 the whole list shared a single
    `certifications_citation` -- the only field in this schema that didn't pair a value
    with the evidence for it, and the one that produced wrong verdicts. A per-item
    citation means every blocking claim can be checked against the exact clause that
    makes it, the same way every other field already could.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        description=(
            "The certification as the pliego names it, e.g. 'ISO 9001', "
            "'ISO/IEC 27001', 'ENS categoría media', 'CMMI nivel 3'."
        )
    )
    role: CertificationRole = Field(
        description=(
            "Why it appears in the pliego. 'required_to_bid' ONLY when holding it is a "
            "condition of admission or part of the solvencia técnica demanded of every "
            "bidder -- if the bid is valid without it, it is not this. "
            "'award_criterion' when the pliego scores it ('se otorgarán N puntos por "
            "disponer de...'). 'administrative_paperwork' for anything every bidder "
            "files with its offer or that only the proposed awardee is asked for: DEUC, "
            "declaraciones responsables, certificados de estar al corriente con Hacienda "
            "o la Seguridad Social, documentación del requerimiento previo a la "
            "adjudicación."
        )
    )
    citation: Citation | None = Field(
        description=(
            "The clause that names this certification. Null only if the pliego names it "
            "with no locatable clause at all."
        )
    )


class PliegoExtraction(BaseModel):
    """The full closed extraction for one pliego -- the code decides the verdict from
    this, never the model.
    """

    model_config = ConfigDict(extra="forbid")

    economic_solvency: EconomicSolvency
    technical_solvency: TechnicalSolvency
    certifications: list[RequiredCertification] = Field(
        description=(
            "Every formal quality/security certification or accreditation the pliego "
            "names (e.g. ISO 9001, ISO 27001, ENS, CMMI), each with the role that says "
            "why it appears -- see `RequiredCertification.role`. List a certification "
            "even when it is only scored or only paperwork: the role is what separates "
            "them, and omitting them loses information the reader wants. Empty list if "
            "the pliego names no certification at all."
        )
    )
    award_criteria: AwardCriteria
    guarantees: Guarantees
    execution_deadline: ExecutionDeadline
    submission_deadline: SubmissionDeadline
    subcontracting: Subcontracting
    lots: Lots
