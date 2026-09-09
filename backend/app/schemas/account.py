from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AccountBase(BaseModel):
    name: str


class AccountCreate(AccountBase):
    pass


class AccountUpdate(BaseModel):
    name: str | None = None
    settings: dict | None = None


class AccountResponse(AccountBase):
    id: UUID
    slug: str
    owner_id: UUID
    # The workspace's billing entity. Subscription tier, limits and Stripe ids
    # are the organization's -- read them from /organizations or /billing, not
    # from a workspace.
    organization_id: UUID
    created_at: datetime

    # The caller's role *in this workspace*. Per-workspace rather than on the
    # user, because one person is an owner here and a viewer there -- a single
    # user.role could only ever be right for one of them.
    #
    # Owners are reported as "owner" although they have no TeamMember row: they
    # are the owner_id. The UI used to read a `role` field that UserResponse
    # never sent and fall back to "Member", so the person who created the
    # workspace was told they were a member of it.
    role: str | None = None

    model_config = ConfigDict(from_attributes=True)
