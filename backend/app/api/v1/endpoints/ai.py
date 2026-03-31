"""AI content generation endpoints."""

import json
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.ai_generation import AIGeneration, AIGenerationStatus, GenerationType
from app.models.business import Business
from app.models.team_member import TeamMember, TeamRole
from app.schemas.ai import AIContentGenerate, AIContentResponse, AITopicSuggestion

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _verify_account_access(
    account_id: uuid.UUID, user, db: AsyncSession
) -> TeamMember:
    result = await db.execute(
        select(TeamMember).where(
            TeamMember.account_id == account_id,
            TeamMember.user_id == user.id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this account",
        )
    return member


async def _get_business(business_id: uuid.UUID, account_id: uuid.UUID, db: AsyncSession) -> Business | None:
    if not business_id:
        return None
    result = await db.execute(
        select(Business).where(Business.id == business_id, Business.account_id == account_id)
    )
    return result.scalar_one_or_none()


def _mock_content_response(prompt: str, platforms: list[str], tone: str) -> dict:
    """Return a mock AI response when no OpenAI key is configured."""
    platform_variations = {}
    for p in platforms:
        platform_variations[p] = f"[{p.upper()}] {prompt[:120]}... #marketing #ai"
    return {
        "content": f"Here is AI-generated content for: {prompt}\n\nThis is a mock response because OPENAI_API_KEY is not configured.",
        "hashtags": ["#marketing", "#socialmedia", "#growth", "#ai"],
        "image_url": None,
        "platform_variations": platform_variations,
    }


async def _call_openai(prompt: str, system_prompt: str, model: str = "gpt-4o") -> tuple[str, int, int]:
    """Call OpenAI and return (response_text, input_tokens, output_tokens)."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    completion = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=0.8,
        max_tokens=2000,
    )
    text = completion.choices[0].message.content or ""
    usage = completion.usage
    return text, usage.prompt_tokens if usage else 0, usage.completion_tokens if usage else 0


# ---------------------------------------------------------------------------
# Request / Response extras
# ---------------------------------------------------------------------------

class RegenerateImageRequest(BaseModel):
    content: str
    style: str | None = "modern"


class RegenerateImageResponse(BaseModel):
    image_url: str
    generation_id: uuid.UUID


class TopicSuggestRequest(BaseModel):
    business_id: uuid.UUID
    count: int = 5


class StrategyGenerateRequest(BaseModel):
    business_id: uuid.UUID
    goals: list[str]
    platforms: list[str]
    budget: float | None = None
    timeframe: str = "30 days"


class StrategyGenerateResponse(BaseModel):
    strategy_text: str
    recommended_platforms: list[str]
    posting_schedule: dict
    content_themes: list[str]
    generation_id: uuid.UUID


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/generate-content", response_model=AIContentResponse)
async def generate_content(
    account_id: uuid.UUID,
    body: AIContentGenerate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Generate AI-powered social media content.

    Uses OpenAI to create platform-specific content with hashtags.
    Falls back to a mock response if OPENAI_API_KEY is not set.
    """
    await _verify_account_access(account_id, current_user, db)

    business = await _get_business(body.business_id, account_id, db) if body.business_id else None
    business_context = ""
    if business:
        business_context = (
            f"\nBusiness: {business.name}"
            f"\nIndustry: {business.industry or 'N/A'}"
            f"\nDescription: {business.description or 'N/A'}"
        )

    system_prompt = (
        "You are a social media marketing expert. Generate engaging content for the given platforms. "
        f"Tone: {body.tone or 'professional'}. {business_context}\n"
        "Return ONLY valid JSON with keys: content (string), hashtags (list of strings), "
        "platform_variations (object mapping platform name to tailored version)."
    )

    # Log generation
    gen = AIGeneration(
        user_id=current_user.id,
        account_id=account_id,
        generation_type=GenerationType.CONTENT,
        provider="openai",
        model="gpt-4o",
        prompt=body.prompt,
        status=AIGenerationStatus.PENDING,
    )
    db.add(gen)
    await db.flush()

    start = time.time()

    if not settings.OPENAI_API_KEY:
        mock = _mock_content_response(body.prompt, body.platforms, body.tone or "professional")
        gen.response = json.dumps(mock)
        gen.status = AIGenerationStatus.COMPLETED
        gen.provider = "mock"
        gen.duration_ms = int((time.time() - start) * 1000)
        await db.flush()
        await db.refresh(gen)
        return AIContentResponse(
            content=mock["content"],
            hashtags=mock["hashtags"],
            image_url=mock["image_url"],
            platform_variations=mock["platform_variations"],
            generation_id=gen.id,
        )

    try:
        user_prompt = f"Create social media content for: {body.prompt}\nPlatforms: {', '.join(body.platforms)}"
        raw_text, tokens_in, tokens_out = await _call_openai(user_prompt, system_prompt)
        gen.tokens_input = tokens_in
        gen.tokens_output = tokens_out
        gen.duration_ms = int((time.time() - start) * 1000)

        # Attempt to parse JSON from AI response
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            parsed = {
                "content": raw_text,
                "hashtags": [],
                "platform_variations": None,
            }

        gen.response = raw_text
        gen.status = AIGenerationStatus.COMPLETED
        await db.flush()
        await db.refresh(gen)

        return AIContentResponse(
            content=parsed.get("content", raw_text),
            hashtags=parsed.get("hashtags", []),
            image_url=None,
            platform_variations=parsed.get("platform_variations"),
            generation_id=gen.id,
        )

    except Exception as exc:
        gen.status = AIGenerationStatus.FAILED
        gen.error_message = str(exc)[:500]
        gen.duration_ms = int((time.time() - start) * 1000)
        await db.flush()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI generation failed: {exc}",
        )


