from uuid import UUID

from pydantic import BaseModel


class AIContentGenerate(BaseModel):
    prompt: str
    platforms: list[str]
    tone: str | None = "professional"
    include_image: bool = False
    business_id: UUID | None = None


class AIContentResponse(BaseModel):
    content: str
    hashtags: list[str]
    image_url: str | None = None
    platform_variations: dict | None = None
    generation_id: UUID


class AITopicSuggestion(BaseModel):
    topics: list[dict]  # Each dict contains: title, description, platforms, estimated_engagement
