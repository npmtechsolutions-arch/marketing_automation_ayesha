"""Team management endpoints."""

import math
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.account import Account
from app.models.team_member import InvitationStatus, TeamMember, TeamRole
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.team import TeamInvite, TeamMemberResponse, TeamMemberUpdate

router = APIRouter(
    prefix="/accounts/{account_id}/team",
    tags=["Team Management"],
)


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


async def _require_admin(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
) -> TeamMember:
    """Require the user to be an owner or admin of the account."""
    member = await _get_member_or_403(db, user_id, account_id)
    if member.role not in (TeamRole.OWNER, TeamRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can manage team members",
        )
    return member


@router.get("/", response_model=PaginatedResponse[TeamMemberResponse])
async def list_team_members(
    account_id: uuid.UUID,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all team members for an account."""
    await _get_member_or_403(db, current_user.id, account_id)

    # Count
    count_query = select(func.count()).where(TeamMember.account_id == account_id)
    total = (await db.execute(count_query)).scalar() or 0

    # Fetch with user relationship
    members_query = (
        select(TeamMember)
        .options(selectinload(TeamMember.user))
        .where(TeamMember.account_id == account_id)
        .order_by(TeamMember.created_at.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(members_query)
    members = result.scalars().all()

    return PaginatedResponse[TeamMemberResponse](
        items=[TeamMemberResponse.model_validate(m) for m in members],
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total else 0,
    )


@router.post(
    "/invite",
    response_model=TeamMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_team_member(
    account_id: uuid.UUID,
    payload: TeamInvite,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Invite a new member to the account by email.

    Creates a pending TeamMember record with an invitation token.
    """
    await _require_admin(db, current_user.id, account_id)

    # Verify the account exists
    acct_result = await db.execute(
        select(Account).where(Account.id == account_id, Account.deleted_at.is_(None))
    )
    account = acct_result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    # Check team member limit
    member_count_result = await db.execute(
        select(func.count()).where(TeamMember.account_id == account_id)
    )
    member_count = member_count_result.scalar() or 0
    if member_count >= account.max_team_members:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Team member limit reached ({account.max_team_members}). "
            "Upgrade your plan to add more members.",
        )

    # Check for existing membership or pending invite
    existing_result = await db.execute(
        select(TeamMember).where(
            TeamMember.account_id == account_id,
            TeamMember.invitation_email == payload.email,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An invitation for this email already exists",
        )

    # Also check if a user with this email is already a member
    user_result = await db.execute(select(User).where(User.email == payload.email))
    invited_user = user_result.scalar_one_or_none()

    if invited_user is not None:
        existing_user_member = await db.execute(
            select(TeamMember).where(
                TeamMember.account_id == account_id,
                TeamMember.user_id == invited_user.id,
            )
        )
        if existing_user_member.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This user is already a member of this account",
            )

    invitation_token = secrets.token_urlsafe(48)
    role_enum = TeamRole(payload.role)

    team_member = TeamMember(
        id=uuid.uuid4(),
        user_id=invited_user.id if invited_user else None,
        account_id=account_id,
        role=role_enum,
        invitation_email=payload.email,
        invitation_token=invitation_token,
        invitation_status=InvitationStatus.PENDING,
        invited_by=current_user.id,
    )
    db.add(team_member)
    await db.flush()
    await db.refresh(team_member)

    # TODO: Send invitation email with the token

    return TeamMemberResponse.model_validate(team_member)


@router.put("/{member_id}", response_model=TeamMemberResponse)
async def update_team_member_role(
    account_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: TeamMemberUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update a team member's role. Requires owner or admin role."""
    actor = await _require_admin(db, current_user.id, account_id)

    result = await db.execute(
        select(TeamMember)
        .options(selectinload(TeamMember.user))
        .where(
            TeamMember.id == member_id,
            TeamMember.account_id == account_id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team member not found",
        )

    # Prevent changing the owner's role unless you are the owner
    if member.role == TeamRole.OWNER and actor.role != TeamRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can change the owner's role",
        )

    # Prevent promoting to owner (ownership transfer is a separate flow)
    if payload.role == TeamRole.OWNER.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot promote to owner via this endpoint",
        )

    member.role = TeamRole(payload.role)
    await db.flush()
    await db.refresh(member)

    return TeamMemberResponse.model_validate(member)


@router.delete("/{member_id}", response_model=MessageResponse)
async def remove_team_member(
    account_id: uuid.UUID,
    member_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Remove a team member from the account. Requires owner or admin role."""
    actor = await _require_admin(db, current_user.id, account_id)

    result = await db.execute(
        select(TeamMember).where(
            TeamMember.id == member_id,
            TeamMember.account_id == account_id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team member not found",
        )

    # Cannot remove the account owner
    if member.role == TeamRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the account owner",
        )

    # Admins cannot remove other admins, only owners can
    if member.role == TeamRole.ADMIN and actor.role != TeamRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can remove an admin",
        )

    await db.delete(member)
    await db.flush()

    return MessageResponse(message="Team member removed")


@router.post("/accept-invite", response_model=TeamMemberResponse)
async def accept_invitation(
    account_id: uuid.UUID,
    token: str = Query(..., description="Invitation token"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Accept a team invitation using the invitation token."""
    result = await db.execute(
        select(TeamMember).where(
            TeamMember.account_id == account_id,
            TeamMember.invitation_token == token,
            TeamMember.invitation_status == InvitationStatus.PENDING,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired invitation token",
        )

    # Verify the email matches the current user
    if member.invitation_email and member.invitation_email != current_user.email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This invitation was sent to a different email address",
        )

    member.user_id = current_user.id
    member.invitation_status = InvitationStatus.ACCEPTED
    member.invitation_token = None
    member.accepted_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(member)

    return TeamMemberResponse.model_validate(member)
