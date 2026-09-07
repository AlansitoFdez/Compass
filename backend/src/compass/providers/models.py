"""SQLAlchemy ORM model for the provider profile -- a singleton row, not one per user.

Multi-tenant support is explicitly out of v1 scope (see CLAUDE.md, "No hagas"),
so there is exactly one profile: this supplier's own description, CPV
interests, budget range, revenue, and certifications, matched against
incoming tenders from Phase 2 onward.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from compass.core.db import Base

# The fixed primary key value for the single row this table ever holds. A
# literal string, not an autoincrement id, so the singleton constraint is
# visible in the schema itself: `repository.py` always reads/writes this
# exact key, never a range of possible ids.
PROVIDER_ID = "default"


class Provider(Base):
    """The single provider profile this instance of Compass serves.

    Always exactly one row, keyed by the fixed `PROVIDER_ID` -- see its
    docstring. `repository.py` enforces this by only exposing
    `get_provider()`/`upsert_provider()`, never a plain `create`.
    """

    __tablename__ = "providers"

    id: Mapped[str] = mapped_column(String, primary_key=True)

    description: Mapped[str] = mapped_column(Text)
    cpv_codes: Mapped[list[str]] = mapped_column(ARRAY(String))

    min_budget: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    max_budget: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    annual_revenue: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    certifications: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
