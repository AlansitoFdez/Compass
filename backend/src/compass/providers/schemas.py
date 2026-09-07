"""Pydantic schema for the provider profile.

The shape shared by the seed script and, later, the API.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ProviderSchema(BaseModel):
    """The provider's own profile: what they do, and the tenders they're willing to bid on.

    `id` is deliberately absent here -- it's `models.Provider`'s persistence
    detail (the fixed singleton key), not a domain fact about the provider.
    `from_attributes=True` lets this be built straight from a fetched
    `Provider` row, the same pattern `TenderSchema` uses.
    """

    model_config = ConfigDict(from_attributes=True)

    description: str
    cpv_codes: list[str]

    min_budget: Decimal | None = None
    max_budget: Decimal | None = None
    annual_revenue: Decimal | None = None
    certifications: list[str] | None = None
    locations: list[str] | None = None
