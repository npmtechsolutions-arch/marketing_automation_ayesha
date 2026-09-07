"""Schemas for the Organization (billing entity) tier."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class OrganizationUpdate(BaseModel):
    """Only the display name is editable here.

    Tier and Stripe fields are deliberately absent: they are changed through the
    billing endpoints, which go via Stripe. Accepting them here would let an
    admin PATCH themselves onto the Enterprise plan.
    """

    name: str | None = Field(default=None, min_length=1, max_length=255)


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    owner_id: UUID
    subscription_tier: str
    subscription_status: str
    monthly_post_limit: int
    max_team_members: int
    max_platforms: int
    max_workspaces: int
    trial_ends_at: datetime | None = None
    created_at: datetime
    # Stripe identifiers are internal billing plumbing and are never serialized.


class WorkspaceSummary(BaseModel):
    """A workspace as seen from the organization."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    owner_id: UUID
    organization_id: UUID
    created_at: datetime
