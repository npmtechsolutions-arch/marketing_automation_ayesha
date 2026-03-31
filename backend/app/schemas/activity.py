"""Pydantic schemas for activity logs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ActivityLogResponse(BaseModel):
    id: UUID
    user_id: UUID
    account_id: UUID | None = None
    action: str
    category: str
    description: str
    resource_type: str | None = None
    resource_id: str | None = None
    resource_name: str | None = None
    old_values: dict | None = None
    new_values: dict | None = None
    ip_address: str | None = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActivityStatsResponse(BaseModel):
    actions_per_day: list[dict]  # [{"date": "2026-03-30", "count": 12}, ...]
    most_active_categories: list[dict]  # [{"category": "post", "count": 45}, ...]
    total_actions: int
