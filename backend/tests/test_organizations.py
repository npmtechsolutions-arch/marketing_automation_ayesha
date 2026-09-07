"""The Organization tier: isolation, boundaries, and org-wide allowances.

Two rules carry most of the weight here.

**Allowances are organization-wide.** That is the point of the tier -- before it,
each workspace had its own subscription, so a company could reset its post
allowance by creating another workspace.

**Organization membership and workspace membership are separate boundaries.**
Holding an OrganizationMember row grants billing and the workspace list, not any
workspace's content. An accountant who needs the invoices should not thereby
gain every client's drafts.
"""

import uuid

import pytest

from app.models.organization import OrgRole
from app.models.team_member import InvitationStatus

pytestmark = pytest.mark.asyncio

PASSWORD = "hunter2-correct-horse"


def _org_url(org_id, suffix: str = "") -> str:
    return f"/api/v1/organizations/{org_id}{suffix}"


async def _create_post(client, auth_header, user, account, content="A post"):
    return await client.post(
        f"/api/v1/accounts/{account.id}/posts/",
        headers=auth_header(user),
        json={"content": content, "target_accounts": []},
    )


# ---------------------------------------------------------------------------
# The behavioural change: one allowance across all workspaces
# ---------------------------------------------------------------------------

async def test_post_allowance_is_shared_across_workspaces(
    client, auth_header, user_factory, account_factory, organization_factory, set_limit
):
    """The reason the Organization tier exists.

    Two workspaces, one organization, a limit of 2: the second workspace must
    not get a fresh allowance.
    """
    user = await user_factory(password=PASSWORD)
    organization = await organization_factory(user)
    await set_limit(organization, "posts_per_month", 2)
    await set_limit(organization, "workspaces", 5)
    first = await account_factory(user, name="Client A", organization=organization)
    second = await account_factory(user, name="Client B", organization=organization)

    assert (await _create_post(client, auth_header, user, first)).status_code == 201
    assert (await _create_post(client, auth_header, user, second)).status_code == 201

    # The allowance is spent, wherever the third post is attempted.
    third = await _create_post(client, auth_header, user, first)
    assert third.status_code == 402, (
        "the organization's allowance was not shared across its workspaces"
    )
    assert (await _create_post(client, auth_header, user, second)).status_code == 402


async def test_seats_are_counted_per_person_not_per_workspace(
    db_session, user_factory, account_factory, organization_factory, set_limit
):
    """One person across three workspaces occupies one seat, not three.

    Counting TeamMember rows would have charged this owner three times once
    seats became organization-wide.
    """
    from app.services.entitlements import count_team_members

    user = await user_factory(password=PASSWORD)
    organization = await organization_factory(user)
    await set_limit(organization, "team_members", 5)
    for name in ("A", "B", "C"):
        await account_factory(user, name=name, organization=organization)

    assert await count_team_members(db_session, organization.id) == 1


async def test_distinct_people_each_take_a_seat(
    db_session, user_factory, account_factory, organization_factory, member_factory, set_limit
):
    from app.models.team_member import TeamRole
    from app.services.entitlements import count_team_members

    owner = await user_factory(password=PASSWORD)
    colleague = await user_factory(password=PASSWORD)
    organization = await organization_factory(owner)
    await set_limit(organization, "team_members", 5)
    workspace = await account_factory(owner, organization=organization)
    await member_factory(
        colleague, workspace,
        role=TeamRole.EDITOR, invitation_status=InvitationStatus.ACCEPTED,
    )

    assert await count_team_members(db_session, organization.id) == 2


# ---------------------------------------------------------------------------
# Isolation
# ---------------------------------------------------------------------------

async def test_user_cannot_read_another_organization(
    client, auth_header, user_factory, organization_factory
):
    alice = await user_factory(password=PASSWORD)
    bob = await user_factory(password=PASSWORD)
    bob_org = await organization_factory(bob, name="Bob Inc")

    response = await client.get(_org_url(bob_org.id), headers=auth_header(alice))
    assert response.status_code == 403


async def test_unknown_organization_is_403_not_404(client, auth_header, user_factory):
    """A random id must look identical to someone else's organization, or the
    endpoint enumerates them."""
    user = await user_factory(password=PASSWORD)
    response = await client.get(_org_url(uuid.uuid4()), headers=auth_header(user))
    assert response.status_code == 403


