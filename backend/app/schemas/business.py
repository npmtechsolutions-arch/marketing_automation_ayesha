from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BusinessBase(BaseModel):
    name: str
    industry: str | None = None
    description: str | None = None
    website: str | None = None


class BusinessCreate(BusinessBase):
    pass


class BusinessUpdate(BaseModel):
    name: str | None = None
    industry: str | None = None
    description: str | None = None
    website: str | None = None
    target_audience: dict | None = None
    brand_voice: dict | None = None
    goals: dict | None = None
    competitors: list[dict] | None = None


class BusinessResponse(BusinessBase):
    id: UUID
    account_id: UUID
    logo_url: str | None = None
    target_audience: dict | None = None
    brand_voice: dict | None = None
    goals: dict | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
