"""The review workflow: who may move a post where, and what happens when they do.

Status used to be set by assignment wherever a handler felt like it. That works
until two endpoints disagree about whether an approved post can go back to
draft, and then the answer depends on which one the user happened to click.
Every transition now goes through :func:`transition`, which is the only code
that writes ``Post.status`` for review purposes.

Two rules are worth stating because they are easy to get backwards:

* **Approval gates publishing only when the workspace asks for it.** A team
  with no reviewers should not be blocked by a workflow they never enabled, so
  the gate is a per-workspace setting rather than a global one.
* **A CLIENT approves; they do not review internally.** The manager's approval
  moves a post to CLIENT_REVIEW when client approval is required, and only the
  client moves it to APPROVED. Collapsing those would let an internal approval
  stand in for the customer's.
"""

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status as http_status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import (
    CONTENT_APPROVE,
    CONTENT_CREATE,
    role_has_permission,
)
from app.models.account import Account
from app.models.post import Post, PostStatus
from app.models.team_member import InvitationStatus, TeamMember, TeamRole
from app.models.user import User

logger = logging.getLogger(__name__)

# Statuses a post can be in while it is still being worked on, as opposed to
# scheduled or already out.
EDITABLE_STATUSES = frozenset(
    {
        PostStatus.DRAFT,
        PostStatus.PREVIEW,
        PostStatus.CHANGES_REQUESTED,
        PostStatus.FAILED,
    }
)

# What a CLIENT may see. An external reviewer needs the queue waiting on them
# and the outcome of what they already approved -- nothing else in the
# workspace. PUBLISHED is included so they can confirm what went live.
CLIENT_VISIBLE_STATUSES = frozenset(
    {PostStatus.CLIENT_REVIEW, PostStatus.APPROVED, PostStatus.PUBLISHED}
)

# Legacy label from before the workflow existed; treated as IN_REVIEW wherever
# an old row still carries it. Postgres cannot drop an enum value.
LEGACY_IN_REVIEW = PostStatus.PENDING_APPROVAL


@dataclass(frozen=True)
class Transition:
    """One legal move, and what it takes to make it."""

    to: PostStatus
    permission: str
    # Roles allowed beyond the permission check. None means "anyone with the
    # permission"; a set narrows it further -- which is how CLIENT is kept from
    # signing off internal review.
    roles: Optional[frozenset] = None
    # Whether a comment must accompany it. "Rejected" with no reason is a
    # message the author has to chase.
    requires_comment: bool = False


# The matrix. Keyed by the action a user takes rather than by target status, so
# an endpoint asks "may this person do this?" rather than reconstructing intent
# from a status pair.
TRANSITIONS: dict[str, dict[PostStatus, Transition]] = {
    "submit": {
        source: Transition(PostStatus.IN_REVIEW, CONTENT_CREATE)
        for source in (
            PostStatus.DRAFT,
            PostStatus.PREVIEW,
            PostStatus.CHANGES_REQUESTED,
            PostStatus.FAILED,
        )
    },
    "approve": {
        # Internal sign-off. Where it lands depends on whether the workspace
        # also wants the client's -- resolved in `approve_target` rather than
        # here, because it is a per-workspace setting, not a fixed edge.
        PostStatus.IN_REVIEW: Transition(
            PostStatus.APPROVED,
            CONTENT_APPROVE,
            roles=frozenset(
                {TeamRole.OWNER, TeamRole.ADMIN, TeamRole.MANAGER}
            ),
        ),
        LEGACY_IN_REVIEW: Transition(
            PostStatus.APPROVED,
            CONTENT_APPROVE,
            roles=frozenset({TeamRole.OWNER, TeamRole.ADMIN, TeamRole.MANAGER}),
        ),
        # The client's sign-off is the only thing that clears CLIENT_REVIEW.
        PostStatus.CLIENT_REVIEW: Transition(
            PostStatus.APPROVED, CONTENT_APPROVE
        ),
    },
    "request_changes": {
        source: Transition(
            PostStatus.CHANGES_REQUESTED, CONTENT_APPROVE, requires_comment=True
        )
        for source in (
            PostStatus.IN_REVIEW,
            LEGACY_IN_REVIEW,
            PostStatus.CLIENT_REVIEW,
            PostStatus.APPROVED,
        )
    },
    # Pulling a post back out of review, e.g. to keep editing it.
    "withdraw": {
        source: Transition(PostStatus.DRAFT, CONTENT_CREATE)
        for source in (
            PostStatus.IN_REVIEW,
            LEGACY_IN_REVIEW,
            PostStatus.CLIENT_REVIEW,
            PostStatus.APPROVED,
        )
    },
}


