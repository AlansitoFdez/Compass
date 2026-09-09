"""Pydantic schema for a pliego analysis -- read-facing shape, mirrors `TenderAnalysis`."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from compass.analysis.enums import AnalysisStatus


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
