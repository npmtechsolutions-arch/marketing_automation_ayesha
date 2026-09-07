"""Cross-account isolation.

The product is multi-tenant: one user's account must be invisible to another's.
Every account-scoped endpoint goes through ``verify_account_access``, and these
tests drive the HTTP surface to confirm the boundary actually holds rather than
trusting that every route remembered to call it.

The threat is mundane and the worst kind: account ids appear in URLs, so
swapping one for another is the first thing anyone tries.
"""

import uuid

import pytest

pytestmark = pytest.mark.asyncio

PASSWORD = "hunter2-correct-horse"


@pytest.fixture
async def two_tenants(user_factory, account_factory):
    """Two unrelated users, each owning their own account."""
    alice = await user_factory(full_name="Alice", password=PASSWORD)
    bob = await user_factory(full_name="Bob", password=PASSWORD)
    alice_account = await account_factory(alice, name="Alice Co")
    bob_account = await account_factory(bob, name="Bob Co")
    return {
        "alice": alice,
        "bob": bob,
        "alice_account": alice_account,
        "bob_account": bob_account,
    }


# Read endpoints across every module that owns account-scoped data.
READ_PATHS = [
    pytest.param("/api/v1/accounts/{account_id}/posts/", id="posts"),
    pytest.param("/api/v1/accounts/{account_id}/analytics/overview", id="analytics"),
    pytest.param("/api/v1/accounts/{account_id}/billing/", id="billing"),
    pytest.param("/api/v1/accounts/{account_id}/campaigns/", id="campaigns"),
    pytest.param("/api/v1/accounts/{account_id}/strategies/", id="strategies"),
    pytest.param("/api/v1/accounts/{account_id}/settings/", id="settings"),
    pytest.param("/api/v1/accounts/{account_id}/team/", id="team"),
    pytest.param("/api/v1/accounts/{account_id}/activity/", id="activity"),
    pytest.param("/api/v1/accounts/{account_id}/social-accounts/", id="social-accounts"),
]


@pytest.mark.parametrize("path", READ_PATHS)
async def test_user_cannot_read_another_accounts_data(
    client, auth_header, two_tenants, path
):
    """Alice, fully authenticated, reading Bob's account must be refused."""
    response = await client.get(
        path.format(account_id=two_tenants["bob_account"].id),
        headers=auth_header(two_tenants["alice"]),
    )

    assert response.status_code == 403, (
        f"{path} leaked another account's data (status {response.status_code})"
    )


@pytest.mark.parametrize("path", READ_PATHS)
async def test_owner_can_read_their_own_account(client, auth_header, two_tenants, path):
    """The counterpart: the boundary must not be blocking legitimate access."""
    response = await client.get(
        path.format(account_id=two_tenants["alice_account"].id),
        headers=auth_header(two_tenants["alice"]),
    )
    assert response.status_code != 403, (
        f"{path} denied the account's own owner: {response.text[:200]}"
    )


async def test_user_cannot_write_to_another_account(client, auth_header, two_tenants):
    """Reading is not the only risk -- creation must be refused too."""
    response = await client.post(
        f"/api/v1/accounts/{two_tenants['bob_account'].id}/posts/",
        headers=auth_header(two_tenants["alice"]),
        json={"content": "planted by Alice", "target_accounts": []},
    )
    assert response.status_code == 403


async def test_user_cannot_invite_themselves_into_another_account(
    client, auth_header, two_tenants
):
    """Otherwise the boundary is one request away from being self-service."""
    response = await client.post(
        f"/api/v1/accounts/{two_tenants['bob_account'].id}/team/invite",
        headers=auth_header(two_tenants["alice"]),
        json={"email": two_tenants["alice"].email, "role": "admin"},
    )
    assert response.status_code == 403


async def test_user_cannot_change_another_accounts_settings(
    client, auth_header, two_tenants
):
    response = await client.put(
        f"/api/v1/accounts/{two_tenants['bob_account'].id}/settings/",
        headers=auth_header(two_tenants["alice"]),
        json={"name": "Owned by Alice now"},
    )
    assert response.status_code in (403, 404, 405)


async def test_unauthenticated_access_is_refused(client, two_tenants):
    response = await client.get(
        f"/api/v1/accounts/{two_tenants['alice_account'].id}/posts/"
    )
    assert response.status_code in (401, 403)


async def test_nonexistent_account_is_refused_not_leaked(client, auth_header, two_tenants):
    """A random id must look the same as someone else's account -- a different
    status for "exists but not yours" would enumerate accounts."""
    response = await client.get(
        f"/api/v1/accounts/{uuid.uuid4()}/posts/",
        headers=auth_header(two_tenants["alice"]),
    )
    assert response.status_code == 403


async def test_pending_invitee_is_still_outside_the_boundary(
    client, auth_header, two_tenants, member_factory
):
    """The 0.3 fix, checked from the tenancy side: an unaccepted invitation is
    not membership."""
    from app.models.team_member import InvitationStatus, TeamRole

    await member_factory(
        two_tenants["alice"],
        two_tenants["bob_account"],
        role=TeamRole.ADMIN,
        invitation_status=InvitationStatus.PENDING,
    )

    response = await client.get(
        f"/api/v1/accounts/{two_tenants['bob_account'].id}/posts/",
        headers=auth_header(two_tenants["alice"]),
    )
    assert response.status_code == 403


async def test_accepted_member_crosses_the_boundary_legitimately(
    client, auth_header, two_tenants, member_factory
):
    from app.models.team_member import InvitationStatus, TeamRole

    await member_factory(
        two_tenants["alice"],
        two_tenants["bob_account"],
        role=TeamRole.VIEWER,
        invitation_status=InvitationStatus.ACCEPTED,
    )

    response = await client.get(
        f"/api/v1/accounts/{two_tenants['bob_account'].id}/posts/",
        headers=auth_header(two_tenants["alice"]),
    )
    assert response.status_code == 200


async def test_accounts_list_shows_only_your_own(client, auth_header, two_tenants):
    response = await client.get(
        "/api/v1/accounts/", headers=auth_header(two_tenants["alice"])
    )
    assert response.status_code == 200

    names = [item["name"] for item in response.json().get("items", [])]
    assert "Alice Co" in names
    assert "Bob Co" not in names, "the account list leaked another tenant"