# ---------------------------------------------------------------------------
# Workspace settings
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ApprovalSettings:
    approvals_required: bool = False
    client_approval_required: bool = False


def settings_for(account: Account) -> ApprovalSettings:
    """Approval settings for a workspace.

    Read from the ``settings`` JSON rather than new columns: they are two
    booleans on a blob that already exists for exactly this kind of
    preference, and a migration per toggle is not a trade worth making.

    Both default to False, so a workspace that never opens the setting keeps
    publishing exactly as it did.
    """
    raw = account.settings or {}
    approvals = bool(raw.get("approvals_required", False))
    return ApprovalSettings(
        approvals_required=approvals,
        # Client approval without internal approval is not a workflow anyone
        # asked for, and would let a draft go straight to an external
        # reviewer. Requiring the former keeps the chain intact.
        client_approval_required=approvals
        and bool(raw.get("client_approval_required", False)),
    )


def approve_target(account: Account, current: PostStatus) -> PostStatus:
    """Where an approval lands.

    A manager approving an internally reviewed post sends it to the client
    when the workspace wants client sign-off; the client's approval is what
    finally reaches APPROVED.
    """
    config = settings_for(account)
    if current is PostStatus.CLIENT_REVIEW:
        return PostStatus.APPROVED
    if config.client_approval_required:
        return PostStatus.CLIENT_REVIEW
    return PostStatus.APPROVED


def requires_approval_to_publish(account: Account) -> bool:
    return settings_for(account).approvals_required


def assert_publishable(account: Account, post: Post) -> None:
    """Refuse to schedule or publish a post the workspace has not approved.

    Enforced here rather than in the two endpoints separately, because a gate
    that exists on publish but not on schedule is not a gate.
    """
    if not requires_approval_to_publish(account):
        return
    if post.status in (
        PostStatus.APPROVED,
        PostStatus.SCHEDULED,
        PostStatus.PUBLISHING,
        PostStatus.PUBLISHED,
        PostStatus.PARTIALLY_PUBLISHED,
    ):
        return
    raise HTTPException(
        status_code=http_status.HTTP_409_CONFLICT,
        detail=(
            "This workspace requires approval before publishing. Submit the "
            "post for review first."
        ),
    )


# ---------------------------------------------------------------------------
# Performing a transition
# ---------------------------------------------------------------------------

def allowed_actions(member: TeamMember, account: Account, post: Post) -> list[str]:
    """Which actions this member may take on this post right now.

    Drives the review panel's buttons, so the UI offers exactly what the server
    will accept rather than showing a button that 403s.
    """
    return [
        action
        for action, sources in TRANSITIONS.items()
        if post.status in sources and _permitted(member, sources[post.status])
    ]


def _permitted(member: TeamMember, rule: Transition) -> bool:
    if not role_has_permission(member.role, rule.permission):
        return False
    return rule.roles is None or member.role in rule.roles


async def transition(
    db: AsyncSession,
    *,
    post: Post,
    account: Account,
    member: TeamMember,
    actor: User,
    action: str,
    comment: Optional[str] = None,
) -> PostStatus:
    """Move a post through the workflow, or refuse with a reason.

    The single writer of ``Post.status`` for review purposes. Returns the new
    status; the caller commits.
    """
    sources = TRANSITIONS.get(action)
    if sources is None:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown review action '{action}'.",
        )

    rule = sources.get(post.status)
    if rule is None:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot {action.replace('_', ' ')} a post that is "
                f"'{post.status.value}'."
            ),
        )

    if not _permitted(member, rule):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail=(
                f"Your role ({member.role.value}) cannot "
                f"{action.replace('_', ' ')} this post."
            ),
        )

    if rule.requires_comment and not (comment or "").strip():
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=(
                "Explain what needs to change -- a rejection with no reason is "
                "one the author has to chase."
            ),
        )

    previous = post.status
    target = (
        approve_target(account, previous) if action == "approve" else rule.to
    )

    post.status = target
    if action == "approve" and target is PostStatus.APPROVED:
        post.approved_by = actor.id
        post.approved_at = datetime.now(timezone.utc)
        post.rejection_reason = None
    elif action == "request_changes":
        post.rejection_reason = (comment or "").strip()
    elif action == "withdraw":
        post.approved_by = None
        post.approved_at = None

    await db.flush()
    logger.info(
        "Post %s: %s -> %s by %s (%s)",
        post.id, previous.value, target.value, actor.email, action,
    )
    return previous


