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
    subscription_tier: str
    subscription_status: str
    trial_ends_at: datetime | None = None
    monthly_post_limit: int
    max_team_members: int
    max_platforms: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
