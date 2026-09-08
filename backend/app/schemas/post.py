"""Pydantic schemas for posts."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_serializer, model_validator


class PostBase(BaseModel):
    content: str
    title: str | None = None
    hashtags: list[str] | None = None


class _StrictWriteModel(BaseModel):
    """Shared rules for post writes.

    **Unknown fields are refused, not ignored.** Pydantic's default is to drop
    them, so a request naming a field this schema does not have used to return
    200 having stored nothing -- the same failure as the settings writer, one
    level up at the contract. A typo, a renamed field, or a client written
    against a newer version now gets a 422 naming the offending key.

    That leaves one legitimate casualty, which is why the validator below
    exists. ``PostResponse`` returns the targets as ``target_accounts`` (a list
    of objects), while writes take ``target_account_ids`` (a list of ids). Read
    a post, change its text, send it back -- the ordinary way to use an API --
    and the field it just gave you would be rejected. So the response's name is
    accepted as an alias and normalised.
    """

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _accept_response_target_shape(cls, data):
        if not isinstance(data, dict) or "target_accounts" not in data:
            return data

        payload = dict(data)
        targets = payload.pop("target_accounts")

        if payload.get("target_account_ids") is not None:
            # Both given and disagreeing is ambiguous, and guessing which the
            # caller meant is how a post publishes to the wrong account.
            raise ValueError(
                "send either target_account_ids or target_accounts, not both"
            )

        if targets is None:
            payload["target_account_ids"] = None
            return payload

        if not isinstance(targets, list):
            raise ValueError("target_accounts must be a list")

        ids = []
        for entry in targets:
            if isinstance(entry, dict):
                value = entry.get("social_account_id") or entry.get("id")
                if value is None:
                    raise ValueError(
                        "each target_accounts entry needs a social_account_id"
                    )
                ids.append(value)
            else:
                ids.append(entry)
        payload["target_account_ids"] = ids
        return payload


class PostCreate(PostBase, _StrictWriteModel):
    media_urls: list[str] | None = None
    # Library files attached from the media picker. Kept separate from
    # media_urls, which also carries pasted external links -- without the
    # distinction, "is this file still in use?" could only be answered by
    # string-matching URLs, which misses one behind an expired presigned link.
    media_ids: list[UUID] | None = None
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


class PostUpdate(_StrictWriteModel):
    content: str | None = None
    title: str | None = None
    hashtags: list[str] | None = None
    media_urls: list[str] | None = None
    # Library files attached from the media picker. Kept separate from
    # media_urls, which also carries pasted external links -- without the
    # distinction, "is this file still in use?" could only be answered by
    # string-matching URLs, which misses one behind an expired presigned link.
    media_ids: list[UUID] | None = None
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

    # Review workflow. Exposed so the calendar and list views can show an
    # approval badge without a second call per post.
    assigned_to: UUID | None = None
    due_at: datetime | None = None
    approved_by: UUID | None = None
    approved_at: datetime | None = None
    rejection_reason: str | None = None

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
