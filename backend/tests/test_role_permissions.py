"""The role/permission matrix.

Authorization used to compare roles by index in a list, which works only while
roles form a ladder. CONTRIBUTOR, ANALYST and CLIENT do not: an analyst is not a
weaker manager, they see a different slice. What each role may do is now a
permission set, and this file asserts the resulting behaviour endpoint by
endpoint rather than trusting the registry to be self-consistent.
"""

import uuid

import pytest

from app.core.permissions import (
    CONTENT_CREATE,
    CONTENT_PUBLISH,
    PERMISSIONS,
    ROLE_DESCRIPTIONS,
    ROLE_PERMISSIONS,
    permissions_for,
    role_has_permission,
)
from app.models.post import Post, PostStatus
from app.models.team_member import InvitationStatus, TeamRole

pytestmark = pytest.mark.asyncio

PASSWORD = "hunter2-correct-horse"


@pytest.fixture
async def workspace(user_factory, account_factory, organization_factory, set_limit):
    owner = await user_factory(password=PASSWORD)
    organization = await organization_factory(owner)
    # Headroom, so a permission test never fails for want of quota.
    await set_limit(organization, "posts_per_month", 500)
    account = await account_factory(owner, organization=organization)
    return {"owner": owner, "organization": organization, "account": account}


async def _member_with(user_factory, member_factory, workspace, role: TeamRole):
    user = await user_factory(password=PASSWORD)
    await member_factory(
        user, workspace["account"], role=role,
        invitation_status=InvitationStatus.ACCEPTED,
    )
    return user


async def _seed_post(db_session, workspace, status=PostStatus.DRAFT) -> Post:
    post = Post(
        id=uuid.uuid4(),
        user_id=workspace["owner"].id,
        account_id=workspace["account"].id,
        content="Seeded",
        status=status,
    )
    db_session.add(post)
    await db_session.flush()
    return post


# ---------------------------------------------------------------------------
# The registry itself
# ---------------------------------------------------------------------------

async def test_every_role_has_a_permission_set():
    """A role added to the enum without a mapping would silently grant nothing;
    better to catch it here than in production."""
    for role in TeamRole:
        assert role in ROLE_PERMISSIONS, f"{role.value} has no permission set"
        assert role in ROLE_DESCRIPTIONS, f"{role.value} has no description"


async def test_permission_sets_reference_known_permissions():
    for role, granted in ROLE_PERMISSIONS.items():
        unknown = granted - set(PERMISSIONS)
        assert not unknown, f"{role.value} references unknown permissions: {unknown}"


async def test_owner_has_everything():
    assert permissions_for(TeamRole.OWNER) == frozenset(PERMISSIONS)


async def test_client_has_exactly_two_permissions():
    """The spec is precise: view (approval items only) and approve."""
    assert permissions_for(TeamRole.CLIENT) == frozenset(
        {"content.view", "content.approve"}
    )


async def test_contributor_cannot_publish():
    assert role_has_permission(TeamRole.CONTRIBUTOR, CONTENT_CREATE)
    assert not role_has_permission(TeamRole.CONTRIBUTOR, CONTENT_PUBLISH)


async def test_analyst_has_no_content_access():
    granted = permissions_for(TeamRole.ANALYST)
    assert not any(p.startswith("content.") for p in granted)
    assert "analytics.view" in granted and "reports.view" in granted


async def test_unknown_role_grants_nothing():
    """Fails closed rather than inheriting someone else's access."""
    assert permissions_for("wizard") == frozenset()
    assert not role_has_permission("wizard", CONTENT_CREATE)


# ---------------------------------------------------------------------------
# The matrix, driven through the API
# ---------------------------------------------------------------------------

# (role, expected status) for POST /posts/ -- creating a draft.
CREATE_MATRIX = [
    (TeamRole.OWNER, 201), (TeamRole.ADMIN, 201), (TeamRole.MANAGER, 201),
    (TeamRole.EDITOR, 201), (TeamRole.CONTRIBUTOR, 201),
    (TeamRole.VIEWER, 403), (TeamRole.ANALYST, 403), (TeamRole.CLIENT, 403),
]


