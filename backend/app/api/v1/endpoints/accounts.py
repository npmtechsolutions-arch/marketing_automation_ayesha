"""Account management endpoints."""

import math
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.account import Account
from app.models.organization import Organization, OrganizationMember
from app.models.team_member import InvitationStatus, TeamMember, TeamRole
from app.models.user import User
from app.schemas.account import AccountCreate, AccountResponse, AccountUpdate
from app.services.entitlements import enforce_workspace_limit
from app.services.provisioning import create_workspace
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/accounts", tags=["Accounts"])


def _generate_slug(name: str) -> str:
    """Generate a URL-safe slug from a name."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"{slug}-{uuid.uuid4().hex[:8]}"


async def _default_organization_for(db: AsyncSession, user: User) -> Organization:
    """The organization to create a workspace in when none was named.

    Prefers one the user owns, then any they are an accepted member of. A user
    with no organization at all cannot reach this (registration provisions one),
    so its absence is a 404 rather than an implicit create.
    """
    owned = (
        await db.execute(
            select(Organization)
            .join(
                OrganizationMember,
                OrganizationMember.organization_id == Organization.id,
            )
            .where(
                OrganizationMember.user_id == user.id,
                OrganizationMember.invitation_status == InvitationStatus.ACCEPTED,
                Organization.deleted_at.is_(None),
            )
            .order_by(
                (Organization.owner_id == user.id).desc(), Organization.created_at
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if owned is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You do not belong to an organization",
        )
    return owned


async def _get_member_or_403(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
) -> TeamMember:
    """Return the team membership or raise 403."""
    result = await db.execute(
        select(TeamMember).where(
            TeamMember.user_id == user_id,
            TeamMember.account_id == account_id,
            TeamMember.invitation_status == InvitationStatus.ACCEPTED,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this account",
        )
    return member


@router.get("/", response_model=PaginatedResponse[AccountResponse])
async def list_accounts(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all accounts the current user is a member of."""
    # Base query: accounts where the user has an accepted membership
    base_filter = (
        select(Account.id)
        .join(TeamMember, TeamMember.account_id == Account.id)
        .where(
            TeamMember.user_id == current_user.id,
            TeamMember.invitation_status == InvitationStatus.ACCEPTED,
            Account.deleted_at.is_(None),
        )
    )

    # Total count
    count_query = select(func.count()).select_from(base_filter.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Fetch page
    accounts_query = (
        select(Account)
        .where(
            Account.id.in_(base_filter),
            Account.deleted_at.is_(None),
        )
        .order_by(Account.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(accounts_query)
    accounts = result.scalars().all()

    # One query for every membership on this page rather than one per row.
    memberships = {
        row.account_id: row.role
        for row in (
            await db.execute(
                select(TeamMember.account_id, TeamMember.role).where(
                    TeamMember.user_id == current_user.id,
                    TeamMember.account_id.in_([a.id for a in accounts] or [None]),
                )
            )
        ).all()
    }

    def _role(account: Account) -> str | None:
        """The caller's role in this workspace.

        Read from TeamMember alone. An owner has one with role OWNER --
        provisioning creates it -- and this endpoint only returns accounts
        where the caller has an accepted membership, so an owner without a row
        would not appear here at all. An extra `owner_id == current_user.id`
        branch looked prudent and was unreachable; no test could distinguish
        it, so it is not here.
        """
        role = memberships.get(account.id)
        return role.value if hasattr(role, "value") else role

    return PaginatedResponse[AccountResponse](
        items=[
            AccountResponse.model_validate(a).model_copy(update={"role": _role(a)})
            for a in accounts
        ],
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total else 0,
    )


@router.post(
    "/",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_account(
    payload: AccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a workspace in the caller's organization.

    Delegates to the organization-scoped creation path so the tier's workspace
    cap applies here too. Before organizations existed this endpoint created
    unlimited free workspaces, each with its own subscription -- leaving it
    unguarded would be a way around the cap.

    Callers who belong to several organizations should use
    ``POST /organizations/{organization_id}/workspaces`` to say which one.
    """
    organization = await _default_organization_for(db, current_user)
    await enforce_workspace_limit(db, organization)
    account = await create_workspace(
        db, organization=organization, owner=current_user, name=payload.name
    )
    await db.refresh(account)

    return AccountResponse.model_validate(account)


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get account details. The current user must be a member."""
    await _get_member_or_403(db, current_user.id, account_id)

    result = await db.execute(
        select(Account).where(Account.id == account_id, Account.deleted_at.is_(None))
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    return AccountResponse.model_validate(account)


@router.put("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: uuid.UUID,
    payload: AccountUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update account details. Only owners and admins can update."""
    member = await _get_member_or_403(db, current_user.id, account_id)

    if member.role not in (TeamRole.OWNER, TeamRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can update account settings",
        )

    result = await db.execute(
        select(Account).where(Account.id == account_id, Account.deleted_at.is_(None))
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    for field, value in update_data.items():
        setattr(account, field, value)

    await db.flush()
    await db.refresh(account)

    return AccountResponse.model_validate(account)


@router.delete("/{account_id}", response_model=dict)
async def delete_account(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Soft-delete an account. Only the owner can delete."""
    member = await _get_member_or_403(db, current_user.id, account_id)

    if member.role != TeamRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the account owner can delete the account",
        )

    result = await db.execute(
        select(Account).where(Account.id == account_id, Account.deleted_at.is_(None))
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    account.deleted_at = datetime.now(timezone.utc)
    await db.flush()

    return {"message": "Account has been deleted"}
