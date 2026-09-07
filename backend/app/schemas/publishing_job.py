"""Schemas for publishing jobs and their logs."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PublishingLogEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    level: str
    message: str
    # Whatever the platform sent back. This is the field someone actually needs
    # when a customer says their post did not go out.
    platform_response: dict | None = None
    created_at: datetime


class PublishingJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    post_id: UUID
    social_account_id: UUID
    # Denormalised for the UI, which shows results per platform and should not
    # have to resolve the account itself.
    platform_slug: str | None = None
    account_name: str | None = None

    status: str
    run_at: datetime
    attempts: int
    max_attempts: int
    attempts_remaining: int
    last_error: str | None = None
    claimed_by: str | None = None
    claimed_at: datetime | None = None
    manual_required: bool = False
    external_post_id: str | None = None
    post_url: str | None = None
    created_at: datetime
    updated_at: datetime | None = None

    logs: list[PublishingLogEntry] = []


class PublishingJobList(BaseModel):
    post_id: UUID
    post_status: str
    jobs: list[PublishingJobResponse] = []
