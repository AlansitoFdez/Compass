"""Pydantic schemas for the fused matches -- what GET /matches (2.6) serializes."""

from pydantic import BaseModel

from compass.tenders.schemas import TenderSchema


class MatchSchema(BaseModel):
    """One fused match: the tender, its RRF score, and the "motivo de encaje" -- which
    recoverer(s) surfaced it, with their raw scores. A `None` pair means that
    recoverer didn't surface this tender at all.
    """

    tender: TenderSchema
    rrf_score: float
    lexical_rank: int | None = None
    lexical_score: float | None = None
    vector_rank: int | None = None
    vector_distance: float | None = None


class MatchListResponse(BaseModel):
    """Envelope for GET /matches -- no `offset`, unlike `TenderListResponse`: the point of
    this endpoint is "here are your best matches", not paginating a large corpus.
    """

    items: list[MatchSchema]
    total: int
    limit: int