async def test_owner_can_read_their_organization(
    client, auth_header, user_factory, organization_factory
):
    user = await user_factory(password=PASSWORD)
    organization = await organization_factory(user, name="Acme Inc")

    response = await client.get(_org_url(organization.id), headers=auth_header(user))
    assert response.status_code == 200
    assert response.json()["name"] == "Acme Inc"


async def test_list_shows_only_your_organizations(
    client, auth_header, user_factory, organization_factory
):
    alice = await user_factory(password=PASSWORD)
    bob = await user_factory(password=PASSWORD)
    await organization_factory(alice, name="Alice Inc")
    await organization_factory(bob, name="Bob Inc")

    response = await client.get("/api/v1/organizations/", headers=auth_header(alice))
    assert response.status_code == 200
    names = [o["name"] for o in response.json()]
    assert "Alice Inc" in names
    assert "Bob Inc" not in names


async def test_pending_org_invitation_grants_nothing(
    client, auth_header, user_factory, organization_factory, org_member_factory
):
    """The Phase 0.3 bug, checked against the second membership table."""
    owner = await user_factory(password=PASSWORD)
    invitee = await user_factory(password=PASSWORD)
    organization = await organization_factory(owner)
    await org_member_factory(
        invitee, organization,
        role=OrgRole.ADMIN, invitation_status=InvitationStatus.PENDING,
    )

    response = await client.get(_org_url(organization.id), headers=auth_header(invitee))
    assert response.status_code == 403


async def test_accepted_org_member_can_read(
    client, auth_header, user_factory, organization_factory, org_member_factory
):
    owner = await user_factory(password=PASSWORD)
    member = await user_factory(password=PASSWORD)
    organization = await organization_factory(owner)
    await org_member_factory(
        member, organization,
        role=OrgRole.MEMBER, invitation_status=InvitationStatus.ACCEPTED,
    )

    response = await client.get(_org_url(organization.id), headers=auth_header(member))
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# The two boundaries are independent
# ---------------------------------------------------------------------------

async def test_org_membership_does_not_grant_workspace_content(
    client, auth_header, user_factory, account_factory,
    organization_factory, org_member_factory,
):
    """An accepted MEMBER of the organization still cannot read a workspace's
    posts without a TeamMember row for that workspace."""
    owner = await user_factory(password=PASSWORD)
    accountant = await user_factory(password=PASSWORD)
    organization = await organization_factory(owner)
    workspace = await account_factory(owner, organization=organization)
    await org_member_factory(
        accountant, organization,
        role=OrgRole.MEMBER, invitation_status=InvitationStatus.ACCEPTED,
    )

    # They can see the organization and that the workspace exists...
    assert (
        await client.get(_org_url(organization.id), headers=auth_header(accountant))
    ).status_code == 200
    assert (
        await client.get(
            _org_url(organization.id, "/workspaces"), headers=auth_header(accountant)
        )
    ).status_code == 200

    # ...but not its contents.
    response = await client.get(
        f"/api/v1/accounts/{workspace.id}/posts/", headers=auth_header(accountant)
    )
    assert response.status_code == 403, (
        "organization membership leaked workspace content"
    )


async def test_workspace_membership_does_not_grant_org_access(
    client, auth_header, user_factory, account_factory,
    organization_factory, member_factory,
):
    """The converse: an editor in one workspace is not an organization member
    and cannot read the billing entity."""
    owner = await user_factory(password=PASSWORD)
    editor = await user_factory(password=PASSWORD)
    organization = await organization_factory(owner)
    workspace = await account_factory(owner, organization=organization)
    from app.models.team_member import TeamRole
    await member_factory(
        editor, workspace,
        role=TeamRole.EDITOR, invitation_status=InvitationStatus.ACCEPTED,
    )

    assert (
        await client.get(
            f"/api/v1/accounts/{workspace.id}/posts/", headers=auth_header(editor)
        )
    ).status_code == 200
    assert (
        await client.get(_org_url(organization.id), headers=auth_header(editor))
    ).status_code == 403


# ---------------------------------------------------------------------------
# Workspaces
# ---------------------------------------------------------------------------

