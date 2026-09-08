"""The review workflow: transitions, client isolation, mentions.

Three things carry the weight. The transition matrix, because a workflow whose
rules differ between endpoints stops meaning anything. Client isolation,
because CLIENT holds content.view and that must not become "sees every draft".
And the client-approval chain, because an internal approval standing in for the
customer's is the failure that matters commercially.
"""

import uuid

import pytest
from sqlalchemy import select

from app.models.notification import Notification
from app.models.post import Post, PostStatus
from app.models.post_comment import PostComment
from app.models.team_member import InvitationStatus, TeamRole

pytestmark = pytest.mark.asyncio

PASSWORD = "hunter2-correct-horse"


@pytest.fixture
async def workspace(
    db_session, user_factory, account_factory, organization_factory, member_factory
):
    """A workspace with one member per role that matters here."""

    async def _make(*, approvals=False, client_approval=False):
        owner = await user_factory(password=PASSWORD, full_name="Olive Owner")
        organization = await organization_factory(owner)
        account = await account_factory(owner, organization=organization)
        if approvals or client_approval:
            account.settings = {
                "approvals_required": approvals,
                "client_approval_required": client_approval,
            }
            await db_session.flush()

        people = {"owner": owner}
        for key, role in (
            ("editor", TeamRole.EDITOR),
            ("manager", TeamRole.MANAGER),
            ("client", TeamRole.CLIENT),
            ("viewer", TeamRole.VIEWER),
        ):
            person = await user_factory(password=PASSWORD, full_name=key.title())
            await member_factory(
                person, account, role=role,
                invitation_status=InvitationStatus.ACCEPTED,
            )
            people[key] = person

        return {
            "account": account, "account_id": account.id, **people,
        }

    return _make


async def _post(db_session, ws, *, status=PostStatus.DRAFT, author=None, **kw):
    post = Post(
        id=uuid.uuid4(),
        user_id=(author or ws["owner"]).id,
        account_id=ws["account_id"],
        content="A post to review",
        status=status,
        target_accounts=[],
        **kw,
    )
    db_session.add(post)
    await db_session.flush()
    return post


def _url(account_id, post_id, suffix=""):
    return f"/api/v1/accounts/{account_id}/posts/{post_id}{suffix}"


# ---------------------------------------------------------------------------
# Transition matrix
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "actor,action,start,expected",
    [
        # Authors submit.
        ("editor", "submit-for-review", PostStatus.DRAFT, 200),
        ("editor", "submit-for-review", PostStatus.CHANGES_REQUESTED, 200),
        # Already in review: nothing to submit.
        ("editor", "submit-for-review", PostStatus.IN_REVIEW, 409),
        # An editor cannot approve their own work.
        ("editor", "approve", PostStatus.IN_REVIEW, 403),
        # Managers approve.
        ("manager", "approve", PostStatus.IN_REVIEW, 200),
        ("owner", "approve", PostStatus.IN_REVIEW, 200),
        # ...but not a draft that was never submitted.
        ("manager", "approve", PostStatus.DRAFT, 409),
        # A viewer has neither permission.
        ("viewer", "approve", PostStatus.IN_REVIEW, 403),
        ("viewer", "submit-for-review", PostStatus.DRAFT, 403),
        # A CLIENT must not clear internal review; that is the manager's job.
        # 404 rather than 403: an internally-reviewed post is outside their
        # queue, and telling them it exists is itself a disclosure.
        ("client", "approve", PostStatus.IN_REVIEW, 404),
        # But they do clear their own queue.
        ("client", "approve", PostStatus.CLIENT_REVIEW, 200),
    ],
)
async def test_transition_matrix(
    client, auth_header, db_session, workspace, actor, action, start, expected
):
    ws = await workspace()
    post = await _post(db_session, ws, status=start)

    response = await client.post(
        _url(ws["account_id"], post.id, f"/{action}"),
        headers=auth_header(ws[actor]),
        json={"comment": "Looks good"},
    )
    assert response.status_code == expected, response.text


