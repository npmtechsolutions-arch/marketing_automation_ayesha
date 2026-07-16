"""Pydantic schemas for social accounts."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.schemas.social_platform import SocialPlatformResponse


class SocialAccountCreate(BaseModel):
    platform_id: UUID
    account_name: str = Field(..., min_length=1, max_length=200)
    account_handle: str | None = Field(None, max_length=200)
    profile_url: str | None = Field(None, max_length=1000)
    profile_image_url: str | None = Field(None, max_length=1000)
    api_key: str | None = None
    api_secret: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    config: dict | None = None


class SocialAccountUpdate(BaseModel):
    account_name: str | None = Field(None, min_length=1, max_length=200)
    account_handle: str | None = Field(None, max_length=200)
    profile_url: str | None = Field(None, max_length=1000)
    profile_image_url: str | None = Field(None, max_length=1000)
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
    metadata: dict | None = Field(None, validation_alias="metadata_")
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    @computed_field  # type: ignore[misc]
    @property
    def followers_count(self) -> int:
        """Extract follower count from metadata dict."""
        meta = self.metadata
        if meta and isinstance(meta, dict):
            return int(meta.get("followers", 0))
        return 0


class SocialAccountWithPlatform(SocialAccountResponse):
    """Social account response including the parent platform details."""

    platform: SocialPlatformResponse | None = None
