from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AnalyticsOverview(BaseModel):
    """The dashboard's headline numbers.

    Every measured field is optional, and null means **not measured** rather
    than zero. The endpoint used to coalesce each aggregate to 0, so a
    workspace that had never connected an account was shown "0 reach" and
    "0.00% engagement rate" as though those had been observed -- the exact
    thing the reports and analytics pages were fixed not to do.

    ``total_posts`` stays a plain int because it is a **count**: no posts
    published is a real answer, not a gap in measurement.
    """

    total_reach: int | None = None
    total_engagement: int | None = None
    avg_engagement_rate: float | None = None
    total_followers_gained: int | None = None
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