async def test_workspace_list_is_scoped_to_the_organization(
    client, auth_header, user_factory, account_factory, organization_factory
):
    user = await user_factory(password=PASSWORD)
    mine = await organization_factory(user, name="Mine")
    other = await organization_factory(user, name="Other")
    await account_factory(user, name="In Mine", organization=mine)
    await account_factory(user, name="In Other", organization=other)

    response = await client.get(_org_url(mine.id, "/workspaces"), headers=auth_header(user))
    assert response.status_code == 200
    names = [w["name"] for w in response.json()["items"]]
    assert names == ["In Mine"]


async def test_workspace_cap_is_enforced(
    client, auth_header, user_factory, account_factory, organization_factory, set_limit
):
    user = await user_factory(password=PASSWORD)
    organization = await organization_factory(user)
    await set_limit(organization, "workspaces", 2)
    await account_factory(user, name="One", organization=organization)

    second = await client.post(
        _org_url(organization.id, "/workspaces"),
        headers=auth_header(user),
        json={"name": "Two"},
    )
    assert second.status_code == 201, second.text

    third = await client.post(
        _org_url(organization.id, "/workspaces"),
        headers=auth_header(user),
        json={"name": "Three"},
    )
    # 402 Payment Required: authorised, but the plan does not cover it.
    assert third.status_code == 402
    detail = third.json()["detail"].lower()
    assert "workspace" in detail and "upgrade" in detail


async def test_unlimited_workspaces_on_enterprise(
    client, auth_header, user_factory, organization_factory, set_limit
):
    user = await user_factory(password=PASSWORD)
    organization = await organization_factory(user)
    await set_limit(organization, "workspaces", None)  # NULL = unlimited

    for i in range(3):
        response = await client.post(
            _org_url(organization.id, "/workspaces"),
            headers=auth_header(user),
            json={"name": f"WS {i}"},
        )
        assert response.status_code == 201, response.text


async def test_creating_a_workspace_requires_admin(
    client, auth_header, user_factory, organization_factory, org_member_factory, set_limit
):
    owner = await user_factory(password=PASSWORD)
    member = await user_factory(password=PASSWORD)
    organization = await organization_factory(owner)
    await set_limit(organization, "workspaces", 10)
    await org_member_factory(
        member, organization,
        role=OrgRole.MEMBER, invitation_status=InvitationStatus.ACCEPTED,
    )

    response = await client.post(
        _org_url(organization.id, "/workspaces"),
        headers=auth_header(member),
        json={"name": "Sneaky"},
    )
    assert response.status_code == 403


async def test_rename_requires_admin(
    client, auth_header, user_factory, organization_factory, org_member_factory
):
    owner = await user_factory(password=PASSWORD)
    member = await user_factory(password=PASSWORD)
    organization = await organization_factory(owner, name="Before")
    await org_member_factory(
        member, organization,
        role=OrgRole.MEMBER, invitation_status=InvitationStatus.ACCEPTED,
    )

    assert (
        await client.patch(
            _org_url(organization.id), headers=auth_header(member),
            json={"name": "After"},
        )
    ).status_code == 403

    ok = await client.patch(
        _org_url(organization.id), headers=auth_header(owner), json={"name": "After"}
    )
    assert ok.status_code == 200
    assert ok.json()["name"] == "After"


async def test_patch_cannot_change_the_subscription_tier(
    client, auth_header, user_factory, organization_factory
):
    """Tier changes go through billing and Stripe. Accepting one here would let
    an admin PATCH themselves onto Enterprise."""
    user = await user_factory(password=PASSWORD)
    organization = await organization_factory(user)

    response = await client.patch(
        _org_url(organization.id),
        headers=auth_header(user),
        json={"name": "Renamed", "subscription_tier": "enterprise"},
    )
    assert response.status_code == 200
    assert response.json()["subscription_tier"] == "free"


async def test_registration_provisions_an_organization(client):
    """A new user gets an Organization, a Workspace, and ownership of both."""
    email = f"orgnew-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "Org Newcomer"},
    )
    assert register.status_code == 201, register.text
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}

    orgs = await client.get("/api/v1/organizations/", headers=headers)
    assert orgs.status_code == 200
    assert len(orgs.json()) == 1
    organization = orgs.json()[0]
    # apply_tier ran, rather than leaning on column defaults.
    assert organization["subscription_tier"] == "free"
    assert organization["max_workspaces"] == 1

    workspaces = await client.get(
        _org_url(organization["id"], "/workspaces"), headers=headers
    )
    assert workspaces.status_code == 200
    assert workspaces.json()["total"] == 1
