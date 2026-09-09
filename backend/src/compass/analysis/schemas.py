"""Pydantic schema for a pliego analysis -- read-facing shape, mirrors `TenderAnalysis`."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from compass.analysis.enums import AnalysisStatus, Verdict
from compass.analysis.extraction_schema import Citation, PliegoExtraction


class TenderAnalysisSchema(BaseModel):
    """A `TenderAnalysis` row, validated -- same `from_attributes=True` pattern as
    `TenderSchema`/`ProviderSchema`, so it builds straight from the ORM row.
    """

    model_config = ConfigDict(from_attributes=True)

    pdf_hash: str
    expediente: str
    status: AnalysisStatus
    extraction: dict[str, object] | None = None
    citation_faithfulness: float | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class VerdictReason(BaseModel):
    """One concrete reason behind a `VerdictResult` -- a blocker or a reservation, never
    an `APTO` with nothing to say.
    """

    model_config = ConfigDict(from_attributes=True)

    detail: str
    citation: Citation | None = None


class VerdictResult(BaseModel):
    """The output of `analysis.verdict.compute_verdict`: a `Verdict` plus every reason
    that produced it, each traceable to the clause that caused it.
    """

    model_config = ConfigDict(from_attributes=True)

    verdict: Verdict
    reasons: list[VerdictReason]


class TenderAnalysisResultSchema(BaseModel):
    """The `GET /tenders/{expediente}/analysis` response: the analysis itself, plus the
    verdict, computed live against whichever `Provider` is current -- never stored (see
    `models.TenderAnalysis`), so this is the only place it's built, at read time.

    `verdict` is `None` until `status` reaches `COMPLETED` -- there's nothing to compare
    yet, so returning `APTO` by default would be misleading rather than merely absent.
    """

    expediente: str
    status: AnalysisStatus
    extraction: PliegoExtraction | None = None
    citation_faithfulness: float | None = None
    error_message: str | None = None
    verdict: VerdictResult | None = None
