"""Pydantic schemas for posts."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator


class PostBase(BaseModel):
    content: str
    title: str | None = None
    hashtags: list[str] | None = None


class PostCreate(PostBase):
    media_urls: list[str] | None = None
    scheduled_at: datetime | None = None
    business_id: UUID | None = None
    strategy_id: UUID | None = None
    campaign_id: UUID | None = None
    target_account_ids: list[UUID] | None = None  # list of social_account IDs to target
    ai_images: list[dict] | None = None  # [{"url": "...", "prompt": "...", "model": "dall-e-3"}]
    digital_assets: list[dict] | None = None  # [{"url": "...", "type": "photo", "filters": {...}}]
    instagram_post_type: str | None = None
    instagram_music_track: str | None = None
    instagram_music_url: str | None = None
    instagram_music_start_offset: int | None = None
    instagram_music_end_offset: int | None = None
    instagram_video_url: str | None = None
    facebook_post_type: str | None = None
    facebook_music_track: str | None = None
    facebook_music_url: str | None = None
    facebook_music_start_offset: int | None = None
    facebook_music_end_offset: int | None = None
    facebook_video_url: str | None = None
    youtube_post_type: str | None = None
    linkedin_post_type: str | None = None
    twitter_post_type: str | None = None


class PostUpdate(BaseModel):
    content: str | None = None
    title: str | None = None
    hashtags: list[str] | None = None
    media_urls: list[str] | None = None
    scheduled_at: datetime | None = None
    status: str | None = None
    target_account_ids: list[UUID] | None = None
    ai_images: list[dict] | None = None
    digital_assets: list[dict] | None = None
    device_previews: dict | None = None
    instagram_post_type: str | None = None
    instagram_music_track: str | None = None
    instagram_music_url: str | None = None
    instagram_music_start_offset: int | None = None
    instagram_music_end_offset: int | None = None
    instagram_video_url: str | None = None
    facebook_post_type: str | None = None
    facebook_music_track: str | None = None
    facebook_music_url: str | None = None
    facebook_music_start_offset: int | None = None
    facebook_music_end_offset: int | None = None
    facebook_video_url: str | None = None
    youtube_post_type: str | None = None
    linkedin_post_type: str | None = None
    twitter_post_type: str | None = None


class PostResponse(PostBase):
    id: UUID
    user_id: UUID
    account_id: UUID
    media_urls: list[str] | None = None
    status: str
    scheduled_at: datetime | None = None
    published_at: datetime | None = None
    ai_generated: bool
    ai_model: str | None = None
    ai_prompt: str | None = None
    ai_cost: float | None = None
    ai_images: list[dict] | None = None
    digital_assets: list[dict] | None = None
    target_accounts: list[dict] | None = None
    posting_results: list[dict] | None = None
    device_previews: dict | None = None
    error_message: str | None = None
    retry_count: int = 0
    created_at: datetime
    updated_at: datetime | None = None
    deleted_at: datetime | None = None
    instagram_post_type: str | None = None
    instagram_music_track: str | None = None
    instagram_music_url: str | None = None
    instagram_music_start_offset: int | None = None
    instagram_music_end_offset: int | None = None
    instagram_video_url: str | None = None
    facebook_post_type: str | None = None
    facebook_music_track: str | None = None
    facebook_music_url: str | None = None
    facebook_music_start_offset: int | None = None
    facebook_music_end_offset: int | None = None
    facebook_video_url: str | None = None
    youtube_post_type: str | None = None
    linkedin_post_type: str | None = None
    twitter_post_type: str | None = None
    performance: dict | None = None


    model_config = ConfigDict(from_attributes=True)

    @field_serializer('status')
    def serialize_status(self, value) -> str:
        """Serialize PostStatus enum to its string value."""
        if hasattr(value, 'value'):
            return value.value
        return str(value)


class PostWithPerformance(PostResponse):
    performances: list[PostPerformanceResponse] = []


# Import here to avoid circular imports; resolved via __future__ annotations
from app.schemas.analytics import PostPerformanceResponse  # noqa: E402, F811

PostWithPerformance.model_rebuild()