@router.post("/regenerate-image", response_model=RegenerateImageResponse)
async def regenerate_image(
    account_id: uuid.UUID,
    body: RegenerateImageRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Generate a new image for given content using DALL-E (or mock)."""
    await _verify_account_access(account_id, current_user, db)

    gen = AIGeneration(
        user_id=current_user.id,
        account_id=account_id,
        generation_type=GenerationType.IMAGE,
        provider="openai",
        model="dall-e-3",
        prompt=body.content[:500],
        status=AIGenerationStatus.PENDING,
    )
    db.add(gen)
    await db.flush()

    if not settings.OPENAI_API_KEY:
        gen.status = AIGenerationStatus.COMPLETED
        gen.provider = "mock"
        gen.response = "https://placehold.co/1024x1024/png?text=AI+Generated+Image"
        await db.flush()
        await db.refresh(gen)
        return RegenerateImageResponse(
            image_url=gen.response,
            generation_id=gen.id,
        )

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        result = await client.images.generate(
            model="dall-e-3",
            prompt=f"Social media marketing image: {body.content[:500]}. Style: {body.style}",
            n=1,
            size="1024x1024",
        )
        image_url = result.data[0].url or ""
        gen.response = image_url
        gen.status = AIGenerationStatus.COMPLETED
        await db.flush()
        await db.refresh(gen)
        return RegenerateImageResponse(image_url=image_url, generation_id=gen.id)

    except Exception as exc:
        gen.status = AIGenerationStatus.FAILED
        gen.error_message = str(exc)[:500]
        await db.flush()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Image generation failed: {exc}",
        )


@router.post("/suggest-topics", response_model=AITopicSuggestion)
async def suggest_topics(
    account_id: uuid.UUID,
    body: TopicSuggestRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """AI-generated topic suggestions based on the business profile."""
    await _verify_account_access(account_id, current_user, db)

    business = await _get_business(body.business_id, account_id, db)
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")

    gen = AIGeneration(
        user_id=current_user.id,
        account_id=account_id,
        generation_type=GenerationType.CONTENT,
        provider="openai",
        model="gpt-4o",
        prompt=f"Suggest {body.count} topics for {business.name}",
        status=AIGenerationStatus.PENDING,
    )
    db.add(gen)
    await db.flush()

    if not settings.OPENAI_API_KEY:
        mock_topics = [
            {
                "title": f"Topic {i+1} for {business.name}",
                "description": f"Engaging content idea #{i+1} about {business.industry or 'your industry'}",
                "platforms": ["instagram", "facebook"],
                "estimated_engagement": "high" if i < 2 else "medium",
            }
            for i in range(body.count)
        ]
        gen.status = AIGenerationStatus.COMPLETED
        gen.provider = "mock"
        gen.response = json.dumps(mock_topics)
        await db.flush()
        return AITopicSuggestion(topics=mock_topics)

    try:
        system_prompt = (
            "You are a social media strategist. Suggest engaging content topics. "
            "Return ONLY valid JSON: a list of objects with keys: title, description, platforms (list), estimated_engagement."
        )
        user_prompt = (
            f"Suggest {body.count} content topics for:\n"
            f"Business: {business.name}\n"
            f"Industry: {business.industry or 'general'}\n"
            f"Description: {business.description or 'N/A'}\n"
            f"Target audience: {json.dumps(business.target_audience) if business.target_audience else 'general'}"
        )
        raw_text, tokens_in, tokens_out = await _call_openai(user_prompt, system_prompt)
        gen.tokens_input = tokens_in
        gen.tokens_output = tokens_out
        gen.response = raw_text
        gen.status = AIGenerationStatus.COMPLETED
        await db.flush()

        try:
            topics = json.loads(raw_text)
            if isinstance(topics, dict) and "topics" in topics:
                topics = topics["topics"]
        except json.JSONDecodeError:
            topics = [{"title": "AI Response", "description": raw_text, "platforms": [], "estimated_engagement": "unknown"}]

        return AITopicSuggestion(topics=topics)

    except Exception as exc:
        gen.status = AIGenerationStatus.FAILED
        gen.error_message = str(exc)[:500]
        await db.flush()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI generation failed: {exc}")


@router.post("/generate-strategy", response_model=StrategyGenerateResponse)
async def generate_strategy(
    account_id: uuid.UUID,
    body: StrategyGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Generate a comprehensive marketing strategy using AI."""
    await _verify_account_access(account_id, current_user, db)

    business = await _get_business(body.business_id, account_id, db)
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")

    gen = AIGeneration(
        user_id=current_user.id,
        account_id=account_id,
        generation_type=GenerationType.STRATEGY,
        provider="openai",
        model="gpt-4o",
        prompt=f"Generate strategy for {business.name}, goals: {body.goals}",
        status=AIGenerationStatus.PENDING,
    )
    db.add(gen)
    await db.flush()

    if not settings.OPENAI_API_KEY:
        mock = {
            "strategy_text": (
                f"Marketing Strategy for {business.name}\n\n"
                f"Goals: {', '.join(body.goals)}\n"
                f"Budget: ${body.budget or 0}/month\n"
                f"Timeframe: {body.timeframe}\n\n"
                "This is a mock strategy. Configure OPENAI_API_KEY for real AI generation."
            ),
            "recommended_platforms": body.platforms or ["instagram", "facebook"],
            "posting_schedule": {
                "monday": 2, "tuesday": 1, "wednesday": 2,
                "thursday": 1, "friday": 2, "saturday": 1, "sunday": 0,
            },
            "content_themes": ["brand awareness", "customer engagement", "product showcase", "behind the scenes"],
        }
        gen.status = AIGenerationStatus.COMPLETED
        gen.provider = "mock"
        gen.response = json.dumps(mock)
        await db.flush()
        await db.refresh(gen)
        return StrategyGenerateResponse(**mock, generation_id=gen.id)

    try:
        system_prompt = (
            "You are an expert marketing strategist. Create a comprehensive social media strategy. "
            "Return ONLY valid JSON with keys: strategy_text (detailed plan), "
            "recommended_platforms (list of strings), posting_schedule (object day->count), "
            "content_themes (list of strings)."
        )
        user_prompt = (
            f"Create a marketing strategy for:\n"
            f"Business: {business.name}\n"
            f"Industry: {business.industry or 'general'}\n"
            f"Goals: {', '.join(body.goals)}\n"
            f"Platforms: {', '.join(body.platforms)}\n"
            f"Budget: ${body.budget or 'flexible'}/month\n"
            f"Timeframe: {body.timeframe}\n"
            f"Target audience: {json.dumps(business.target_audience) if business.target_audience else 'general'}"
        )
        raw_text, tokens_in, tokens_out = await _call_openai(user_prompt, system_prompt)
        gen.tokens_input = tokens_in
        gen.tokens_output = tokens_out
        gen.response = raw_text
        gen.status = AIGenerationStatus.COMPLETED
        await db.flush()
        await db.refresh(gen)

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            parsed = {
                "strategy_text": raw_text,
                "recommended_platforms": body.platforms or [],
                "posting_schedule": {},
                "content_themes": [],
            }

        return StrategyGenerateResponse(
            strategy_text=parsed.get("strategy_text", raw_text),
            recommended_platforms=parsed.get("recommended_platforms", []),
            posting_schedule=parsed.get("posting_schedule", {}),
            content_themes=parsed.get("content_themes", []),
            generation_id=gen.id,
        )

    except Exception as exc:
        gen.status = AIGenerationStatus.FAILED
        gen.error_message = str(exc)[:500]
        await db.flush()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI strategy generation failed: {exc}")
