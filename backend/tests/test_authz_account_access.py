"""Regression tests for account-level authorization.

The bug these lock down: ``_verify_account_access`` was copy-pasted into seven
endpoint modules and none of the copies filtered on ``invitation_status``.
``teams.py`` creates an invitation for an already-registered user as a
``TeamMember`` row with ``user_id`` set and ``invitation_status = PENDING``, so
a merely *invited* user was granted full access at their invited role before
accepting the invitation.
"""

import uuid

import pytest

from app.core.authz import ROLE_HIERARCHY, verify_account_access
from app.models.team_member import InvitationStatus, TeamRole

pytestmark = pytest.mark.asyncio

# One representative account-scoped endpoint per module that used to carry its
# own copy of the helper. All are plain GETs that hit the access check first.
READ_ENDPOINTS = [
    pytest.param("/api/v1/accounts/{account_id}/posts/", id="posts"),
    pytest.param("/api/v1/accounts/{account_id}/billing/", id="billing"),
    pytest.param("/api/v1/accounts/{account_id}/analytics/overview", id="analytics"),
    pytest.param("/api/v1/accounts/{account_id}/campaigns/", id="campaigns"),
    pytest.param("/api/v1/accounts/{account_id}/strategies/", id="strategies"),
    pytest.param("/api/v1/accounts/{account_id}/settings/", id="settings"),
]


# ---------------------------------------------------------------------------
# (a) A pending invitee must be denied
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", READ_ENDPOINTS)
async def test_pending_invitee_is_denied(
    client, auth_header, user_factory, account_factory, member_factory, path
):
    """A PENDING TeamMember row with user_id set grants no access."""
    owner = await user_factory()
    account = await account_factory(owner)
    invitee = await user_factory()
    # Exactly what teams.py writes when inviting an existing user.
    await member_factory(
        invitee, account, role=TeamRole.ADMIN,
        invitation_status=InvitationStatus.PENDING,
    )

    response = await client.get(
        path.format(account_id=account.id), headers=auth_header(invitee)
    )

    assert response.status_code == 403, (
        f"{path} allowed a PENDING invitee (status {response.status_code})"
    )


async def test_pending_invitee_is_denied_on_ai_endpoint(
    client, auth_header, user_factory, account_factory, member_factory
):
    """The AI module's copy of the helper had no min_role parameter at all."""
    owner = await user_factory()
    account = await account_factory(owner)
    invitee = await user_factory()
    await member_factory(
        invitee, account, role=TeamRole.ADMIN,
        invitation_status=InvitationStatus.PENDING,
    )

    # The access check runs before the business lookup, so a business_id that
    # does not exist must still come back 403 (not 404) for a pending invitee.
    response = await client.post(
        f"/api/v1/accounts/{account.id}/ai/suggest-topics",
        headers=auth_header(invitee),
        json={"business_id": str(uuid.uuid4()), "count": 3},
    )

    assert response.status_code == 403


