"""SQLAlchemy ORM model for a pliego (PCAP) analysis."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from compass.analysis.enums import AnalysisStatus
from compass.core.db import Base


class TenderAnalysis(Base):
    """One pliego analysis, keyed by the PDF's own content hash -- not by `expediente`.

    Caching by `pdf_hash` (not by tender) is deliberate: it's the extraction
    -- the expensive, provider-agnostic half of an analysis -- that gets
    cached this way (see docs/phases/phase3/phase3.md). Two different
    expedientes whose PCAP happens to be byte-identical share one row. No
    verdict lives here: it's computed from `extraction` against whichever
    `Provider` is current at read time, not stored -- storing it would mean
    invalidating it on every profile edit, for a comparison cheap enough
    (pure Python, no LLM) that there's nothing worth caching yet.
    """

    __tablename__ = "tender_analyses"
    __table_args__ = (
        # Every lookup so far is "has this tender's current PCAP already been
        # analyzed" -- by expediente, not by hash.
        Index("ix_tender_analyses_expediente", "expediente"),
    )

    pdf_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    expediente: Mapped[str] = mapped_column(String, ForeignKey("tenders.expediente"))

    status: Mapped[AnalysisStatus] = mapped_column(
        SqlEnum(
            AnalysisStatus,
            native_enum=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        )
    )

    # Untyped JSON for now -- the closed Pydantic extraction schema (clause
    # number, page, quote, solvency figures, etc.) lands in 3.4. Nullable:
    # empty until the status reaches COMPLETED.
    extraction: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