# ---------------------------------------------------------------------------
# Mentions
# ---------------------------------------------------------------------------

# @[uuid] -- an explicit token rather than @name, because names are ambiguous
# and change. The client renders it as a name; the stored form stays stable.
MENTION_PATTERN = re.compile(
    r"@\[([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\]"
)


async def parse_mentions(
    db: AsyncSession, body: str, account_id: uuid.UUID
) -> list[uuid.UUID]:
    """User ids mentioned in a comment, filtered to workspace members.

    Membership is re-checked rather than trusted: without it, mentioning an
    arbitrary user id would notify a stranger and, worse, tell the mentioner
    that the id belongs to a real account.
    """
    found = {uuid.UUID(m) for m in MENTION_PATTERN.findall(body or "")}
    if not found:
        return []

    members = set(
        (
            await db.execute(
                select(TeamMember.user_id).where(
                    TeamMember.account_id == account_id,
                    TeamMember.user_id.in_(found),
                    TeamMember.invitation_status == InvitationStatus.ACCEPTED,
                )
            )
        ).scalars().all()
    )
    ignored = found - members
    if ignored:
        logger.info(
            "Ignoring %d mention(s) of non-members on account %s",
            len(ignored), account_id,
        )
    return sorted(members, key=str)


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

async def notify(
    db: AsyncSession,
    *,
    recipients: set[uuid.UUID],
    account_id: uuid.UUID,
    actor: User,
    post: Post,
    notification_type: str,
    title: str,
    message: str,
) -> int:
    """Create in-app notifications and queue the emails.

    The actor is always removed: telling someone about their own action is
    noise, and it is what makes people turn notifications off.
    """
    from app.models.notification import Notification

    targets = {r for r in recipients if r and r != actor.id}
    if not targets:
        return 0

    users = (
        await db.execute(select(User).where(User.id.in_(targets)))
    ).scalars().all()

    for user in users:
        db.add(
            Notification(
                id=uuid.uuid4(),
                user_id=user.id,
                account_id=account_id,
                type=notification_type,
                title=title,
                message=message,
                action_url=f"/calendar?post={post.id}",
            )
        )
    await db.flush()
    return len(users)


async def review_audience(
    db: AsyncSession, post: Post, account_id: uuid.UUID
) -> set[uuid.UUID]:
    """Who cares that this post moved: its author, its assignee, and anyone who
    has commented on it.

    Commenters are included because someone who asked for a change is waiting
    on the answer; leaving them out means they have to keep checking.
    """
    from app.models.post_comment import PostComment

    audience = {post.user_id}
    if post.assigned_to:
        audience.add(post.assigned_to)

    commenters = (
        await db.execute(
            select(PostComment.author_id).where(
                PostComment.post_id == post.id,
                PostComment.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    audience.update(commenters)
    return {a for a in audience if a}


async def approvers_for(
    db: AsyncSession, account_id: uuid.UUID, *, client: bool = False
) -> set[uuid.UUID]:
    """Members who can act on a post waiting for review.

    ``client=True`` selects the external reviewers; otherwise the internal
    ones. Without this, submitting for review notifies nobody and the post sits
    until someone happens to look at the queue.
    """
    roles = (
        [TeamRole.CLIENT]
        if client
        else [TeamRole.OWNER, TeamRole.ADMIN, TeamRole.MANAGER]
    )
    rows = (
        await db.execute(
            select(TeamMember.user_id).where(
                TeamMember.account_id == account_id,
                TeamMember.role.in_(roles),
                TeamMember.invitation_status == InvitationStatus.ACCEPTED,
                TeamMember.user_id.is_not(None),
            )
        )
    ).scalars().all()
    return set(rows)


def visible_status_filter(member: TeamMember) -> Optional[frozenset]:
    """Statuses this member may see, or None for "everything".

    A CLIENT is an external reviewer: content.view lets them open the approval
    queue, and this is what stops it also exposing every draft, internal note
    and unpublished idea in the workspace.
    """
    from app.core.permissions import restricts_content_to_approvals

    if restricts_content_to_approvals(member.role):
        return CLIENT_VISIBLE_STATUSES
    return None