async def test_expired_invitation_is_denied(
    client, auth_header, user_factory, account_factory, member_factory
):
    owner = await user_factory()
    account = await account_factory(owner)
    invitee = await user_factory()
    await member_factory(
        invitee, account, role=TeamRole.OWNER,
        invitation_status=InvitationStatus.EXPIRED,
    )

    response = await client.get(
        f"/api/v1/accounts/{account.id}/posts/", headers=auth_header(invitee)
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# (b) An accepted member passes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", READ_ENDPOINTS)
async def test_accepted_member_is_allowed(
    client, auth_header, user_factory, account_factory, member_factory, path
):
    """The fix must not lock out legitimate members: same row, ACCEPTED."""
    owner = await user_factory()
    account = await account_factory(owner)
    member = await user_factory()
    await member_factory(
        member, account, role=TeamRole.ADMIN,
        invitation_status=InvitationStatus.ACCEPTED,
    )

    response = await client.get(
        path.format(account_id=account.id), headers=auth_header(member)
    )

    assert response.status_code != 403, (
        f"{path} denied an ACCEPTED member: {response.status_code} {response.text[:200]}"
    )


@pytest.mark.parametrize("path", READ_ENDPOINTS)
async def test_owner_is_allowed(client, auth_header, user_factory, account_factory, path):
    """Account owners get an ACCEPTED row at creation and must keep access."""
    owner = await user_factory()
    account = await account_factory(owner)

    response = await client.get(
        path.format(account_id=account.id), headers=auth_header(owner)
    )
    assert response.status_code != 403


async def test_non_member_is_denied(
    client, auth_header, user_factory, account_factory
):
    """A user with no TeamMember row at all is still denied."""
    owner = await user_factory()
    account = await account_factory(owner)
    stranger = await user_factory()

    response = await client.get(
        f"/api/v1/accounts/{account.id}/posts/", headers=auth_header(stranger)
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# (c) Role hierarchy is still enforced
# ---------------------------------------------------------------------------

async def test_role_hierarchy_order():
    """VIEWER < EDITOR < MANAGER < ADMIN < OWNER, per RBAC-Permissions.md."""
    assert list(ROLE_HIERARCHY) == [
        TeamRole.VIEWER,
        TeamRole.EDITOR,
        TeamRole.MANAGER,
        TeamRole.ADMIN,
        TeamRole.OWNER,
    ]


@pytest.mark.parametrize(
    "role,min_role,allowed",
    [
        (TeamRole.VIEWER, TeamRole.EDITOR, False),
        (TeamRole.EDITOR, TeamRole.EDITOR, True),
        (TeamRole.EDITOR, TeamRole.MANAGER, False),
        (TeamRole.MANAGER, TeamRole.EDITOR, True),
        (TeamRole.MANAGER, TeamRole.ADMIN, False),
        (TeamRole.ADMIN, TeamRole.MANAGER, True),
        (TeamRole.OWNER, TeamRole.ADMIN, True),
        (TeamRole.VIEWER, None, True),
    ],
)
async def test_min_role_enforced(
    db_session, user_factory, account_factory, member_factory, role, min_role, allowed
):
    from fastapi import HTTPException

    owner = await user_factory()
    account = await account_factory(owner)
    member_user = await user_factory()
    await member_factory(
        member_user, account, role=role,
        invitation_status=InvitationStatus.ACCEPTED,
    )

    if allowed:
        member = await verify_account_access(
            account.id, member_user, db_session, min_role=min_role
        )
        assert member.role is role
    else:
        with pytest.raises(HTTPException) as exc:
            await verify_account_access(
                account.id, member_user, db_session, min_role=min_role
            )
        assert exc.value.status_code == 403


async def test_min_role_not_bypassed_by_pending_high_role(
    db_session, user_factory, account_factory, member_factory
):
    """A PENDING OWNER invitation must not satisfy even the lowest min_role."""
    from fastapi import HTTPException

    owner = await user_factory()
    account = await account_factory(owner)
    invitee = await user_factory()
    await member_factory(
        invitee, account, role=TeamRole.OWNER,
        invitation_status=InvitationStatus.PENDING,
    )

    with pytest.raises(HTTPException) as exc:
        await verify_account_access(
            account.id, invitee, db_session, min_role=TeamRole.VIEWER
        )
    assert exc.value.status_code == 403


async def test_write_endpoint_enforces_editor_role(
    client, auth_header, user_factory, account_factory, member_factory
):
    """An accepted VIEWER cannot create a post (needs EDITOR)."""
    owner = await user_factory()
    account = await account_factory(owner)
    viewer = await user_factory()
    await member_factory(
        viewer, account, role=TeamRole.VIEWER,
        invitation_status=InvitationStatus.ACCEPTED,
    )

    response = await client.post(
        f"/api/v1/accounts/{account.id}/posts/",
        headers=auth_header(viewer),
        json={"content": "hello world", "target_accounts": []},
    )
    assert response.status_code == 403
    assert "editor" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Structural guarantee: one implementation, not seven
# ---------------------------------------------------------------------------

async def test_all_endpoint_modules_share_one_implementation():
    """Every module must bind to the single function in app.core.authz."""
    from app.api.v1.endpoints import (
        ai, analytics, billing, campaigns, posts, strategies,
        settings as settings_routes,
    )

    for module in (
        posts, billing, ai, analytics, campaigns, strategies, settings_routes,
    ):
        assert module._verify_account_access is verify_account_access, (
            f"{module.__name__} does not use the shared verify_account_access"
        )


async def test_teams_helper_also_requires_accepted(
    db_session, user_factory, account_factory, member_factory
):
    """teams.py has its own helper; it must have the same invitation gate."""
    from fastapi import HTTPException

    from app.api.v1.endpoints.teams import _get_member_or_403

    owner = await user_factory()
    account = await account_factory(owner)
    invitee = await user_factory()
    await member_factory(
        invitee, account, role=TeamRole.ADMIN,
        invitation_status=InvitationStatus.PENDING,
    )

    with pytest.raises(HTTPException) as exc:
        await _get_member_or_403(db_session, invitee.id, account.id)
    assert exc.value.status_code == 403


async def test_unknown_account_is_denied(
    client, auth_header, user_factory
):
    """No membership row exists for a random account id."""
    user = await user_factory()
    response = await client.get(
        f"/api/v1/accounts/{uuid.uuid4()}/posts/", headers=auth_header(user)
    )
    assert response.status_code == 403
