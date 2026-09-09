"""Pydantic schema for a pliego analysis -- read-facing shape, mirrors `TenderAnalysis`."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from compass.analysis.enums import AnalysisStatus, Verdict
from compass.analysis.extraction_schema import Citation


class TenderAnalysisSchema(BaseModel):
    """A `TenderAnalysis` row, validated -- same `from_attributes=True` pattern as
    `TenderSchema`/`ProviderSchema`, so it builds straight from the ORM row.
    """

    model_config = ConfigDict(from_attributes=True)

    pdf_hash: str
    expediente: str
    status: AnalysisStatus
    extraction: dict[str, object] | None = None
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
