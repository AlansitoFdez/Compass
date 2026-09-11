"""Pydantic schemas for the fused matches -- what GET /matches (2.6) serializes."""

from pydantic import BaseModel, ConfigDict

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


class FunnelCountsSchema(BaseModel):
    """Survivors at each cumulative stage of the funnel's hard filters (Etapa 1).

    The reduction this project exists to perform, as numbers: the whole ingested corpus,
    then what is still open for submission, then what overlaps the provider's CPV codes,
    then its budget range, then its geographic scope. Each count includes every filter
    before it, so the sequence never increases -- and a stage where the provider sets no
    filter simply repeats the previous count.

    Serialized so the dashboard can state the reduction instead of asserting it, and so an
    empty result can say *which* stage emptied it rather than just "no matches".
    """

    model_config = ConfigDict(from_attributes=True)

    total: int
    after_status: int
    after_cpv: int
    after_budget: int
    after_location: int


class MatchListResponse(BaseModel):
    """Envelope for GET /matches -- no `offset`, unlike `TenderListResponse`: the point of
    this endpoint is "here are your best matches", not paginating a large corpus.

    `total` is how many tenders survive the funnel, not how many came back in this
    response -- that's `returned`. Until 5.2 this field was `len(items)`, so it always
    equalled `limit` and the dashboard's "N resultados del embudo" was really printing its
    own page size.
    """

    items: list[MatchSchema]
    total: int
    returned: int
    limit: int
    funnel: FunnelCountsSchema
