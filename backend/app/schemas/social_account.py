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
    # OAuth/API credentials are populated from the ORM (so computed flags below
    # can see them) but are NEVER serialized back to clients. Returning them
    # let any account member — including a read-only VIEWER — exfiltrate every
    # connected platform's tokens.
    api_key: str | None = Field(None, exclude=True)
    api_secret: str | None = Field(None, exclude=True)
    access_token: str | None = Field(None, exclude=True)
    refresh_token: str | None = Field(None, exclude=True)
    token_expires_at: datetime | None = None
    config: dict | None = None
    # Connection health, so the accounts page can badge a dying token before
    # a scheduled post fails on it.
    health: str = "unknown"
    health_detail: str | None = None
    last_checked_at: datetime | None = None
    health_changed_at: datetime | None = None

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
        """Extract follower / subscriber / connection count from metadata dict."""
        meta = self.metadata
        if meta and isinstance(meta, dict):
            for key in ("followers", "followers_count", "subscriberCount", "subscribers", "subscriber_count", "connections", "fan_count"):
                val = meta.get(key)
                if val is not None:
                    try:
                        return int(val)
                    except (ValueError, TypeError):
                        pass
        return 0

    @computed_field  # type: ignore[misc]
    @property
    def has_credentials(self) -> bool:
        """Whether the account has stored credentials, without exposing them."""
        return bool(self.access_token or self.refresh_token or self.api_key)


class SocialAccountWithPlatform(SocialAccountResponse):
    """Social account response including the parent platform details."""

    platform: SocialPlatformResponse | None = None


class SocialAccountCapabilities(BaseModel):
    """What the platform behind a connected account will accept.

    Served so the composer can validate before a user spends effort on a post
    the platform will reject. Its character counter is currently a hardcoded
    2,200 for every platform, so someone targeting X is told 2,200 is fine and
    finds out at publish time that the limit is 280.

    ``None`` on a numeric field means "no limit" -- not "unknown" and not zero.
    """

    social_account_id: UUID
    platform_slug: str
    platform_name: str

    supports_images: bool
    supports_video: bool
    # True where the platform publishes video and nothing else (TikTok), so
    # the composer can say "attach a video" instead of letting a caption-only
    # post reach publish and fail there.
    requires_video: bool = False
    supports_carousel: bool
    supports_link_posts: bool
    supports_comments_api: bool
    supports_dm_api: bool

    max_chars: int | None = None
    max_images: int
    max_video_seconds: int | None = None
    max_video_bytes: int | None = None
