"""SQLAlchemy ORM model for a pliego (PCAP) analysis."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from compass.analysis.enums import AnalysisStatus
from compass.core.db import Base

# How long an analysis may sit in `IN_PROGRESS` before it is treated as dead. Matches the
# Redis lock the Celery task holds (`analysis.tasks.LOCK_TIMEOUT_SECONDS`, which imports
# this): once that lock has expired, no run is protecting this row any more, so a row still
# claiming to be in progress is a worker that died mid-analysis -- not work still happening.
STALE_AFTER_SECONDS = 900


class TenderAnalysis(Base):
    """One pliego analysis per tender, keyed by `expediente`.

    Keyed by the tender, not by the document: until 5.2 the primary key was
    `pdf_hash`, which read well as a cache but broke both directions of the
    real access pattern. Two tenders whose PCAP happened to be byte-identical
    collided on one row -- the second one's `GET /analysis`, which looks up by
    expediente, then found nothing and reported "never analyzed" forever while
    the task kept hitting the cache and writing nothing. And two such analyses
    running at once both inserted the same key, so the second transaction died
    with an `IntegrityError`.

    The cache didn't need that key. What's worth reusing is the *extraction* --
    the expensive, provider-agnostic half (see docs/phases/phase3/phase3.md) --
    and `repository.find_cached_extraction` finds it by `pdf_hash` on any
    tender's row, then copies it onto this one. Same LLM call saved, without
    two tenders sharing an identity.

    `pdf_hash` is nullable because a row can exist before (or without) a
    readable document: a PCAP that exceeds the download cap is recorded as
    `NOT_ANALYZABLE` with nothing to hash.

    No verdict lives here: it's computed from `extraction` against whichever
    `Provider` is current at read time, not stored -- storing it would mean
    invalidating it on every profile edit, for a comparison cheap enough
    (pure Python, no LLM) that there's nothing worth caching yet.
    """

    __tablename__ = "tender_analyses"
    __table_args__ = (
        # The extraction cache's only lookup: "has this exact document already
        # been analyzed, for any tender". No longer a primary key, so it needs
        # an index of its own.
        Index("ix_tender_analyses_pdf_hash", "pdf_hash"),
    )

    expediente: Mapped[str] = mapped_column(
        String, ForeignKey("tenders.expediente"), primary_key=True
    )
    pdf_hash: Mapped[str | None] = mapped_column(String(64))

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
    # The fraction of extraction's citations that verify against the parsed
    # pliego text (3.5's `citation_faithfulness`), computed in Python and
    # tracked by `regression_eval` (4.4) -- not by RAGAS, which 5.6 aimed at
    # the free-text descriptions instead. Nullable for the same reason as
    # `extraction`: only set once the graph reaches `verify`.
    citation_faithfulness: Mapped[float | None] = mapped_column(Float)
    error_message: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