async def test_request_changes_needs_a_reason(
    client, auth_header, db_session, workspace
):
    """"Rejected" with no explanation is a message the author has to chase."""
    ws = await workspace()
    post = await _post(db_session, ws, status=PostStatus.IN_REVIEW)
    url = _url(ws["account_id"], post.id, "/request-changes")

    blank = await client.post(url, headers=auth_header(ws["manager"]), json={"comment": "  "})
    assert blank.status_code == 400
    assert "reason" in blank.json()["detail"] or "Explain" in blank.json()["detail"]

    given = await client.post(
        url, headers=auth_header(ws["manager"]),
        json={"comment": "Tighten the opening line."},
    )
    assert given.status_code == 200
    assert given.json()["status"] == "changes_requested"


async def test_request_changes_records_the_reason_as_a_comment(
    client, auth_header, db_session, workspace
):
    """The reason travels with the work rather than living in a chat app."""
    ws = await workspace()
    post = await _post(db_session, ws, status=PostStatus.IN_REVIEW)
    await client.post(
        _url(ws["account_id"], post.id, "/request-changes"),
        headers=auth_header(ws["manager"]),
        json={"comment": "Needs a stronger hook."},
    )

    comments = (
        await db_session.execute(
            select(PostComment).where(PostComment.post_id == post.id)
        )
    ).scalars().all()
    assert len(comments) == 1
    assert comments[0].body == "Needs a stronger hook."


async def test_withdraw_returns_a_post_to_draft(
    client, auth_header, db_session, workspace
):
    ws = await workspace()
    post = await _post(db_session, ws, status=PostStatus.APPROVED)
    post.approved_by = ws["manager"].id
    await db_session.flush()

    response = await client.post(
        _url(ws["account_id"], post.id, "/withdraw"), headers=auth_header(ws["editor"])
    )
    assert response.status_code == 200
    assert response.json()["status"] == "draft"
    assert response.json()["approved_by"] is None, (
        "a withdrawn post must not keep a stale approval"
    )


# ---------------------------------------------------------------------------
# The client approval chain
# ---------------------------------------------------------------------------

async def test_manager_approval_stops_at_client_review(
    client, auth_header, db_session, workspace
):
    """The commercially important one: an internal approval must not be able to
    stand in for the customer's."""
    ws = await workspace(approvals=True, client_approval=True)
    post = await _post(db_session, ws, status=PostStatus.IN_REVIEW)

    response = await client.post(
        _url(ws["account_id"], post.id, "/approve"), headers=auth_header(ws["manager"])
    )
    assert response.status_code == 200
    assert response.json()["status"] == "client_review", (
        "with client approval required, a manager's sign-off is not the last word"
    )

    final = await client.post(
        _url(ws["account_id"], post.id, "/approve"), headers=auth_header(ws["client"])
    )
    assert final.json()["status"] == "approved"


async def test_without_client_approval_a_manager_finishes_it(
    client, auth_header, db_session, workspace
):
    ws = await workspace(approvals=True, client_approval=False)
    post = await _post(db_session, ws, status=PostStatus.IN_REVIEW)

    response = await client.post(
        _url(ws["account_id"], post.id, "/approve"), headers=auth_header(ws["manager"])
    )
    assert response.json()["status"] == "approved"


async def test_client_approval_implies_internal_approval(db_session, workspace):
    """Client approval alone would send drafts straight to an external
    reviewer with nobody having looked at them first."""
    from app.services.approvals import settings_for

    ws = await workspace(approvals=False, client_approval=True)
    config = settings_for(ws["account"])
    assert config.client_approval_required is False


# ---------------------------------------------------------------------------
# The publish gate
# ---------------------------------------------------------------------------

async def test_publishing_is_blocked_until_approved_when_required(
    client, auth_header, db_session, workspace, social_account_factory
):
    ws = await workspace(approvals=True)
    sa = await social_account_factory(ws["owner"], ws["account"])
    post = await _post(db_session, ws, status=PostStatus.DRAFT)
    post.target_accounts = [{"social_account_id": str(sa.id)}]
    await db_session.flush()

    blocked = await client.post(
        _url(ws["account_id"], post.id, "/publish"), headers=auth_header(ws["owner"])
    )
    assert blocked.status_code == 409
    assert "approval" in blocked.json()["detail"].lower()

    post.status = PostStatus.APPROVED
    await db_session.flush()
    allowed = await client.post(
        _url(ws["account_id"], post.id, "/publish"), headers=auth_header(ws["owner"])
    )
    assert allowed.status_code == 200


