"""Creating an organization and its first workspace.

This existed in six near-identical copies before: the registration endpoint, the
four Google/Firebase login branches, and ``POST /accounts/``. They had already
drifted (some set the tier explicitly, some relied on column defaults), and every
one of them now needs an Organization created first. One helper instead.
"""

import re
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.organization import Organization, OrganizationMember, OrgRole
from app.models.team_member import InvitationStatus, TeamMember, TeamRole
from app.models.user import User
from app.services.entitlements import apply_tier
from app.models.account import SubscriptionTier


def generate_slug(name: str) -> str:
    """A URL-safe slug with a random suffix.

    Uniqueness is by construction rather than by retry, matching the behaviour
    the endpoints already relied on.
    """
    base = re.sub(r"[^a-z0-9]+", "-", (name or "workspace").lower()).strip("-")
    return f"{base or 'workspace'}-{uuid.uuid4().hex[:8]}"


async def create_workspace(
    db: AsyncSession,
    *,
    organization: Organization,
    owner: User,
    name: str,
) -> Account:
    """Create a workspace in an organization, with its owner membership.

    Does not enforce the workspace cap -- callers that represent a user action
    must call ``entitlements.enforce_workspace_limit`` first. Provisioning a
    brand-new organization deliberately skips that check, since its first
    workspace is always within any tier's allowance.
    """
    account = Account(
        id=uuid.uuid4(),
        name=name,
        slug=generate_slug(name),
        owner_id=owner.id,
        organization_id=organization.id,
    )
    db.add(account)
    await db.flush()

    db.add(
        TeamMember(
            id=uuid.uuid4(),
            user_id=owner.id,
            account_id=account.id,
            role=TeamRole.OWNER,
            invitation_status=InvitationStatus.ACCEPTED,
            accepted_at=datetime.now(timezone.utc),
        )
    )
    await db.flush()
    return account


async def provision_organization_with_workspace(
    db: AsyncSession,
    *,
    user: User,
    organization_name: str | None = None,
    workspace_name: str | None = None,
) -> tuple[Organization, Account]:
    """Give a brand-new user an Organization, a Workspace, and ownership of both.

    The single entry point used by registration and by every OAuth sign-up
    branch, so those paths cannot drift apart again.
    """
    display_name = user.full_name or user.email
    org_name = organization_name or f"{display_name}'s Organization"

    organization = Organization(
        id=uuid.uuid4(),
        name=org_name,
        slug=generate_slug(org_name),
        owner_id=user.id,
    )
    # Sets the tier and every derived limit, including max_workspaces, rather
    # than leaning on column defaults that can drift from TIER_LIMITS.
    apply_tier(organization, SubscriptionTier.FREE)
    db.add(organization)
    await db.flush()

    db.add(
        OrganizationMember(
            id=uuid.uuid4(),
            user_id=user.id,
            organization_id=organization.id,
            role=OrgRole.OWNER,
            invitation_status=InvitationStatus.ACCEPTED,
            accepted_at=datetime.now(timezone.utc),
        )
    )
    await db.flush()

    account = await create_workspace(
        db,
        organization=organization,
        owner=user,
        name=workspace_name or f"{display_name}'s Workspace",
    )
    return organization, account
