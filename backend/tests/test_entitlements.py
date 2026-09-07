"""Plan entitlements.

Limits used to be a Python dict; they are now Plan/PlanFeature rows. These
tests cover what that has to preserve (a cap still binds, and it binds across
every workspace in the organization) and what it adds: atomicity, unlimited as
NULL rather than a sentinel, boolean gating, and cache invalidation on a plan
change.
"""

import uuid

import pytest

from app.services import entitlement_service as ent

pytestmark = pytest.mark.asyncio

PASSWORD = "hunter2-correct-horse"


async def _create_post(client, auth_header, user, account, content="A post"):
    return await client.post(
        f"/api/v1/accounts/{account.id}/posts/",
        headers=auth_header(user),
        json={"content": content, "target_accounts": []},
    )


@pytest.fixture
async def org_with_workspace(user_factory, account_factory, organization_factory):
    user = await user_factory(password=PASSWORD)
    organization = await organization_factory(user)
    account = await account_factory(user, organization=organization)
    return {"user": user, "organization": organization, "account": account}


# ---------------------------------------------------------------------------
# Limits resolve from plan rows
# ---------------------------------------------------------------------------

async def test_limits_come_from_the_plan(db_session, org_with_workspace):
    """The seeded Free plan reproduces what TIER_LIMITS used to hold."""
    organization = org_with_workspace["organization"]
    assert await ent.get_limit(db_session, organization, ent.POSTS_PER_MONTH) == 10
    assert await ent.get_limit(db_session, organization, ent.WORKSPACES) == 1
    assert await ent.get_limit(db_session, organization, ent.TEAM_MEMBERS) == 1
    assert await ent.get_limit(db_session, organization, ent.SOCIAL_ACCOUNTS) == 2


async def test_null_limit_means_unlimited(db_session, org_with_workspace, set_limit):
    """NULL is unlimited. The old code used -1 and 99999 as stand-ins, which
    meant 'unlimited' and 'a very large cap' were indistinguishable."""
    organization = org_with_workspace["organization"]
    await set_limit(organization, ent.POSTS_PER_MONTH, None)

    assert await ent.get_limit(db_session, organization, ent.POSTS_PER_MONTH) is None
    for i in range(5):
        assert await ent.check_and_increment(
            db_session, organization, ent.POSTS_PER_MONTH
        ) == i + 1


async def test_missing_plan_feature_grants_nothing(
    db_session, org_with_workspace, set_limit
):
    """An absent row is 0, not unlimited. Failing open on a missing entitlement
    would be the worst possible default."""
    from sqlalchemy import delete, select

    from app.models.plan import Plan, PlanFeature

    organization = org_with_workspace["organization"]
    plan = (
        await db_session.execute(
            select(Plan).where(Plan.key == organization.subscription_tier.value)
        )
    ).scalar_one()
    await db_session.execute(
        delete(PlanFeature).where(
            PlanFeature.plan_id == plan.id,
            PlanFeature.feature_key == ent.REPORTS_PER_MONTH,
        )
    )
    await db_session.flush()
    ent.invalidate_all()

    assert await ent.get_limit(db_session, organization, ent.REPORTS_PER_MONTH) == 0
    with pytest.raises(ent.EntitlementExceeded):
        await ent.check_and_increment(db_session, organization, ent.REPORTS_PER_MONTH)


# ---------------------------------------------------------------------------
# Metered enforcement
# ---------------------------------------------------------------------------

async def test_metered_increment_stops_at_the_limit(
    db_session, org_with_workspace, set_limit
):
    organization = org_with_workspace["organization"]
    await set_limit(organization, ent.AI_REQUESTS_PER_MONTH, 3)

    for expected in (1, 2, 3):
        assert await ent.check_and_increment(
            db_session, organization, ent.AI_REQUESTS_PER_MONTH
        ) == expected

    with pytest.raises(ent.EntitlementExceeded) as exc:
        await ent.check_and_increment(db_session, organization, ent.AI_REQUESTS_PER_MONTH)
    assert exc.value.status_code == 402
    assert exc.value.feature_key == ent.AI_REQUESTS_PER_MONTH
    assert "upgrade" in exc.value.detail.lower()


