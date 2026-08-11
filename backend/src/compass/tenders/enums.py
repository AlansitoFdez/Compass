"""Closed-set vocabularies shared by the ORM model and the Pydantic schema.

`procedure_type` is deliberately NOT an enum here: the design doc lists it with
a trailing "..." (open set — Spanish procurement law defines more procedure
types than the ones named), while `status` and `contract_type` are closed
lists. Enforcing an enum on an open set would break real ingestion the first
time PLACSP sends a legitimate value we didn't anticipate.
"""

from enum import StrEnum


class ContractType(StrEnum):
    SERVICES = "services"
    SUPPLIES = "supplies"
    WORKS = "works"


class TenderStatus(StrEnum):
    PRIOR_NOTICE = "prior_notice"
    OPEN_FOR_SUBMISSION = "open_for_submission"
    PENDING_AWARD = "pending_award"
    AWARDED = "awarded"
    RESOLVED = "resolved"
