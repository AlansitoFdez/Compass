"""Etapa 1 of the matching funnel: deterministic hard filters in SQL, no ranking involved.

Every filter here is AND'd and derived straight from the provider's own
profile -- CPV, budget range, and geographic scope -- plus a fixed "still
biddable" filter (open status *and* a deadline that hasn't passed; see
`_status_filter`). Nothing here ranks or scores
a tender; a tender either survives every filter or it doesn't. Semantic
ranking is Etapa 2 (`matching.lexical`, `matching.vector` and `matching.fusion`,
built in 2.3-2.6), which reuses `build_filters` to stay scoped to these same
survivors.
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
        after_status: Surviving the "still biddable" filter -- open status *and* a
            submission deadline that hasn't passed (see `_status_filter`).
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
    """Only tenders a provider could actually still bid on ever reach them.

    Two conditions, not one, and the second is what makes this stage mean what it says.
    Until 5.3 this checked only PLACSP's own `status` code -- but PLACSP does not reliably
    move a tender out of `PUB` when its deadline passes, so the code is stale far more
    often than not: of the 508 tenders in the real corpus whose status said "open",
    **429 (84%) had a submission deadline already in the past**. The funnel was calling
    them "en plazo" and the dashboard was showing them as such, right next to a deadline
    that said "cerrado". Re-measured in 5.8 as the corpus grew, the ratio only got worse:
    1.636 of 1.740.

    A tender with no published deadline at all is excluded too, for the same reason
    `_budget_filter` excludes a tender with no budget: the filter exists to answer "can
    this still be bid on", and a tender that can't answer doesn't get in for free.
    """
    return and_(
        Tender.status == TenderStatus.OPEN_FOR_SUBMISSION,
        Tender.submission_deadline >= func.now(),
    )


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


def build_filters(provider: Provider) -> list[ColumnElement[bool]]:
    """Every hard filter that applies to `provider`, in the fixed order the funnel checks them.

    Not private: `matching.lexical` (Etapa 2) reuses this to scope its own
    ranking to the same survivors this stage already narrowed down to --
    the funnel is sequential, so later stages never look at a wider set
    than this one already passed.
    """
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
    filters = build_filters(provider)
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