@pytest.mark.parametrize("role,expected", CREATE_MATRIX, ids=lambda v: getattr(v, "value", v))
async def test_create_post_matrix(
    client, auth_header, user_factory, member_factory, workspace, role, expected
):
    user = await _member_with(user_factory, member_factory, workspace, role)
    response = await client.post(
        f"/api/v1/accounts/{workspace['account'].id}/posts/",
        headers=auth_header(user),
        json={"content": "A draft", "target_accounts": []},
    )
    assert response.status_code == expected, (
        f"{role.value} got {response.status_code}: {response.text[:160]}"
    )


PUBLISH_MATRIX = [
    (TeamRole.OWNER, True), (TeamRole.ADMIN, True), (TeamRole.MANAGER, True),
    (TeamRole.EDITOR, True), (TeamRole.CONTRIBUTOR, False),
    (TeamRole.VIEWER, False), (TeamRole.ANALYST, False), (TeamRole.CLIENT, False),
]


@pytest.mark.parametrize("role,allowed", PUBLISH_MATRIX, ids=lambda v: getattr(v, "value", v))
async def test_publish_matrix(
    client, auth_header, db_session, user_factory, member_factory, workspace, role, allowed
):
    """The headline case: a contributor drafts but cannot publish."""
    user = await _member_with(user_factory, member_factory, workspace, role)
    post = await _seed_post(db_session, workspace, status=PostStatus.APPROVED)

    response = await client.post(
        f"/api/v1/accounts/{workspace['account'].id}/posts/{post.id}/publish",
        headers=auth_header(user),
    )
    if allowed:
        assert response.status_code != 403, f"{role.value} was denied publishing"
    else:
        assert response.status_code == 403, (
            f"{role.value} was allowed to publish (got {response.status_code})"
        )


SCHEDULE_DENIED = [TeamRole.CONTRIBUTOR, TeamRole.VIEWER, TeamRole.ANALYST, TeamRole.CLIENT]


@pytest.mark.parametrize("role", SCHEDULE_DENIED, ids=lambda r: r.value)
async def test_scheduling_counts_as_publishing(
    client, auth_header, db_session, user_factory, member_factory, workspace, role
):
    """Scheduling is publishing, deferred. A role that cannot publish must not
    be able to schedule either -- otherwise the restriction is cosmetic."""
    user = await _member_with(user_factory, member_factory, workspace, role)
    post = await _seed_post(db_session, workspace, status=PostStatus.APPROVED)

    response = await client.post(
        f"/api/v1/accounts/{workspace['account'].id}/posts/{post.id}/schedule",
        headers=auth_header(user),
        params={"scheduled_at": "2027-01-01T12:00:00Z"},
    )
    assert response.status_code == 403


APPROVE_MATRIX = [
    (TeamRole.OWNER, True), (TeamRole.ADMIN, True), (TeamRole.MANAGER, True),
    (TeamRole.CLIENT, True),
    (TeamRole.EDITOR, False), (TeamRole.CONTRIBUTOR, False),
    (TeamRole.VIEWER, False), (TeamRole.ANALYST, False),
]


@pytest.mark.parametrize("role,allowed", APPROVE_MATRIX, ids=lambda v: getattr(v, "value", v))
async def test_approve_matrix(
    client, auth_header, db_session, user_factory, member_factory, workspace, role, allowed
):
    """A CLIENT can approve -- that is the entire reason the role exists -- while
    an EDITOR, who outranks them on the old ladder, cannot."""
    user = await _member_with(user_factory, member_factory, workspace, role)
    post = await _seed_post(db_session, workspace, status=PostStatus.PENDING_APPROVAL)

    response = await client.post(
        f"/api/v1/accounts/{workspace['account'].id}/posts/{post.id}/approve",
        headers=auth_header(user),
    )
    if allowed:
        assert response.status_code != 403, f"{role.value} was denied approval"
    else:
        assert response.status_code == 403, (
            f"{role.value} was allowed to approve (got {response.status_code})"
        )


async def test_analyst_can_read_analytics_but_not_posts(
    client, auth_header, user_factory, member_factory, workspace
):
    user = await _member_with(user_factory, member_factory, workspace, TeamRole.ANALYST)
    base = f"/api/v1/accounts/{workspace['account'].id}"

    assert (
        await client.get(f"{base}/analytics/overview", headers=auth_header(user))
    ).status_code == 200
    assert (
        await client.get(f"{base}/posts/", headers=auth_header(user))
    ).status_code == 403


