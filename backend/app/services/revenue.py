"""Revenue metrics for the admin panel.

Everything here is computed from two sources and never from a hard-coded price
table: ``organizations`` for who is subscribed to what right now, and ``plans``
for what that costs. The old ``TIER_PRICING`` dict is gone for the same reason
``TIER_LIMITS`` went -- a price an operator can edit in the plans UI must be
the price the revenue report uses, or the two disagree and nobody knows which
one billing follows.

Three deliberate decisions about what counts, because each is a place where a
dashboard can flatter itself:

* **Only ACTIVE subscriptions are revenue.** TRIALING has not paid yet; that is
  what the conversion number is for. PAST_DUE has an unpaid invoice, and
  counting it as MRR is booking money the business has not received -- it is
  reported separately as at-risk.
* **Soft-deleted organizations are excluded.** A cancelled customer whose row
  is still present is not paying.
* **Enterprise contributes what its plan row says**, which is currently zero
  because Enterprise is priced by negotiation and not sold through Stripe. That
  would silently understate MRR, so the count of Enterprise organizations is
  returned alongside it and the UI says so rather than showing a total that
  quietly omits the largest customers.
"""

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import SubscriptionStatus, SubscriptionTier
from app.models.organization import Organization
from app.models.plan import Plan
from app.models.subscription_event import SubscriptionEvent, SubscriptionEventSource

logger = logging.getLogger(__name__)

MONTHS_PER_YEAR = 12

# Enterprise is priced by negotiation, so its plan row carries no usable
# amount. Named rather than inlined so the report and the caveat cannot drift.
UNPRICED_TIERS = frozenset({SubscriptionTier.ENTERPRISE.value})


def _money(value) -> float:
    """Money as a float, rounded to cents.

    Sums come back as Decimal from Postgres and float from SQLite. Rounding
    here means the two agree, and that a total never renders as 148.99999.
    """
    return float(round(Decimal(str(value or 0)), 2))


async def _price_by_tier(db: AsyncSession) -> dict[str, Decimal]:
    """Every plan's monthly price, keyed by the tier value it matches."""
    rows = (await db.execute(select(Plan.key, Plan.price_monthly))).all()
    return {row.key: Decimal(str(row.price_monthly or 0)) for row in rows}


async def monthly_value(db: AsyncSession, organization: Organization) -> Decimal:
    """What one organization contributes to MRR right now.

    Zero unless the subscription is ACTIVE -- a trialing or past-due
    organization is on a tier but is not paying for it.
    """
    if organization.subscription_status is not SubscriptionStatus.ACTIVE:
        return Decimal("0")
    prices = await _price_by_tier(db)
    return prices.get(organization.subscription_tier.value, Decimal("0"))


# ---------------------------------------------------------------------------
# Current state
# ---------------------------------------------------------------------------

async def summary(db: AsyncSession) -> dict:
    """MRR, ARR, and the counts behind them."""
    # Counts come from the database; prices are applied in Python.
    #
    # Not a SQL join on the tier. A SQLAlchemy Enum column stores the member
    # *name* -- Postgres holds 'FREE' -- while plans.key holds the member
    # *value*, 'free'. ``Plan.key == Organization.subscription_tier`` therefore
    # matches nothing, and an outer join of nothing is a total of zero: MRR
    # reads as $0 with a full customer book and nothing raises. Grouping is at
    # most one row per tier per status, so there is nothing to gain by pushing
    # the multiplication down anyway.
    prices = await _price_by_tier(db)

    rows = (
        await db.execute(
            select(
                Organization.subscription_tier,
                Organization.subscription_status,
                func.count().label("organizations"),
            )
            .where(Organization.deleted_at.is_(None))
            .group_by(Organization.subscription_tier, Organization.subscription_status)
        )
    ).all()

    by_plan: dict[str, dict] = {}
    by_status: dict[str, int] = {s.value: 0 for s in SubscriptionStatus}
    mrr = Decimal("0")
    at_risk = Decimal("0")
    unpriced_active = 0

    for row in rows:
        tier = (
            row.subscription_tier.value
            if hasattr(row.subscription_tier, "value")
            else str(row.subscription_tier)
        )
        state = (
            row.subscription_status.value
            if hasattr(row.subscription_status, "value")
            else str(row.subscription_status)
        )
        count = int(row.organizations)
        value = prices.get(tier, Decimal("0")) * count

        entry = by_plan.setdefault(
            tier, {"plan": tier, "organizations": 0, "active": 0, "mrr": Decimal("0")}
        )
        entry["organizations"] += count
        by_status[state] = by_status.get(state, 0) + count

        if state == SubscriptionStatus.ACTIVE.value:
            entry["active"] += count
            entry["mrr"] += value
            mrr += value
            if tier in UNPRICED_TIERS:
                unpriced_active += count
        elif state == SubscriptionStatus.PAST_DUE.value:
            at_risk += value

    plans = sorted(
        (
            {**entry, "mrr": _money(entry["mrr"])}
            for entry in by_plan.values()
        ),
        key=lambda item: item["mrr"],
        reverse=True,
    )

    return {
        "mrr": _money(mrr),
        # Straight multiplication, not a forecast: this is what the current
        # book bills over twelve months if nothing changes, which is the only
        # thing the data supports.
        "arr": _money(mrr * MONTHS_PER_YEAR),
        "at_risk_mrr": _money(at_risk),
        "paying_organizations": by_status.get(SubscriptionStatus.ACTIVE.value, 0),
        "by_status": by_status,
        "by_plan": plans,
        # Active organizations on a plan with no price. MRR excludes them, and
        # saying so is the difference between a total that is incomplete and
        # one that is wrong.
        "unpriced_active_organizations": unpriced_active,
        "unpriced_tiers": sorted(UNPRICED_TIERS),
    }


