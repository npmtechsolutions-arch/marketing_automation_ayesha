from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AnalyticsOverview(BaseModel):
    total_reach: int
    total_engagement: int
    avg_engagement_rate: float
    total_followers_gained: int
    total_posts: int
    period: str
    comparison: dict | None = None


class TopPost(BaseModel):
    post_id: UUID
    content: str
    platform: str
    engagement_rate: float
    total_engagement: int
    published_at: datetime


class PerformanceTrend(BaseModel):
    date: str
    impressions: int
    reach: int
    engagement: int
    followers: int


class PostPerformanceResponse(BaseModel):
    id: UUID
    post_id: UUID
    platform_type: str
    impressions: int
    reach: int
    likes: int
    comments: int
    shares: int
    saves: int
    clicks: int
    engagement_rate: float

    model_config = ConfigDict(from_attributes=True)


class AnalyticsExport(BaseModel):
    format: str = "pdf"
    period: str = "30d"
    platforms: list[str] | None = None
