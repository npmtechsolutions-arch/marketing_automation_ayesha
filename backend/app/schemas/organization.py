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
    trial_ends_at: datetime | None = None
    created_at: datetime
    # Stripe identifiers are internal billing plumbing and are never serialized.
    #
    # Neither are limits. They used to be copied onto this row and served from
    # here, which meant a client could read a cap that no longer matched what
    # enforcement would do. GET /organizations/{id}/usage is the one place that
    # reports limits, and it resolves them the same way enforcement does.


class WorkspaceSummary(BaseModel):
    """A workspace as seen from the organization."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    owner_id: UUID
    organization_id: UUID
    created_at: datetime


class FeatureUsage(BaseModel):
    """One feature's consumption against the plan's allowance.

    ``limit`` is ``None`` for unlimited, which is why ``unlimited`` is sent
    alongside it -- a client should not have to infer the difference between
    "no cap" and "not sent".
    """

    key: str
    name: str
    description: str | None = None
    unit: str
    metered: bool
    used: int
    limit: int | None = None
    unlimited: bool
    enabled: bool


class OrganizationUsageResponse(BaseModel):
    organization_id: UUID
    plan_key: str
    plan_name: str
    period_start: datetime
    features: list[FeatureUsage]