# ---------------------------------------------------------------------------
# Movement over time -- all of it from the event log
# ---------------------------------------------------------------------------

async def tracking_since(db: AsyncSession) -> Optional[datetime]:
    """When the event log starts.

    Before this instant there is no transition history, so churn and trend are
    reporting on a window they cannot see all of. The endpoints return it so
    the UI can say "tracking since X" instead of drawing a line that implies
    zero revenue before the feature shipped.
    """
    return (
        await db.execute(select(func.min(SubscriptionEvent.created_at)))
    ).scalar_one_or_none()


async def churn(db: AsyncSession, *, days: int = 30) -> dict:
    """Organizations that cancelled in the window.

    Counted from transitions *into* CANCELLED, not from the current status: an
    organization that cancelled and resubscribed inside the window churned, and
    a status column cannot say so.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)

    cancellations = (
        await db.execute(
            select(
                SubscriptionEvent.organization_id,
                func.min(SubscriptionEvent.created_at).label("cancelled_at"),
            )
            .where(
                SubscriptionEvent.created_at >= since,
                SubscriptionEvent.to_status == SubscriptionStatus.CANCELLED.value,
                # A repeated webhook re-asserting CANCELLED is not a second
                # customer leaving.
                SubscriptionEvent.from_status != SubscriptionStatus.CANCELLED.value,
            )
            .group_by(SubscriptionEvent.organization_id)
        )
    ).all()

    churned = len(cancellations)

    # What each was worth *before* cancelling. mrr_amount on a cancellation
    # event is zero by definition, so the lost revenue is carried by the last
    # paying event that preceded it.
    lost = Decimal("0")
    for row in cancellations:
        previous = (
            await db.execute(
                select(SubscriptionEvent.mrr_amount)
                .where(
                    SubscriptionEvent.organization_id == row.organization_id,
                    SubscriptionEvent.created_at < row.cancelled_at,
                    SubscriptionEvent.to_status == SubscriptionStatus.ACTIVE.value,
                )
                .order_by(SubscriptionEvent.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        lost += Decimal(str(previous or 0))

    paying = (
        await db.execute(
            select(func.count())
            .select_from(Organization)
            .where(
                Organization.deleted_at.is_(None),
                Organization.subscription_status == SubscriptionStatus.ACTIVE,
            )
        )
    ).scalar_one()

    # Denominator is who is paying now plus who left, i.e. who could have left.
    # Null rather than zero when nobody could have churned: 0% churn out of no
    # customers is not a good month.
    exposed = paying + churned
    return {
        "days": days,
        "churned_organizations": churned,
        "lost_mrr": _money(lost),
        "churn_rate": (
            round(churned / exposed * 100, 2) if exposed else None
        ),
    }


async def trial_conversions(db: AsyncSession, *, days: int = 30) -> dict:
    """Trials that became paying subscriptions in the window."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    converted = (
        await db.execute(
            select(func.count(func.distinct(SubscriptionEvent.organization_id)))
            .where(
                SubscriptionEvent.created_at >= since,
                SubscriptionEvent.from_status == SubscriptionStatus.TRIALING.value,
                SubscriptionEvent.to_status == SubscriptionStatus.ACTIVE.value,
            )
        )
    ).scalar_one()

    # Trials that ended either way in the window, so the rate has a denominator
    # that means something.
    ended = (
        await db.execute(
            select(func.count(func.distinct(SubscriptionEvent.organization_id)))
            .where(
                SubscriptionEvent.created_at >= since,
                SubscriptionEvent.from_status == SubscriptionStatus.TRIALING.value,
                SubscriptionEvent.to_status != SubscriptionStatus.TRIALING.value,
            )
        )
    ).scalar_one()

    trialing_now = (
        await db.execute(
            select(func.count())
            .select_from(Organization)
            .where(
                Organization.deleted_at.is_(None),
                Organization.subscription_status == SubscriptionStatus.TRIALING,
            )
        )
    ).scalar_one()

    return {
        "days": days,
        "converted": int(converted),
        "trials_ended": int(ended),
        "trialing_now": int(trialing_now),
        # Null, not zero, when no trial ended in the window: a 0% conversion
        # rate is a claim about trials that did not happen.
        "conversion_rate": (
            round(int(converted) / int(ended) * 100, 2) if ended else None
        ),
    }