async def test_a_single_request_larger_than_the_limit_is_refused(
    db_session, org_with_workspace, set_limit
):
    """The guard lives in the UPDATE branch, so a first-ever insert has to be
    checked separately or it would create a row already over the limit."""
    organization = org_with_workspace["organization"]
    await set_limit(organization, ent.POSTS_PER_MONTH, 5)

    with pytest.raises(ent.EntitlementExceeded):
        await ent.check_and_increment(
            db_session, organization, ent.POSTS_PER_MONTH, amount=6
        )
    assert await ent.current_usage(db_session, organization, ent.POSTS_PER_MONTH) == 0


async def test_refused_increment_does_not_consume(
    db_session, org_with_workspace, set_limit
):
    """A rejected call must leave the counter untouched, or repeated failures
    would eat the allowance."""
    organization = org_with_workspace["organization"]
    await set_limit(organization, ent.POSTS_PER_MONTH, 1)

    await ent.check_and_increment(db_session, organization, ent.POSTS_PER_MONTH)
    for _ in range(3):
        with pytest.raises(ent.EntitlementExceeded):
            await ent.check_and_increment(db_session, organization, ent.POSTS_PER_MONTH)

    assert await ent.current_usage(db_session, organization, ent.POSTS_PER_MONTH) == 1


async def test_usage_is_per_period(db_session, org_with_workspace, set_limit):
    """Last month's usage does not count against this month's allowance."""
    from datetime import timedelta

    from app.models.plan import UsageRecord

    organization = org_with_workspace["organization"]
    await set_limit(organization, ent.POSTS_PER_MONTH, 2)

    previous = ent.period_start() - timedelta(days=1)
    db_session.add(
        UsageRecord(
            id=uuid.uuid4(), organization_id=organization.id,
            feature_key=ent.POSTS_PER_MONTH,
            period_start=previous.replace(day=1), count=99,
        )
    )
    await db_session.flush()

    assert await ent.current_usage(db_session, organization, ent.POSTS_PER_MONTH) == 0
    assert await ent.check_and_increment(
        db_session, organization, ent.POSTS_PER_MONTH
    ) == 1


# ---------------------------------------------------------------------------
# Boolean features
# ---------------------------------------------------------------------------

async def test_boolean_feature_gating(db_session, org_with_workspace, set_limit):
    organization = org_with_workspace["organization"]

    # Free does not include white label.
    assert await ent.is_enabled(db_session, organization, ent.WHITE_LABEL) is False
    with pytest.raises(ent.EntitlementExceeded) as exc:
        await ent.require_feature(db_session, organization, ent.WHITE_LABEL)
    assert exc.value.status_code == 402
    assert "white label" in exc.value.detail.lower()

    await set_limit(organization, ent.WHITE_LABEL, 1)
    assert await ent.is_enabled(db_session, organization, ent.WHITE_LABEL) is True
    await ent.require_feature(db_session, organization, ent.WHITE_LABEL)  # no raise


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

async def test_plan_change_invalidates_the_cached_limit(
    db_session, org_with_workspace, set_limit
):
    """A limit is cached for 60s. Without invalidation an upgrade would appear
    not to work for up to a minute -- the moment a customer is least patient."""
    from app.models.account import SubscriptionTier
    from app.services.entitlements import apply_tier

    organization = org_with_workspace["organization"]
    assert await ent.get_limit(db_session, organization, ent.POSTS_PER_MONTH) == 10

    await apply_tier(db_session, organization, SubscriptionTier.GROWTH)
    await db_session.flush()

    assert await ent.get_limit(db_session, organization, ent.POSTS_PER_MONTH) == 200


async def test_editing_a_limit_takes_effect_after_invalidation(
    db_session, org_with_workspace, set_limit
):
    organization = org_with_workspace["organization"]
    assert await ent.get_limit(db_session, organization, ent.POSTS_PER_MONTH) == 10

    await set_limit(organization, ent.POSTS_PER_MONTH, 42)
    assert await ent.get_limit(db_session, organization, ent.POSTS_PER_MONTH) == 42


