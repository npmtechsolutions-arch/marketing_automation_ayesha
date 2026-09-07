"""Centralised account-level authorization.

Every account-scoped endpoint funnels through :func:`verify_account_access`.
This module is deliberately the *only* place that decides whether a user may
act on an account: the check used to be copy-pasted into each endpoint module,
and every one of those copies had drifted into omitting the
``invitation_status`` filter. Because ``teams.py`` stores an invitation for an
already-registered user as a ``TeamMember`` row with ``user_id`` populated and
``invitation_status = PENDING``, those copies handed a merely *invited* user
full access at their invited role before they ever accepted. Keeping the rule
in one function is what stops that class of bug from coming back.
"""

import uuid
from typing import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.core.permissions import PERMISSIONS, role_has_permission
from app.models.organization import OrganizationMember, OrgRole
from app.models.team_member import InvitationStatus, TeamMember

async def verify_account_access(
    account_id: uuid.UUID,
    user,
    db: AsyncSession,
    *,
    permission: str | None = None,
) -> TeamMember:
    """Verify ``user`` is an *accepted* member of the account, and optionally
    that they meet a minimum role.

    Returns the :class:`TeamMember` row on success; raises 403 otherwise.
    """
    result = await db.execute(
        select(TeamMember).where(
            TeamMember.account_id == account_id,
            TeamMember.user_id == user.id,
            # The check whose absence was the bug: a PENDING (or EXPIRED)
            # invitation is not membership, even though the row already
            # carries the user_id and the intended role.
            TeamMember.invitation_status == InvitationStatus.ACCEPTED,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this account",
        )

    if permission is not None and not role_has_permission(member.role, permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Your role ({member.role.value}) cannot "
                f"{PERMISSIONS.get(permission, permission).lower()}."
            ),
        )
    return member


def require_permission(permission: str) -> Callable:
    """FastAPI dependency factory: membership plus a specific permission.

    Replaces ``require_account_role``/``min_role``. What an endpoint needs is a
    capability -- "may publish" -- not a position in an ordering, and only the
    former survives the introduction of roles that do not rank.
    """

    async def _verify(
        account_id: uuid.UUID,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_active_user),
    ) -> TeamMember:
        return await verify_account_access(
            account_id, current_user, db, permission=permission
        )

    return _verify


# ---------------------------------------------------------------------------
# Organization-level access
#
# A second, INDEPENDENT boundary. Holding an OrganizationMember row grants
# organization-level access -- billing, the workspace list, org settings -- and
# nothing more. Reading a workspace's content still requires a TeamMember row
# for that specific workspace, checked by verify_account_access above.
#
# Keeping them separate is deliberate: an accountant who needs the invoices
# should not thereby gain every client's draft posts.
# ---------------------------------------------------------------------------

ORG_ROLE_HIERARCHY: tuple[OrgRole, ...] = (
    OrgRole.MEMBER,
    OrgRole.ADMIN,
    OrgRole.OWNER,
)

_ORG_ROLE_RANK: dict[OrgRole, int] = {
    role: rank for rank, role in enumerate(ORG_ROLE_HIERARCHY)
}


def _org_rank(role: OrgRole | str) -> int:
    """Privilege rank of an organization role, failing closed on anything unknown."""
    if isinstance(role, str) and not isinstance(role, OrgRole):
        try:
            role = OrgRole(role)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this organization",
            )
    try:
        return _ORG_ROLE_RANK[role]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this organization",
        )


async def verify_org_access(
    organization_id: uuid.UUID,
    user,
    db: AsyncSession,
    *,
    min_role: OrgRole | None = None,
) -> OrganizationMember:
    """Verify ``user`` is an *accepted* member of the organization.

    Mirrors :func:`verify_account_access`, including the ACCEPTED requirement --
    a pending invitation is not membership. That was the bug fixed in Phase 0.3
    and this second membership table must not reintroduce it.

    Returns 403 for an organization that does not exist, exactly as for one the
    user cannot see: a different status would let a caller enumerate them.
    """
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user.id,
            OrganizationMember.invitation_status == InvitationStatus.ACCEPTED,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this organization",
        )

    if min_role is not None and _org_rank(member.role) < _org_rank(min_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires at least {min_role.value} role in this organization",
        )
    return member


def require_org_role(min_role: OrgRole | None = None) -> Callable:
    """FastAPI dependency factory enforcing organization membership and a role."""

    async def _verify(
        organization_id: uuid.UUID,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_active_user),
    ) -> OrganizationMember:
        return await verify_org_access(
            organization_id, current_user, db, min_role=min_role
        )

    return _verify