async def trend(db: AsyncSession, *, days: int = 90) -> dict:
    """Daily MRR over the window, reconstructed from the event log.

    Each organization contributes its most recent ``mrr_amount`` as at the end
    of each day. An organization with no event before a given day contributes
    nothing to that day -- which is why the series is honest only from
    ``tracking_since`` onward, and why that value is returned with it.
    """
    start = (datetime.now(timezone.utc) - timedelta(days=days)).date()
    since = await tracking_since(db)

    events = (
        await db.execute(
            select(
                SubscriptionEvent.organization_id,
                SubscriptionEvent.created_at,
                SubscriptionEvent.mrr_amount,
            ).order_by(SubscriptionEvent.created_at)
        )
    ).all()

    # Walk the log once, carrying each organization's latest value forward.
    # The alternative -- a query per day -- is 90 round trips for a chart.
    per_org: dict[str, Decimal] = {}
    by_day: dict[date, Decimal] = {}
    cursor = 0
    today = datetime.now(timezone.utc).date()
    day = start
    while day <= today:
        while cursor < len(events) and events[cursor].created_at.date() <= day:
            event = events[cursor]
            per_org[str(event.organization_id)] = Decimal(str(event.mrr_amount or 0))
            cursor += 1
        by_day[day] = sum(per_org.values(), Decimal("0"))
        day += timedelta(days=1)

    series = [
        {"date": day.isoformat(), "mrr": _money(value)}
        for day, value in sorted(by_day.items())
    ]
    return {
        "days": days,
        "series": series,
        # The client draws from here, and greys or annotates anything earlier.
        "tracking_since": since.isoformat() if since else None,
        "has_history": since is not None,
    }


# ---------------------------------------------------------------------------
# Writing the log
# ---------------------------------------------------------------------------

async def record_transition(
    db: AsyncSession,
    organization: Organization,
    *,
    from_tier: Optional[str],
    from_status: Optional[str],
    source: SubscriptionEventSource = SubscriptionEventSource.SYSTEM,
    note: Optional[str] = None,
) -> Optional[SubscriptionEvent]:
    """Record a tier or status change, if anything actually changed.

    Called after the organization has been mutated, with the values it held
    beforehand. A no-op change writes nothing: a Stripe webhook that repeats an
    event we have already applied should not show up as churn and re-signup.

    Never raises. A revenue report is worth having, and it is not worth failing
    a customer's checkout for.
    """
    to_tier = organization.subscription_tier.value
    to_status = organization.subscription_status.value
    if from_tier == to_tier and from_status == to_status:
        return None

    try:
        amount = await monthly_value(db, organization)
        event = SubscriptionEvent(
            id=uuid.uuid4(),
            organization_id=organization.id,
            from_tier=from_tier,
            to_tier=to_tier,
            from_status=from_status,
            to_status=to_status,
            mrr_amount=amount,
            source=source,
            note=note,
        )
        db.add(event)
        return event
    except Exception:  # noqa: BLE001
        logger.exception(
            "Could not record a subscription transition for organization %s",
            organization.id,
        )
        return None
