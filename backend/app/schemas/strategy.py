from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class StrategyGenerate(BaseModel):
    goal: str
    budget: float | None = None
    platforms: list[str] | None = None
    business_id: UUID


class StrategyUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    platform_mix: dict | None = None
    posting_frequency: dict | None = None


class StrategyResponse(BaseModel):
    id: UUID
    name: str
    goal: str
    platform_mix: dict | None = None
    posting_frequency: dict | None = None
    content_themes: list | None = None
    reasoning: str | None = None
    confidence_score: float | None = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
