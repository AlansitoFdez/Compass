"""Etapa 1 of the matching funnel: deterministic hard filters in SQL, no ranking involved.

Every filter here is AND'd and derived straight from the provider's own
profile -- CPV, budget range, and geographic scope -- plus a fixed status
filter ("en plazo": still open for submission). Nothing here ranks or scores
a tender; a tender either survives every filter or it doesn't. Semantic
ranking is Etapa 2, a later subphase.
"""

from dataclasses import dataclass

from sqlalchemy import ColumnElement, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from compass.providers.models import Provider
from compass.tenders.enums import TenderStatus
from compass.tenders.models import Tender


@dataclass
class FunnelStageCounts:
    """How many tenders survive each cumulative hard-filter stage, for the Phase 2 README numbers.

    Each count includes every filter before it (e.g. `after_budget` already
    reflects the status and CPV filters too), so the sequence is always
    non-increasing. `after_budget`/`after_location` equal the previous
    stage's count whenever the provider doesn't set that filter (no
    `min_budget`/`max_budget`, or no `locations`) -- not applying a filter
    is not the same as it matching zero rows.

    Attributes:
        total: Every tender in the table, before any filter.
        after_status: Surviving `status == open_for_submission`.
        after_cpv: Also surviving the CPV overlap with the provider.
        after_budget: Also surviving the provider's budget range, if any.
        after_location: Also surviving the provider's geographic scope, if any.
    """

    total: int
    after_status: int
    after_cpv: int
    after_budget: int
    after_location: int


def _status_filter() -> ColumnElement[bool]:
    """Only tenders still open for submission ("en plazo") ever reach a provider."""
    return Tender.status == TenderStatus.OPEN_FOR_SUBMISSION


def _cpv_filter(provider: Provider) -> ColumnElement[bool]:
    """Any CPV shared between the tender and the provider's interests is enough to match.

    `overlap` compiles to Postgres' `&&` on the array, which the existing
    `ix_tenders_cpv_codes_gin` index (1.11) already speeds up.
    """
    # ARRAY.Comparator.overlap() isn't precisely typed upstream and returns
    # Any; the explicit annotation here (not a cast) is what tells mypy the
    # real, already-correct runtime type instead of letting Any escape.
    overlap: ColumnElement[bool] = Tender.cpv_codes.overlap(provider.cpv_codes)
    return overlap


def _budget_filter(provider: Provider) -> ColumnElement[bool] | None:
    """The provider's budget range, or `None` if neither bound is set (no filtering).

    A tender with no `budget_with_vat` at all is excluded whenever the
    provider sets a bound -- comparing NULL against `>=`/`<=` evaluates to
    NULL in SQL, which `where()` treats as "doesn't match", so an
    unverifiable tender never gets in for free.
    """
    if provider.min_budget is None and provider.max_budget is None:
        return None

    conditions: list[ColumnElement[bool]] = []
    if provider.min_budget is not None:
        conditions.append(Tender.budget_with_vat >= provider.min_budget)
    if provider.max_budget is not None:
        conditions.append(Tender.budget_with_vat <= provider.max_budget)
    return and_(*conditions)


def _location_filter(provider: Provider) -> ColumnElement[bool] | None:
    """The provider's geographic scope, or `None` if unrestricted (`locations` is empty/unset).

    Same NULL-excludes-by-default reasoning as `_budget_filter`: a tender
    with no `location` at all doesn't match a provider that did restrict
    to specific provinces.
    """
    if not provider.locations:
        return None
    return Tender.location.in_(provider.locations)


def _build_filters(provider: Provider) -> list[ColumnElement[bool]]:
    """Every hard filter that applies to `provider`, in the fixed order the funnel checks them."""
    filters = [_status_filter(), _cpv_filter(provider)]

    budget_filter = _budget_filter(provider)
    if budget_filter is not None:
        filters.append(budget_filter)

    location_filter = _location_filter(provider)
    if location_filter is not None:
        filters.append(location_filter)

    return filters


async def _count(session: AsyncSession, filters: list[ColumnElement[bool]]) -> int:
    """How many `Tender` rows satisfy every filter in `filters` (an empty list counts them all)."""
    return await session.scalar(select(func.count()).select_from(Tender).where(*filters)) or 0


async def list_matches(
    session: AsyncSession, provider: Provider, *, limit: int, offset: int
) -> tuple[list[Tender], int]:
    """The tenders that survive every hard filter for `provider`, paginated newest-first.

    Args:
        session: The active database session.
        provider: The profile whose CPV/budget/location filters are applied.
        limit: Maximum number of rows to return.
        offset: Number of matching rows to skip, for pagination.

    Returns:
        The page of matching tenders, and the total match count across all pages.
    """
    filters = _build_filters(provider)
    total = await _count(session, filters)

    items_stmt = (
        select(Tender)
        .where(*filters)
        .order_by(Tender.published_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = (await session.scalars(items_stmt)).all()

    return list(items), total


async def funnel_stage_counts(session: AsyncSession, provider: Provider) -> FunnelStageCounts:
    """Cumulative survivor counts through each hard-filter stage, for `provider`.

    Applies the same filters as `list_matches`, one at a time, in the same
    fixed order -- so `after_location` always equals `list_matches`'s
    `total` for the same provider.
    """
    total = await _count(session, [])

    running: list[ColumnElement[bool]] = [_status_filter()]
    after_status = await _count(session, running)

    running.append(_cpv_filter(provider))
    after_cpv = await _count(session, running)

    budget_filter = _budget_filter(provider)
    if budget_filter is not None:
        running.append(budget_filter)
    after_budget = await _count(session, running)

    location_filter = _location_filter(provider)
    if location_filter is not None:
        running.append(location_filter)
    after_location = await _count(session, running)

    return FunnelStageCounts(
        total=total,
        after_status=after_status,
        after_cpv=after_cpv,
        after_budget=after_budget,
        after_location=after_location,
    )
