"""Closed-set vocabularies shared by the ORM model and the Pydantic schema.

`procedure_type` is deliberately NOT an enum here: the design doc lists it with
a trailing "..." (open set — Spanish procurement law defines more procedure
types than the ones named), while `status` and `contract_type` are closed
lists. Enforcing an enum on an open set would break real ingestion the first
time PLACSP sends a legitimate value we didn't anticipate.
"""

from enum import StrEnum


class ContractType(StrEnum):
    """The closed set of contract types PLACSP's CODICE schema defines."""

    SERVICES = "services"
    SUPPLIES = "supplies"
    WORKS = "works"
    PUBLIC_SERVICES_MANAGEMENT = "public_services_management"
    SERVICES_CONCESSION = "services_concession"
    PUBLIC_WORKS_CONCESSION = "public_works_concession"
    WORKS_CONCESSION = "works_concession"
    PUBLIC_PRIVATE_COLLABORATION = "public_private_collaboration"
    SPECIAL_ADMINISTRATIVE = "special_administrative"
    PRIVATE = "private"
    PATRIMONIAL = "patrimonial"


class TenderStatus(StrEnum):
    """Where a tender sits in its own lifecycle, as PLACSP reports it.

    Order matters here: PLACSP republishes the same expediente every time it
    changes state, and a status change is what tells the upsert whether a
    tender that was `OPEN_FOR_SUBMISSION` yesterday is now `CANCELLED` — never
    a physical delete.
    """

    PRIOR_NOTICE = "prior_notice"
    OPEN_FOR_SUBMISSION = "open_for_submission"
    PENDING_AWARD = "pending_award"
    AWARDED = "awarded"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"
