"""Closed-set vocabulary for where a pliego analysis sits in its own pipeline."""

from enum import StrEnum


class AnalysisStatus(StrEnum):
    """The lifecycle of one `TenderAnalysis` row.

    `NOT_ANALYZABLE` is terminal, not a failure to retry: a scanned PCAP with
    no text layer is detected once (Phase 3.2) and never re-attempted -- v1
    does no OCR (see docs/phases/phase3/phase3.md).
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NOT_ANALYZABLE = "not_analyzable"


class Verdict(StrEnum):
    """Whether a provider can bid on a tender, per `analysis.verdict.compute_verdict`.

    Never set by the LLM -- see `docs/phases/phase3/phase3.md`, "el LLM extrae, el
    código decide". Computed at read time from a `PliegoExtraction` and the current
    `Provider`, never stored (same reasoning as `TenderAnalysis` storing no verdict).
    """

    APTO = "apto"
    APTO_CON_RESERVAS = "apto_con_reservas"
    NO_APTO = "no_apto"
