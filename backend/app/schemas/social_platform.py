"""Pydantic schemas for social platforms."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SocialPlatformCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Platform name, e.g. 'Facebook'")
    slug: str | None = Field(None, max_length=100, description="URL-friendly slug; auto-generated from name if omitted")
    icon: str | None = Field(None, max_length=50, description="Icon identifier")
    color: str | None = Field(None, max_length=7, description="Hex color, e.g. '#1877F2'")
    description: str | None = None
    api_config_template: dict | None = None
    base_url: str | None = Field(None, max_length=500)


class SocialPlatformUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    slug: str | None = Field(None, max_length=100)
    icon: str | None = Field(None, max_length=50)
    color: str | None = Field(None, max_length=7)
    description: str | None = None
    api_config_template: dict | None = None
    base_url: str | None = Field(None, max_length=500)
    is_active: bool | None = None
    sort_order: int | None = None


class SocialPlatformResponse(BaseModel):
    id: UUID
    user_id: UUID
    account_id: UUID
    name: str
    slug: str
    icon: str | None = None
    color: str | None = None
    description: str | None = None
    api_config_template: dict | None = None
    base_url: str | None = None
    is_active: bool
    sort_order: int
    social_accounts_count: int = 0
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