async def test_client_sees_only_items_awaiting_approval(
    client, auth_header, db_session, user_factory, member_factory, workspace
):
    """content.view for a CLIENT is narrowed at the query level. A permission
    bit alone would have exposed every draft in the workspace."""
    user = await _member_with(user_factory, member_factory, workspace, TeamRole.CLIENT)
    await _seed_post(db_session, workspace, status=PostStatus.DRAFT)
    await _seed_post(db_session, workspace, status=PostStatus.PUBLISHED)
    await _seed_post(db_session, workspace, status=PostStatus.PENDING_APPROVAL)

    response = await client.get(
        f"/api/v1/accounts/{workspace['account'].id}/posts/", headers=auth_header(user)
    )
    assert response.status_code == 200
    statuses = {item["status"] for item in response.json()["items"]}
    assert statuses == {"pending_approval"}, (
        f"a client saw content outside the approval queue: {statuses}"
    )


async def test_editor_sees_everything_the_client_cannot(
    client, auth_header, db_session, user_factory, member_factory, workspace
):
    """The counterpart: the narrowing is specific to CLIENT, not applied to all."""
    user = await _member_with(user_factory, member_factory, workspace, TeamRole.EDITOR)
    await _seed_post(db_session, workspace, status=PostStatus.DRAFT)
    await _seed_post(db_session, workspace, status=PostStatus.PENDING_APPROVAL)

    response = await client.get(
        f"/api/v1/accounts/{workspace['account'].id}/posts/", headers=auth_header(user)
    )
    assert response.status_code == 200
    assert len(response.json()["items"]) == 2


TEAM_VIEW_MATRIX = [
    (TeamRole.OWNER, 200), (TeamRole.ADMIN, 200), (TeamRole.MANAGER, 200),
    (TeamRole.EDITOR, 200), (TeamRole.VIEWER, 200), (TeamRole.CONTRIBUTOR, 200),
    (TeamRole.ANALYST, 200),
    # No internal data for an external reviewer.
    (TeamRole.CLIENT, 403),
]


@pytest.mark.parametrize("role,expected", TEAM_VIEW_MATRIX, ids=lambda v: getattr(v, "value", v))
async def test_team_visibility_matrix(
    client, auth_header, user_factory, member_factory, workspace, role, expected
):
    user = await _member_with(user_factory, member_factory, workspace, role)
    response = await client.get(
        f"/api/v1/accounts/{workspace['account'].id}/team/", headers=auth_header(user)
    )
    assert response.status_code == expected, (
        f"{role.value} got {response.status_code} on the team list"
    )


BILLING_MANAGE_DENIED = [
    TeamRole.MANAGER, TeamRole.EDITOR, TeamRole.VIEWER,
    TeamRole.CONTRIBUTOR, TeamRole.ANALYST, TeamRole.CLIENT,
]


@pytest.mark.parametrize("role", BILLING_MANAGE_DENIED, ids=lambda r: r.value)
async def test_only_admins_change_the_plan(
    client, auth_header, user_factory, member_factory, workspace, role
):
    user = await _member_with(user_factory, member_factory, workspace, role)
    response = await client.post(
        f"/api/v1/accounts/{workspace['account'].id}/billing/change-plan",
        headers=auth_header(user),
        json={"tier": "growth"},
    )
    assert response.status_code == 403


async def test_denial_message_names_the_role_and_the_action(
    client, auth_header, user_factory, member_factory, workspace
):
    """A bare 'forbidden' leaves the user guessing which of their roles is wrong."""
    user = await _member_with(user_factory, member_factory, workspace, TeamRole.CONTRIBUTOR)
    post_id = uuid.uuid4()
    response = await client.post(
        f"/api/v1/accounts/{workspace['account'].id}/posts/{post_id}/publish",
        headers=auth_header(user),
    )
    assert response.status_code == 403
    detail = response.json()["detail"].lower()
    assert "contributor" in detail
    assert "publish" in detail
