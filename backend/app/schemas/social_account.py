"""Pydantic schemas for social accounts."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.social_platform import SocialPlatformResponse


class SocialAccountCreate(BaseModel):
    platform_id: UUID
    account_name: str = Field(..., min_length=1, max_length=200)
    account_handle: str | None = Field(None, max_length=200)
    profile_url: str | None = Field(None, max_length=500)
    profile_image_url: str | None = Field(None, max_length=500)
    api_key: str | None = None
    api_secret: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    config: dict | None = None


class SocialAccountUpdate(BaseModel):
    account_name: str | None = Field(None, min_length=1, max_length=200)
    account_handle: str | None = Field(None, max_length=200)
    profile_url: str | None = Field(None, max_length=500)
    profile_image_url: str | None = Field(None, max_length=500)
    api_key: str | None = None
    api_secret: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    config: dict | None = None
    is_active: bool | None = None


class SocialAccountResponse(BaseModel):
    id: UUID
    user_id: UUID
    account_id: UUID
    platform_id: UUID
    account_name: str
    account_handle: str | None = None
    profile_url: str | None = None
    profile_image_url: str | None = None
    api_key: str | None = None
    # api_secret is intentionally excluded for security
    access_token: str | None = None
    refresh_token: str | None = None
    token_expires_at: datetime | None = None
    config: dict | None = None
    is_active: bool
    is_verified: bool
    last_verified_at: datetime | None = None
    last_posted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class SocialAccountWithPlatform(SocialAccountResponse):
    """Social account response including the parent platform details."""

    platform: SocialPlatformResponse | None = None