async def test_scheduling_is_gated_too(
    client, auth_header, db_session, workspace, social_account_factory
):
    """A gate on publish but not on schedule is not a gate -- the post just
    goes out later."""
    import urllib.parse
    from datetime import datetime, timedelta, timezone

    ws = await workspace(approvals=True)
    sa = await social_account_factory(ws["owner"], ws["account"])
    post = await _post(db_session, ws, status=PostStatus.DRAFT)
    post.target_accounts = [{"social_account_id": str(sa.id)}]
    await db_session.flush()

    when = urllib.parse.quote(
        (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    )
    response = await client.post(
        _url(ws["account_id"], post.id, f"/schedule?scheduled_at={when}"),
        headers=auth_header(ws["owner"]),
    )
    assert response.status_code == 409


async def test_no_gate_when_the_workspace_has_not_enabled_approvals(
    client, auth_header, db_session, workspace, social_account_factory
):
    """A team with no reviewers must not be blocked by a workflow they never
    turned on."""
    ws = await workspace(approvals=False)
    sa = await social_account_factory(ws["owner"], ws["account"])
    post = await _post(db_session, ws, status=PostStatus.DRAFT)
    post.target_accounts = [{"social_account_id": str(sa.id)}]
    await db_session.flush()

    response = await client.post(
        _url(ws["account_id"], post.id, "/publish"), headers=auth_header(ws["owner"])
    )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# CLIENT visibility
# ---------------------------------------------------------------------------

async def test_a_client_sees_only_their_review_queue(
    client, auth_header, db_session, workspace
):
    """CLIENT holds content.view so they can open the queue. This is what stops
    that becoming "sees every draft in the workspace"."""
    ws = await workspace(approvals=True, client_approval=True)
    for status in (
        PostStatus.DRAFT, PostStatus.IN_REVIEW, PostStatus.CHANGES_REQUESTED,
        PostStatus.CLIENT_REVIEW, PostStatus.APPROVED, PostStatus.PUBLISHED,
    ):
        await _post(db_session, ws, status=status)

    listing = await client.get(
        f"/api/v1/accounts/{ws['account_id']}/posts/", headers=auth_header(ws["client"])
    )
    assert listing.status_code == 200
    seen = {p["status"] for p in listing.json()["items"]}
    assert seen == {"client_review", "approved", "published"}
    assert "draft" not in seen and "in_review" not in seen


async def test_the_client_filter_is_applied_to_the_count_too(
    client, auth_header, db_session, workspace
):
    """Filtering the page but not the total would leak how many drafts exist."""
    ws = await workspace()
    for _ in range(4):
        await _post(db_session, ws, status=PostStatus.DRAFT)
    await _post(db_session, ws, status=PostStatus.CLIENT_REVIEW)

    body = (
        await client.get(
            f"/api/v1/accounts/{ws['account_id']}/posts/",
            headers=auth_header(ws["client"]),
        )
    ).json()
    assert body["total"] == 1


async def test_a_client_cannot_open_a_draft_by_id(
    client, auth_header, db_session, workspace
):
    """The list filter alone would leave every single-post route open to anyone
    who guessed an id or was once sent a link."""
    ws = await workspace()
    draft = await _post(db_session, ws, status=PostStatus.DRAFT)

    response = await client.get(
        _url(ws["account_id"], draft.id), headers=auth_header(ws["client"])
    )
    assert response.status_code == 404, "a client reached a draft directly"


async def test_a_client_cannot_open_the_review_panel_for_a_draft(
    client, auth_header, db_session, workspace
):
    ws = await workspace()
    draft = await _post(db_session, ws, status=PostStatus.DRAFT)

    response = await client.get(
        _url(ws["account_id"], draft.id, "/review"), headers=auth_header(ws["client"])
    )
    assert response.status_code == 404


async def test_an_internal_role_still_sees_everything(
    client, auth_header, db_session, workspace
):
    ws = await workspace()
    for status in (PostStatus.DRAFT, PostStatus.CLIENT_REVIEW):
        await _post(db_session, ws, status=status)

    body = (
        await client.get(
            f"/api/v1/accounts/{ws['account_id']}/posts/",
            headers=auth_header(ws["editor"]),
        )
    ).json()
    assert body["total"] == 2


# ---------------------------------------------------------------------------
# Comments and mentions
# ---------------------------------------------------------------------------

async def test_comment_crud(client, auth_header, db_session, workspace):
    ws = await workspace()
    post = await _post(db_session, ws)
    base = _url(ws["account_id"], post.id, "/comments")
    headers = auth_header(ws["editor"])

    created = await client.post(base, headers=headers, json={"body": "First pass done"})
    assert created.status_code == 201
    comment_id = created.json()["id"]
    assert created.json()["author"]["email"] == ws["editor"].email

    reply = await client.post(
        base, headers=headers, json={"body": "And a reply", "parent_id": comment_id}
    )
    assert reply.json()["parent_id"] == comment_id

    edited = await client.patch(
        f"{base}/{comment_id}", headers=headers, json={"body": "Revised"}
    )
    assert edited.json()["body"] == "Revised"
    assert edited.json()["edited_at"] is not None

    assert (await client.delete(f"{base}/{comment_id}", headers=headers)).status_code == 200
    remaining = (await client.get(base, headers=headers)).json()
    assert comment_id not in [c["id"] for c in remaining]


async def test_only_the_author_edits_their_comment(
    client, auth_header, db_session, workspace
):
    """Editing someone else's words in a review thread would let an objection
    be rewritten by the person it was aimed at."""
    ws = await workspace()
    post = await _post(db_session, ws)
    base = _url(ws["account_id"], post.id, "/comments")

    created = await client.post(
        base, headers=auth_header(ws["manager"]), json={"body": "Please change this"}
    )
    response = await client.patch(
        f"{base}/{created.json()['id']}", headers=auth_header(ws["editor"]),
        json={"body": "Actually it is fine"},
    )
    assert response.status_code == 403


async def test_a_client_can_comment_without_content_create(
    client, auth_header, db_session, workspace
):
    """A reviewer has to be able to say why they are rejecting something."""
    ws = await workspace()
    post = await _post(db_session, ws, status=PostStatus.CLIENT_REVIEW)

    response = await client.post(
        _url(ws["account_id"], post.id, "/comments"),
        headers=auth_header(ws["client"]),
        json={"body": "Can we soften the wording?"},
    )
    assert response.status_code == 201


async def test_mentions_notify_members(client, auth_header, db_session, workspace):
    ws = await workspace()
    post = await _post(db_session, ws)

    response = await client.post(
        _url(ws["account_id"], post.id, "/comments"),
        headers=auth_header(ws["manager"]),
        json={"body": f"Over to you @[{ws['editor'].id}]"},
    )
    assert response.status_code == 201
    assert response.json()["mentions"] == [str(ws["editor"].id)]

    notes = (
        await db_session.execute(
            select(Notification).where(
                Notification.user_id == ws["editor"].id,
                Notification.type == "post.mentioned",
            )
        )
    ).scalars().all()
    assert len(notes) == 1
    assert "mentioned you" in notes[0].message


async def test_mentioning_a_non_member_is_ignored(
    client, auth_header, db_session, workspace, user_factory
):
    """Otherwise mentioning an arbitrary id notifies a stranger -- and tells
    the mentioner that the id belongs to a real account."""
    ws = await workspace()
    outsider = await user_factory()
    post = await _post(db_session, ws)

    response = await client.post(
        _url(ws["account_id"], post.id, "/comments"),
        headers=auth_header(ws["manager"]),
        json={"body": f"Hello @[{outsider.id}]"},
    )
    assert response.status_code == 201
    assert response.json()["mentions"] == []

    notes = (
        await db_session.execute(
            select(Notification).where(Notification.user_id == outsider.id)
        )
    ).scalars().all()
    assert notes == []


async def test_mentioning_yourself_creates_no_notification(
    client, auth_header, db_session, workspace
):
    """Telling someone about their own action is the noise that makes people
    turn notifications off."""
    ws = await workspace()
    post = await _post(db_session, ws)

    await client.post(
        _url(ws["account_id"], post.id, "/comments"),
        headers=auth_header(ws["manager"]),
        json={"body": f"Note to self @[{ws['manager'].id}]"},
    )
    notes = (
        await db_session.execute(
            select(Notification).where(Notification.user_id == ws["manager"].id)
        )
    ).scalars().all()
    assert notes == []


# ---------------------------------------------------------------------------
# Transition notifications and the activity log
# ---------------------------------------------------------------------------

async def test_submitting_notifies_the_approvers(
    client, auth_header, db_session, workspace
):
    """Without this the post sits until someone happens to check the queue."""
    ws = await workspace()
    post = await _post(db_session, ws, author=ws["editor"])

    await client.post(
        _url(ws["account_id"], post.id, "/submit-for-review"),
        headers=auth_header(ws["editor"]),
    )
    recipients = {
        n.user_id
        for n in (
            await db_session.execute(
                select(Notification).where(Notification.type == "post.submit")
            )
        ).scalars().all()
    }
    assert ws["manager"].id in recipients
    assert ws["owner"].id in recipients
    assert ws["client"].id not in recipients, "the client is not an internal reviewer"


async def test_approval_to_client_review_notifies_the_client(
    client, auth_header, db_session, workspace
):
    ws = await workspace(approvals=True, client_approval=True)
    post = await _post(db_session, ws, status=PostStatus.IN_REVIEW, author=ws["editor"])

    await client.post(
        _url(ws["account_id"], post.id, "/approve"), headers=auth_header(ws["manager"])
    )
    recipients = {
        n.user_id
        for n in (
            await db_session.execute(
                select(Notification).where(Notification.type == "post.approve")
            )
        ).scalars().all()
    }
    assert ws["client"].id in recipients
    assert ws["editor"].id in recipients, "the author is waiting on this too"


async def test_transitions_are_written_to_the_activity_log(
    client, auth_header, db_session, workspace
):
    from app.models.audit_log import ActivityLog

    ws = await workspace()
    post = await _post(db_session, ws)
    await client.post(
        _url(ws["account_id"], post.id, "/submit-for-review"),
        headers=auth_header(ws["editor"]),
    )

    entries = (
        await db_session.execute(
            select(ActivityLog).where(ActivityLog.action == "post.submit")
        )
    ).scalars().all()
    assert len(entries) == 1
    assert "draft to in_review" in entries[0].description


# ---------------------------------------------------------------------------
# Review state and assignment
# ---------------------------------------------------------------------------

async def test_review_state_offers_only_permitted_actions(
    client, auth_header, db_session, workspace
):
    """The UI should show what the API will accept, not a button that 403s."""
    ws = await workspace()
    post = await _post(db_session, ws, status=PostStatus.IN_REVIEW)
    url = _url(ws["account_id"], post.id, "/review")

    manager = (await client.get(url, headers=auth_header(ws["manager"]))).json()
    assert set(manager["allowed_actions"]) == {"approve", "request_changes", "withdraw"}

    viewer = (await client.get(url, headers=auth_header(ws["viewer"]))).json()
    assert viewer["allowed_actions"] == []


async def test_assignment_requires_membership(
    client, auth_header, db_session, workspace, user_factory
):
    """Assigning a stranger creates a task nobody can see, and leaks that the
    user id exists."""
    ws = await workspace()
    post = await _post(db_session, ws)
    outsider = await user_factory()

    bad = await client.patch(
        _url(ws["account_id"], post.id, "/assignment"),
        headers=auth_header(ws["manager"]),
        json={"assigned_to": str(outsider.id)},
    )
    assert bad.status_code == 400

    good = await client.patch(
        _url(ws["account_id"], post.id, "/assignment"),
        headers=auth_header(ws["manager"]),
        json={"assigned_to": str(ws["editor"].id)},
    )
    assert good.status_code == 200
    assert good.json()["assigned_to"] == str(ws["editor"].id)


async def test_assignment_notifies_the_assignee(
    client, auth_header, db_session, workspace
):
    ws = await workspace()
    post = await _post(db_session, ws)
    await client.patch(
        _url(ws["account_id"], post.id, "/assignment"),
        headers=auth_header(ws["manager"]),
        json={"assigned_to": str(ws["editor"].id)},
    )
    notes = (
        await db_session.execute(
            select(Notification).where(
                Notification.user_id == ws["editor"].id,
                Notification.type == "post.assigned",
            )
        )
    ).scalars().all()
    assert len(notes) == 1


async def test_comments_cascade_with_the_post(db_session, workspace):
    ws = await workspace()
    post = await _post(db_session, ws)
    db_session.add(
        PostComment(
            id=uuid.uuid4(), post_id=post.id, author_id=ws["owner"].id, body="x"
        )
    )
    await db_session.flush()
    post_id = post.id

    await db_session.delete(post)
    await db_session.flush()
    remaining = (
        await db_session.execute(
            select(PostComment).where(PostComment.post_id == post_id)
        )
    ).scalars().all()
    assert remaining == []
