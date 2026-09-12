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


class CertificationRole(StrEnum):
    """Why a certification appears in the pliego at all -- which decides whether it can
    block a bid.

    Added in 5.8 after a plain `list[str]` produced false NO APTO verdicts on four of the
    six analyses in the database. A PCAP names certifications in at least three roles and
    only one of them is a condition to bid, but the field had nowhere to say which, so
    `verdict.compute_verdict` treated every string as a requirement:

    - `INN 26 002` was rejected over an ISO/IEC 20000 the pliego only *scores*
      ("s'atorgaran 6 punts en el cas de disposar qualsevol dels següents certificats").
    - `2026/20` was rejected over three certificados de estar al corriente con Hacienda y
      la Seguridad Social -- the model's own citation said where they came from,
      "Cláusula 27ª. Requerimiento a la primera empresa clasificada".

    Both are silent false negatives: a tender the provider could have bid on, discarded
    without a word. That is the most expensive mistake this product can make, which is
    why the distinction is in the schema rather than in a prompt instruction.
    """

    REQUIRED_TO_BID = "required_to_bid"
    """A condition of admission: without it the bid is excluded. The only blocking role."""

    AWARD_CRITERION = "award_criterion"
    """Scored, not demanded -- holding it earns points, lacking it costs points, and
    nothing more.
    """

    ADMINISTRATIVE_PAPERWORK = "administrative_paperwork"
    """Paperwork every bidder files with its offer, or that only the proposed awardee is
    asked for: DEUC, declaraciones responsables, certificados de estar al corriente. Not
    something a provider holds in advance.
    """


class Verdict(StrEnum):
    """Whether a provider can bid on a tender, per `analysis.verdict.compute_verdict`.

    Never set by the LLM -- see `docs/phases/phase3/phase3.md`, "el LLM extrae, el
    código decide". Computed at read time from a `PliegoExtraction` and the current
    `Provider`, never stored (same reasoning as `TenderAnalysis` storing no verdict).
    """

    APTO = "apto"
    APTO_CON_RESERVAS = "apto_con_reservas"
    NO_APTO = "no_apto"
