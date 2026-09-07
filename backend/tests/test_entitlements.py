"""Plan entitlements.

The monthly post allowance is what a paid tier actually buys, so the cap has to
hold at the boundary: the last allowed post succeeds and the next one is
refused, with an error that names the plan and the limit rather than failing
opaquely.
"""

import uuid

import pytest

from app.models.account import SubscriptionTier
from app.services.entitlements import TIER_LIMITS

pytestmark = pytest.mark.asyncio

PASSWORD = "hunter2-correct-horse"


def _posts_url(account_id) -> str:
    return f"/api/v1/accounts/{account_id}/posts/"


async def _create_post(client, auth_header, user, account, content="A post"):
    return await client.post(
        _posts_url(account.id),
        headers=auth_header(user),
        json={"content": content, "target_accounts": []},
    )


async def test_posts_allowed_up_to_the_cap(client, auth_header, user_factory, account_factory):
    """A small explicit limit keeps this fast; the mechanism is the same one the
    Free tier's 10 uses."""
    user = await user_factory(password=PASSWORD)
    account = await account_factory(user, monthly_post_limit=3)

    for i in range(3):
        response = await _create_post(client, auth_header, user, account, f"Post {i}")
        assert response.status_code == 201, (
            f"post {i + 1} of 3 was refused: {response.text[:200]}"
        )


async def test_post_over_the_cap_is_refused(client, auth_header, user_factory, account_factory):
    user = await user_factory(password=PASSWORD)
    account = await account_factory(user, monthly_post_limit=3)

    for i in range(3):
        await _create_post(client, auth_header, user, account, f"Post {i}")

    response = await _create_post(client, auth_header, user, account, "One too many")

    assert response.status_code == 403
    detail = response.json()["detail"].lower()
    assert "limit" in detail
    assert "upgrade" in detail, f"the error should say how to fix it: {detail!r}"


async def test_limit_error_names_the_plan(client, auth_header, user_factory, account_factory):
    user = await user_factory(password=PASSWORD)
    account = await account_factory(
        user, monthly_post_limit=1, subscription_tier=SubscriptionTier.FREE
    )
    await _create_post(client, auth_header, user, account)

    response = await _create_post(client, auth_header, user, account)
    assert response.status_code == 403
    assert "free" in response.json()["detail"].lower()


async def test_a_higher_tier_gets_a_higher_allowance(
    client, auth_header, user_factory, account_factory
):
    """The cap must follow the account's own limit, not a constant."""
    user = await user_factory(password=PASSWORD)
    account = await account_factory(user, monthly_post_limit=5)

    for i in range(5):
        assert (
            await _create_post(client, auth_header, user, account, f"P{i}")
        ).status_code == 201
    assert (
        await _create_post(client, auth_header, user, account, "P6")
    ).status_code == 403


async def test_each_account_has_its_own_allowance(
    client, auth_header, user_factory, account_factory
):
    """One account exhausting its quota must not spend another's."""
    user = await user_factory(password=PASSWORD)
    first = await account_factory(user, name="First", monthly_post_limit=1)
    second = await account_factory(user, name="Second", monthly_post_limit=1)

    assert (await _create_post(client, auth_header, user, first)).status_code == 201
    assert (await _create_post(client, auth_header, user, first)).status_code == 403
    assert (await _create_post(client, auth_header, user, second)).status_code == 201


async def test_unlimited_is_expressed_as_a_negative_limit(
    client, auth_header, user_factory, account_factory
):
    user = await user_factory(password=PASSWORD)
    account = await account_factory(user, monthly_post_limit=-1)

    for i in range(4):
        assert (
            await _create_post(client, auth_header, user, account, f"P{i}")
        ).status_code == 201


def test_tier_limits_are_monotonic():
    """A more expensive plan must never allow less than a cheaper one."""
    order = [
        SubscriptionTier.FREE,
        SubscriptionTier.STARTER,
        SubscriptionTier.GROWTH,
        SubscriptionTier.PRO,
        SubscriptionTier.ENTERPRISE,
    ]
    for key in ("posts", "members", "platforms"):
        values = [TIER_LIMITS[tier][key] for tier in order]
        assert values == sorted(values), f"{key} limits are not monotonic: {values}"


async def test_member_limit_blocks_an_invitation_at_the_cap(
    client, auth_header, user_factory, account_factory
):
    """The same entitlement machinery guards seats, and the Free tier's single
    seat is already taken by the owner."""
    user = await user_factory(password=PASSWORD)
    account = await account_factory(user, max_team_members=1)

    response = await client.post(
        f"/api/v1/accounts/{account.id}/team/invite",
        headers=auth_header(user),
        json={"email": f"new-{uuid.uuid4().hex[:8]}@example.com", "role": "viewer"},
    )
    assert response.status_code == 403
    assert "member" in response.json()["detail"].lower()
