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

    model_config = ConfigDict(from_attributes=True)
