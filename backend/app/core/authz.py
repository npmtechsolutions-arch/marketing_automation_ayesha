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
from app.models.team_member import InvitationStatus, TeamMember, TeamRole

# Account roles in ascending order of privilege. A role satisfies ``min_role``
# when its index here is >= the index of the required role.
ROLE_HIERARCHY: tuple[TeamRole, ...] = (
    TeamRole.VIEWER,
    TeamRole.EDITOR,
    TeamRole.MANAGER,
    TeamRole.ADMIN,
    TeamRole.OWNER,
)

_ROLE_RANK: dict[TeamRole, int] = {role: rank for rank, role in enumerate(ROLE_HIERARCHY)}


def _rank(role: TeamRole | str) -> int:
    """Return the privilege rank of ``role``, failing closed on anything unknown.

    A role we cannot rank must never satisfy a minimum-role requirement, so an
    unrecognised value raises 403 rather than bubbling up a ValueError as a 500.
    """
    if isinstance(role, str) and not isinstance(role, TeamRole):
        try:
            role = TeamRole(role)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this account",
            )
    try:
        return _ROLE_RANK[role]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this account",
        )


async def verify_account_access(
    account_id: uuid.UUID,
    user,
    db: AsyncSession,
    *,
    min_role: TeamRole | None = None,
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

    if min_role is not None and _rank(member.role) < _rank(min_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires at least {min_role.value} role",
        )
    return member


def require_account_role(min_role: TeamRole | None = None) -> Callable:
    """FastAPI dependency factory enforcing account membership and a minimum role.

    ``account_id`` is resolved from the path (the account-scoped routers are
    mounted under ``/api/v1/accounts/{account_id}/...``), so an endpoint can
    simply declare::

        member: TeamMember = Depends(require_account_role(TeamRole.EDITOR))
    """

    async def _verify(
        account_id: uuid.UUID,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_active_user),
    ) -> TeamMember:
        return await verify_account_access(
            account_id, current_user, db, min_role=min_role
        )

    return _verify
