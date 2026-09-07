"""Organization endpoints — the billing entity above a workspace.

Access is governed by ``OrganizationMember`` and is a separate boundary from
workspace membership: these endpoints expose the subscription, the workspace
list and org settings, never a workspace's content.
"""

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import verify_org_access
from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.account import Account
from app.models.organization import Organization, OrganizationMember, OrgRole
from app.models.plan import Plan
from app.models.team_member import InvitationStatus
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
    OrganizationUsageResponse,
    WorkspaceSummary,
)
from app.services import entitlement_service as ent
from app.services.entitlements import enforce_workspace_limit
from app.services.provisioning import create_workspace

router = APIRouter(prefix="/organizations", tags=["Organizations"])


async def _get_organization(db: AsyncSession, organization_id: uuid.UUID) -> Organization:
    organization = (
        await db.execute(
            select(Organization).where(
                Organization.id == organization_id,
                Organization.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if organization is None:
        # 403 rather than 404 would be wrong here: verify_org_access has already
        # confirmed membership, so the row genuinely does not exist.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        )
    return organization


@router.get("/", response_model=list[OrganizationResponse])
async def list_organizations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Organizations the caller is an accepted member of."""
    rows = await db.execute(
        select(Organization)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.invitation_status == InvitationStatus.ACCEPTED,
            Organization.deleted_at.is_(None),
        )
        .order_by(Organization.created_at)
    )
    return [OrganizationResponse.model_validate(o) for o in rows.scalars().all()]


@router.get("/{organization_id}", response_model=OrganizationResponse)
async def get_organization(
    organization_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await verify_org_access(organization_id, current_user, db)
    return OrganizationResponse.model_validate(
        await _get_organization(db, organization_id)
    )


@router.patch("/{organization_id}", response_model=OrganizationResponse)
async def update_organization(
    organization_id: uuid.UUID,
    payload: OrganizationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Rename an organization. Requires ADMIN or OWNER."""
    await verify_org_access(organization_id, current_user, db, min_role=OrgRole.ADMIN)
    organization = await _get_organization(db, organization_id)

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update"
        )
    for field, value in updates.items():
        setattr(organization, field, value)
    await db.flush()
    await db.refresh(organization)
    return OrganizationResponse.model_validate(organization)


@router.get("/{organization_id}/workspaces", response_model=PaginatedResponse[WorkspaceSummary])
async def list_workspaces(
    organization_id: uuid.UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Every workspace in the organization.

    Organization membership is enough to see that a workspace exists; reading
    its content still requires a TeamMember row for it.
    """
    await verify_org_access(organization_id, current_user, db)

    conditions = [Account.organization_id == organization_id, Account.deleted_at.is_(None)]
    total = (
        await db.execute(select(func.count(Account.id)).where(*conditions))
    ).scalar() or 0
    rows = await db.execute(
        select(Account)
        .where(*conditions)
        .order_by(Account.created_at)
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    return PaginatedResponse[WorkspaceSummary](
        items=[WorkspaceSummary.model_validate(a) for a in rows.scalars().all()],
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total else 0,
    )


@router.post(
    "/{organization_id}/workspaces",
    response_model=WorkspaceSummary,
    status_code=status.HTTP_201_CREATED,
)
async def create_organization_workspace(
    organization_id: uuid.UUID,
    payload: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Add a workspace, subject to the organization's tier allowance."""
    await verify_org_access(organization_id, current_user, db, min_role=OrgRole.ADMIN)
    organization = await _get_organization(db, organization_id)

    await enforce_workspace_limit(db, organization)
    account = await create_workspace(
        db, organization=organization, owner=current_user, name=payload.name
    )
    await db.refresh(account)
    return WorkspaceSummary.model_validate(account)


@router.get("/{organization_id}/usage", response_model=OrganizationUsageResponse)
async def get_organization_usage(
    organization_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Usage against the plan's allowance, feature by feature.

    Any accepted member may read this: knowing how much of the plan is spent is
    not privileged, and hiding it from non-admins is how people hit a cap with
    no warning.
    """
    await verify_org_access(organization_id, current_user, db)
    organization = await _get_organization(db, organization_id)

    plan = (
        await db.execute(
            select(Plan).where(Plan.key == organization.subscription_tier.value)
        )
    ).scalar_one_or_none()

    return OrganizationUsageResponse(
        organization_id=organization.id,
        plan_key=organization.subscription_tier.value,
        plan_name=plan.name if plan else organization.subscription_tier.value.title(),
        period_start=ent.period_start(),
        features=await ent.usage_summary(db, organization),
    )
