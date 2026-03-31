from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PlatformConnect(BaseModel):
    platform_type: str
    redirect_uri: str


class PlatformCallback(BaseModel):
    platform_type: str
    code: str
    state: str | None = None


class PlatformUpdate(BaseModel):
    is_active: bool | None = None
    metadata: dict | None = None


class PlatformResponse(BaseModel):
    id: UUID
    platform_type: str
    account_name: str | None = None
    is_active: bool
    profile_url: str | None = None
    profile_image_url: str | None = None
    last_synced_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
