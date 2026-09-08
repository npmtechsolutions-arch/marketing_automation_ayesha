"""Revenue metrics, and the superadmin gate on every new admin route.

The MRR arithmetic is the load-bearing part. Getting it wrong does not raise --
it produces a plausible number that someone reports to a board, so each rule
about what counts is pinned by a test that fails if the rule is relaxed:

* only ACTIVE subscriptions are revenue
* soft-deleted organizations are not
* prices come from the plans table, so editing a plan moves MRR
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.account import SubscriptionStatus, SubscriptionTier
from app.models.plan import Plan
from app.models.subscription_event import SubscriptionEvent, SubscriptionEventSource
from app.services import revenue

pytestmark = pytest.mark.asyncio

# The seeded plan prices, which the assertions below are written against.
STARTER = Decimal("49")
GROWTH = Decimal("149")
PRO = Decimal("399")


@pytest.fixture
async def subscribed(db_session, user_factory, organization_factory):
    """Create an organization on a given tier and status."""

    async def _make(
        tier: SubscriptionTier = SubscriptionTier.PRO,
        status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
        *,
        deleted: bool = False,
    ):
        owner = await user_factory()
        organization = await organization_factory(
            owner, subscription_tier=tier, subscription_status=status
        )
        if deleted:
            organization.deleted_at = datetime.now(timezone.utc)
        await db_session.flush()
        return organization

    return _make


# ---------------------------------------------------------------------------
# What counts as revenue
# ---------------------------------------------------------------------------

async def test_mrr_sums_active_subscriptions_at_plan_prices(db_session, subscribed):
    await subscribed(SubscriptionTier.PRO)
    await subscribed(SubscriptionTier.GROWTH)
    await subscribed(SubscriptionTier.STARTER)

    summary = await revenue.summary(db_session)

    assert summary["mrr"] == float(PRO + GROWTH + STARTER)
    assert summary["arr"] == float((PRO + GROWTH + STARTER) * 12)
    assert summary["paying_organizations"] == 3


@pytest.mark.parametrize(
    "status",
    [
        SubscriptionStatus.TRIALING,
        SubscriptionStatus.PAST_DUE,
        SubscriptionStatus.CANCELLED,
    ],
)
async def test_only_active_subscriptions_are_revenue(db_session, subscribed, status):
    """A trial has not paid, a past-due invoice has not been collected, and a
    cancelled subscription is gone. Counting any of them books money the
    business does not have."""
    await subscribed(SubscriptionTier.PRO, status)

    summary = await revenue.summary(db_session)

    assert summary["mrr"] == 0.0
    assert summary["paying_organizations"] == 0


async def test_past_due_is_reported_as_at_risk_rather_than_ignored(
    db_session, subscribed
):
    """Excluded from MRR, but an operator still needs to see it -- that is the
    revenue about to disappear."""
    await subscribed(SubscriptionTier.PRO, SubscriptionStatus.PAST_DUE)

    summary = await revenue.summary(db_session)

    assert summary["mrr"] == 0.0
    assert summary["at_risk_mrr"] == float(PRO)


async def test_soft_deleted_organizations_are_excluded(db_session, subscribed):
    await subscribed(SubscriptionTier.PRO)
    await subscribed(SubscriptionTier.PRO, deleted=True)

    summary = await revenue.summary(db_session)

    assert summary["mrr"] == float(PRO), "a deleted organization is still being billed"
    assert summary["paying_organizations"] == 1


async def test_free_organizations_contribute_nothing_but_are_counted(
    db_session, subscribed
):
    await subscribed(SubscriptionTier.FREE)

    summary = await revenue.summary(db_session)

    assert summary["mrr"] == 0.0
    free = next(row for row in summary["by_plan"] if row["plan"] == "free")
    assert free["organizations"] == 1


async def test_enterprise_is_surfaced_rather_than_silently_omitted(
    db_session, subscribed
):
    """Enterprise is priced by negotiation, so its plan row says zero. MRR is
    therefore incomplete, and the report has to say so -- a total that quietly
    drops the largest customers is worse than one that flags the gap."""
    await subscribed(SubscriptionTier.ENTERPRISE)

    summary = await revenue.summary(db_session)

    assert summary["mrr"] == 0.0
    assert summary["unpriced_active_organizations"] == 1
    assert "enterprise" in summary["unpriced_tiers"]


async def test_mrr_follows_the_plans_table(db_session, subscribed):
    """The point of moving pricing out of a Python dict in 1.3: an operator
    editing a plan changes what the revenue report says, with no deploy."""
    await subscribed(SubscriptionTier.PRO)
    assert (await revenue.summary(db_session))["mrr"] == float(PRO)

    plan = (
        await db_session.execute(select(Plan).where(Plan.key == "pro"))
    ).scalar_one()
    plan.price_monthly = Decimal("500")
    await db_session.flush()

    assert (await revenue.summary(db_session))["mrr"] == 500.0


async def test_by_plan_breaks_the_total_down(db_session, subscribed):
    await subscribed(SubscriptionTier.PRO)
    await subscribed(SubscriptionTier.PRO)
    await subscribed(SubscriptionTier.STARTER)

    summary = await revenue.summary(db_session)

    rows = {row["plan"]: row for row in summary["by_plan"]}
    assert rows["pro"]["active"] == 2
    assert rows["pro"]["mrr"] == float(PRO * 2)
    assert rows["starter"]["mrr"] == float(STARTER)
    assert sum(row["mrr"] for row in summary["by_plan"]) == summary["mrr"]


# ---------------------------------------------------------------------------
# Movement, from the event log
# ---------------------------------------------------------------------------

async def _event(db_session, organization, *, to_status, from_status, mrr, ago_days=1):
    event = SubscriptionEvent(
        id=uuid.uuid4(),
        organization_id=organization.id,
        from_tier="pro",
        to_tier="pro",
        from_status=from_status,
        to_status=to_status,
        mrr_amount=Decimal(str(mrr)),
        source=SubscriptionEventSource.WEBHOOK,
        created_at=datetime.now(timezone.utc) - timedelta(days=ago_days),
    )
    db_session.add(event)
    await db_session.flush()
    return event


async def test_churn_counts_cancellations_in_the_window(db_session, subscribed):
    organization = await subscribed(SubscriptionTier.PRO, SubscriptionStatus.CANCELLED)
    await _event(db_session, organization, from_status="trialing",
                 to_status="active", mrr=PRO, ago_days=40)
    await _event(db_session, organization, from_status="active",
                 to_status="cancelled", mrr=0, ago_days=5)

    result = await revenue.churn(db_session, days=30)

    assert result["churned_organizations"] == 1
    # The cancellation event itself is worth zero; what was lost is what they
    # were paying beforehand.
    assert result["lost_mrr"] == float(PRO)


async def test_churn_ignores_cancellations_outside_the_window(db_session, subscribed):
    organization = await subscribed(SubscriptionTier.PRO, SubscriptionStatus.CANCELLED)
    await _event(db_session, organization, from_status="active",
                 to_status="cancelled", mrr=0, ago_days=100)

    assert (await revenue.churn(db_session, days=30))["churned_organizations"] == 0


async def test_a_repeated_cancellation_event_is_one_churn(db_session, subscribed):
    """Stripe redelivers webhooks. A repeat must not read as a second customer
    leaving."""
    organization = await subscribed(SubscriptionTier.PRO, SubscriptionStatus.CANCELLED)
    await _event(db_session, organization, from_status="active",
                 to_status="cancelled", mrr=0, ago_days=5)
    await _event(db_session, organization, from_status="cancelled",
                 to_status="cancelled", mrr=0, ago_days=4)

    assert (await revenue.churn(db_session, days=30))["churned_organizations"] == 1


async def test_churn_rate_is_null_with_nobody_to_churn(db_session):
    """0% churn out of no customers is not a good month; it is no data."""
    assert (await revenue.churn(db_session, days=30))["churn_rate"] is None


async def test_trial_conversions_count_trialing_to_active(db_session, subscribed):
    converted = await subscribed(SubscriptionTier.PRO)
    await _event(db_session, converted, from_status="trialing",
                 to_status="active", mrr=PRO, ago_days=3)

    lapsed = await subscribed(SubscriptionTier.FREE, SubscriptionStatus.CANCELLED)
    await _event(db_session, lapsed, from_status="trialing",
                 to_status="cancelled", mrr=0, ago_days=3)

    result = await revenue.trial_conversions(db_session, days=30)

    assert result["converted"] == 1
    assert result["trials_ended"] == 2
    assert result["conversion_rate"] == 50.0


async def test_conversion_rate_is_null_when_no_trial_ended(db_session):
    result = await revenue.trial_conversions(db_session, days=30)
    assert result["converted"] == 0
    assert result["conversion_rate"] is None


async def test_the_trend_carries_each_value_forward(db_session, subscribed):
    """A day with no event for an organization keeps its last known value --
    revenue does not drop to zero because nothing happened that day."""
    organization = await subscribed(SubscriptionTier.PRO)
    await _event(db_session, organization, from_status="trialing",
                 to_status="active", mrr=PRO, ago_days=10)

    result = await revenue.trend(db_session, days=30)
    by_date = {row["date"]: row["mrr"] for row in result["series"]}

    today = datetime.now(timezone.utc).date()
    assert by_date[(today - timedelta(days=5)).isoformat()] == float(PRO)
    assert by_date[today.isoformat()] == float(PRO)
    # Before the first event there is genuinely nothing recorded.
    assert by_date[(today - timedelta(days=20)).isoformat()] == 0.0


async def test_the_trend_reports_where_its_history_starts(db_session, subscribed):
    """Without this the chart's leading zeros look like a revenue cliff rather
    than the absence of a log."""
    empty = await revenue.trend(db_session, days=30)
    assert empty["has_history"] is False
    assert empty["tracking_since"] is None

    organization = await subscribed(SubscriptionTier.PRO)
    await _event(db_session, organization, from_status="trialing",
                 to_status="active", mrr=PRO, ago_days=10)

    filled = await revenue.trend(db_session, days=30)
    assert filled["has_history"] is True
    assert filled["tracking_since"] is not None


# ---------------------------------------------------------------------------
# Writing the log
# ---------------------------------------------------------------------------

async def test_a_transition_is_recorded(db_session, subscribed):
    organization = await subscribed(SubscriptionTier.FREE, SubscriptionStatus.TRIALING)

    organization.subscription_tier = SubscriptionTier.PRO
    organization.subscription_status = SubscriptionStatus.ACTIVE
    await revenue.record_transition(
        db_session, organization, from_tier="free", from_status="trialing",
        source=SubscriptionEventSource.CHECKOUT,
    )
    await db_session.flush()

    event = (
        await db_session.execute(
            select(SubscriptionEvent).where(
                SubscriptionEvent.organization_id == organization.id
            )
        )
    ).scalar_one()
    assert event.from_status == "trialing"
    assert event.to_status == "active"
    assert float(event.mrr_amount) == float(PRO)


async def test_a_no_op_transition_writes_nothing(db_session, subscribed):
    """A redelivered webhook re-applying a change we already have must not
    appear in the log as movement."""
    organization = await subscribed(SubscriptionTier.PRO, SubscriptionStatus.ACTIVE)

    written = await revenue.record_transition(
        db_session, organization, from_tier="pro", from_status="active"
    )

    assert written is None


async def test_a_recorded_amount_does_not_move_when_a_price_changes(
    db_session, subscribed
):
    """History is what the business earned, not what it would charge today.
    Deriving the trend from today's Plan row would rewrite last quarter."""
    organization = await subscribed(SubscriptionTier.FREE, SubscriptionStatus.TRIALING)
    organization.subscription_tier = SubscriptionTier.PRO
    organization.subscription_status = SubscriptionStatus.ACTIVE
    await revenue.record_transition(
        db_session, organization, from_tier="free", from_status="trialing"
    )
    await db_session.flush()

    plan = (await db_session.execute(select(Plan).where(Plan.key == "pro"))).scalar_one()
    plan.price_monthly = Decimal("999")
    await db_session.flush()

    event = (
        await db_session.execute(
            select(SubscriptionEvent).where(
                SubscriptionEvent.organization_id == organization.id
            )
        )
    ).scalar_one()
    assert float(event.mrr_amount) == float(PRO)