# ---------------------------------------------------------------------------
# Through the API
# ---------------------------------------------------------------------------

async def test_posts_allowed_up_to_the_cap(
    client, auth_header, org_with_workspace, set_limit
):
    await set_limit(org_with_workspace["organization"], ent.POSTS_PER_MONTH, 3)
    for i in range(3):
        response = await _create_post(
            client, auth_header, org_with_workspace["user"],
            org_with_workspace["account"], f"Post {i}",
        )
        assert response.status_code == 201, response.text[:200]


async def test_post_over_the_cap_is_refused(
    client, auth_header, org_with_workspace, set_limit
):
    await set_limit(org_with_workspace["organization"], ent.POSTS_PER_MONTH, 2)
    for i in range(2):
        await _create_post(
            client, auth_header, org_with_workspace["user"],
            org_with_workspace["account"], f"Post {i}",
        )

    response = await _create_post(
        client, auth_header, org_with_workspace["user"],
        org_with_workspace["account"], "One too many",
    )
    assert response.status_code == 402
    detail = response.json()["detail"].lower()
    assert "limit" in detail and "upgrade" in detail


async def test_ai_endpoints_are_metered(
    client, auth_header, org_with_workspace, set_limit
):
    """The cost hole this closes: AI generation was previously unmetered, so an
    organization on any plan could run up an unbounded provider bill."""
    await set_limit(org_with_workspace["organization"], ent.AI_REQUESTS_PER_MONTH, 1)
    url = f"/api/v1/accounts/{org_with_workspace['account'].id}/ai/suggest-topics"
    body = {"business_id": str(uuid.uuid4()), "count": 3}
    headers = auth_header(org_with_workspace["user"])

    # The first spends the allowance (whatever the generation itself returns).
    first = await client.post(url, headers=headers, json=body)
    assert first.status_code != 402

    second = await client.post(url, headers=headers, json=body)
    assert second.status_code == 402, (
        f"a second AI request was not metered (got {second.status_code})"
    )


async def test_member_limit_blocks_an_invitation_at_the_cap(
    client, auth_header, org_with_workspace, set_limit
):
    await set_limit(org_with_workspace["organization"], ent.TEAM_MEMBERS, 1)
    response = await client.post(
        f"/api/v1/accounts/{org_with_workspace['account'].id}/team/invite",
        headers=auth_header(org_with_workspace["user"]),
        json={"email": f"new-{uuid.uuid4().hex[:8]}@example.com", "role": "viewer"},
    )
    assert response.status_code == 402


async def test_usage_summary_reports_used_against_limit(
    db_session, org_with_workspace, set_limit
):
    organization = org_with_workspace["organization"]
    await set_limit(organization, ent.POSTS_PER_MONTH, 10)
    await ent.check_and_increment(db_session, organization, ent.POSTS_PER_MONTH, 3)

    summary = {row["key"]: row for row in await ent.usage_summary(db_session, organization)}
    assert summary[ent.POSTS_PER_MONTH]["used"] == 3
    assert summary[ent.POSTS_PER_MONTH]["limit"] == 10
    assert summary[ent.POSTS_PER_MONTH]["metered"] is True
    # Stateful: one workspace exists.
    assert summary[ent.WORKSPACES]["used"] == 1
    assert summary[ent.WORKSPACES]["metered"] is False
    assert summary[ent.WHITE_LABEL]["enabled"] is False


async def test_deleting_a_workspace_frees_a_slot(
    db_session, user_factory, account_factory, organization_factory, set_limit
):
    """Stateful features are counted live, so removing one gives the slot back.
    Metered ones deliberately do not behave this way."""
    from datetime import datetime, timezone

    user = await user_factory(password=PASSWORD)
    organization = await organization_factory(user)
    await set_limit(organization, ent.WORKSPACES, 1)
    account = await account_factory(user, organization=organization)

    with pytest.raises(ent.EntitlementExceeded):
        await ent.enforce_stateful_limit(db_session, organization, ent.WORKSPACES)

    account.deleted_at = datetime.now(timezone.utc)
    await db_session.flush()
    await ent.enforce_stateful_limit(db_session, organization, ent.WORKSPACES)
