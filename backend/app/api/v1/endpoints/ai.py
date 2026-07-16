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
    """Return a mock AI response when no OpenAI key is configured.

    Keeps the copy and hashtags focused strictly on the topic the user typed —
    no company name or unrelated filler.
    """
    import re

    topic = (prompt or "").strip()
    words = re.findall(r"[A-Za-z0-9]+", topic.lower())
    stop = {
        "the", "a", "an", "and", "or", "for", "to", "of", "in", "on", "with",
        "about", "post", "content", "create", "make", "write", "generate",
        "my", "me", "please", "give", "related", "only", "is", "are", "this",
    }
    seen: set[str] = set()
    keywords = [
        w for w in words
        if w not in stop and len(w) > 2 and not (w in seen or seen.add(w))
    ]
    hashtags = keywords[:8] or ["trending"]

    label = topic or "your topic"
    content = (
        f"{label.capitalize()} 🔥\n\n"
        f"Everything you love about {label}, all in one place. "
        f"Drop your favourite {label} moment in the comments below 👇"
    )
    platform_variations = {p: f"[{p.upper()}] {content}" for p in platforms}
    return {
        "content": content,
        "hashtags": hashtags,
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


async def _call_anthropic(prompt: str, system_prompt: str, model: str = "claude-sonnet-4-6") -> tuple[str, int, int]:
    """Call Anthropic API via httpx and return (response_text, input_tokens, output_tokens)."""
    import httpx

    headers = {
        "x-api-key": settings.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    payload = {
        "model": model,
        "max_tokens": 2000,
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
            timeout=60.0
        )
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Anthropic API error: {response.text}"
            )
        data = response.json()
        text = data["content"][0]["text"].strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        input_tokens = data.get("usage", {}).get("input_tokens", 0)
        output_tokens = data.get("usage", {}).get("output_tokens", 0)
        return text, input_tokens, output_tokens


# ---------------------------------------------------------------------------
# Request / Response extras
# ---------------------------------------------------------------------------

class RegenerateImageRequest(BaseModel):
    content: str
    style: str | None = "modern"
    size: str | None = "square"


class RegenerateImageResponse(BaseModel):
    image_url: str
    generation_id: uuid.UUID


# Map the UI style choice to concrete descriptors the image model understands.
_STYLE_DESCRIPTORS: dict[str, str] = {
    "realistic": "photorealistic, ultra realistic, natural lighting, highly detailed",
    "photography": "professional photography, DSLR, sharp focus, depth of field, cinematic lighting",
    "illustration": "digital illustration, clean vector art, vibrant colors",
    "abstract": "abstract art, expressive shapes, artistic composition",
    "3d-render": "3D render, octane render, volumetric lighting, highly detailed",
    "modern": "modern, clean, professional",
}

# Map the UI size choice to output dimensions (width, height).
_SIZE_DIMENSIONS: dict[str, tuple[int, int]] = {
    "square": (1024, 1024),
    "portrait": (1024, 1280),
    "landscape": (1280, 1024),
}


def _build_image_prompt(content: str, style: str | None) -> str:
    """Build a subject-first prompt so the described subject dominates the image
    instead of being diluted by generic marketing boilerplate."""
    subject = (content or "").strip()
    descriptor = _STYLE_DESCRIPTORS.get((style or "").lower(), style or "")
    if descriptor:
        return f"{subject}. {descriptor}"
    return subject


def _pollinations_url(content: str, style: str | None, size: str | None) -> str:
    """Construct a Pollinations image URL with the flux model, prompt
    enhancement and a deterministic seed derived from the prompt."""
    import urllib.parse
    import zlib

    prompt = _build_image_prompt(content, style)
    width, height = _SIZE_DIMENSIONS.get((size or "square").lower(), (1024, 1024))
    # Deterministic per-prompt seed (stable across processes, unlike hash()).
    seed = zlib.crc32(prompt.encode("utf-8")) % 1_000_000
    encoded = urllib.parse.quote(prompt)
    return (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width={width}&height={height}&model=flux&enhance=true&nologo=true&seed={seed}"
    )


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

    # Note: we intentionally do NOT inject the business/brand profile into the
    # prompt. The user wants copy strictly about the topic they typed (e.g.
    # "dhoni") — not the company name or any unrelated info.
    system_prompt = (
        "You are a social media copywriter. Write ONE short, engaging social media "
        f"post about ONLY the exact topic/brief the user gives. Tone: {body.tone or 'professional'}.\n"
        "Strict rules:\n"
        "- Stay strictly on the given topic. Write only about it.\n"
        "- Do NOT mention any company, brand, product, business, app or website name "
        "unless that name literally appears in the user's topic.\n"
        "- Do NOT add unrelated information, calls to sign up, or promotional filler.\n"
        "- Hashtags must be directly about the topic only (e.g. topic 'dhoni' -> "
        "dhoni, cricket, thala, csk, captaincool).\n"
    )

    if "linkedin" in body.platforms:
        system_prompt += (
            "- Because LinkedIn is one of the target platforms, optimize the copy specifically for a professional "
            "business audience, recruiters, and career professionals. Focus on professional value, networking significance, "
            "and industry-minded insights, while staying strictly on the topic.\n"
        )

    system_prompt += (
        "Return ONLY valid JSON with keys: content (a string under 200 words) and "
        "hashtags (a list of 5-10 short strings, each relevant to the topic, without the '#' symbol). "
        "Do NOT generate separate platform variations."
    )

    # Determine provider and model based on configured API keys
    provider = "mock"
    model = "mock"
    if settings.OPENAI_API_KEY:
        provider = "openai"
        model = "gpt-4o"
    elif settings.ANTHROPIC_API_KEY:
        provider = "anthropic"
        model = "claude-sonnet-4-6"

    gen = AIGeneration(
        user_id=current_user.id,
        account_id=account_id,
        generation_type=GenerationType.CONTENT,
        provider=provider,
        model=model,
        prompt=body.prompt,
        status=AIGenerationStatus.PENDING,
    )
    db.add(gen)
    await db.flush()

    start = time.time()

    if provider == "mock":
        mock = _mock_content_response(body.prompt, body.platforms, body.tone or "professional")
        gen.response = json.dumps(mock)
        gen.status = AIGenerationStatus.COMPLETED
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
        if provider == "openai":
            raw_text, tokens_in, tokens_out = await _call_openai(user_prompt, system_prompt)
        else:
            raw_text, tokens_in, tokens_out = await _call_anthropic(user_prompt, system_prompt)

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
        import logging
        logging.getLogger("app.api.v1.endpoints.ai").warning(
            "AI generation failed, falling back to mock content. Error: %s", exc
        )
        mock = _mock_content_response(body.prompt, body.platforms, body.tone or "professional")
        mock["content"] = (
            f"Here is fallback content for: {body.prompt}\n\n"
            f"⚠️ (Note: AI generator service connection failed, returned a fallback response. Error: {exc})"
        )
        gen.response = json.dumps(mock)
        gen.status = AIGenerationStatus.COMPLETED
        gen.error_message = f"Fallback triggered. Original error: {exc}"[:500]
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
        image_url = _pollinations_url(body.content, body.style, body.size)
        gen.status = AIGenerationStatus.COMPLETED
        gen.provider = "mock"
        gen.response = image_url
        await db.flush()
        await db.refresh(gen)
        return RegenerateImageResponse(
            image_url=gen.response,
            generation_id=gen.id,
        )

    # DALL-E accepts a fixed set of sizes; map our aspect choice onto them.
    _dalle_size = {
        "square": "1024x1024",
        "portrait": "1024x1792",
        "landscape": "1792x1024",
    }.get((body.size or "square").lower(), "1024x1024")

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        result = await client.images.generate(
            model="dall-e-3",
            prompt=_build_image_prompt(body.content[:900], body.style),
            n=1,
            size=_dalle_size,
        )
        image_url = result.data[0].url or ""
        gen.response = image_url
        gen.status = AIGenerationStatus.COMPLETED
        await db.flush()
        await db.refresh(gen)
        return RegenerateImageResponse(image_url=image_url, generation_id=gen.id)

    except Exception as exc:
        import logging
        logging.getLogger("app.api.v1.endpoints.ai").warning(
            "AI image generation failed, falling back to placeholder. Error: %s", exc
        )
        fallback_url = _pollinations_url(body.content, body.style, body.size)
        gen.response = fallback_url
        gen.status = AIGenerationStatus.COMPLETED
        gen.error_message = f"Fallback triggered. Original error: {exc}"[:500]
        await db.flush()
        await db.refresh(gen)
        return RegenerateImageResponse(image_url=fallback_url, generation_id=gen.id)


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

    # Determine provider and model based on configured API keys
    provider = "mock"
    model = "mock"
    if settings.OPENAI_API_KEY:
        provider = "openai"
        model = "gpt-4o"
    elif settings.ANTHROPIC_API_KEY:
        provider = "anthropic"
        model = "claude-sonnet-4-6"

    gen = AIGeneration(
        user_id=current_user.id,
        account_id=account_id,
        generation_type=GenerationType.CONTENT,
        provider=provider,
        model=model,
        prompt=f"Suggest {body.count} topics for {business.name}",
        status=AIGenerationStatus.PENDING,
    )
    db.add(gen)
    await db.flush()

    if provider == "mock":
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
        if provider == "openai":
            raw_text, tokens_in, tokens_out = await _call_openai(user_prompt, system_prompt)
        else:
            raw_text, tokens_in, tokens_out = await _call_anthropic(user_prompt, system_prompt)

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
        import logging
        logging.getLogger("app.api.v1.endpoints.ai").warning(
            "AI topic suggestion failed, falling back to mock topics. Error: %s", exc
        )
        mock_topics = [
            {
                "title": f"Topic {i+1} for {business.name} (Fallback)",
                "description": f"Connection to AI service failed. Fallback topic idea #{i+1} about {business.industry or 'your industry'}.",
                "platforms": ["instagram", "facebook"],
                "estimated_engagement": "medium",
            }
            for i in range(body.count)
        ]
        gen.status = AIGenerationStatus.COMPLETED
        gen.error_message = f"Fallback triggered. Original error: {exc}"[:500]
        gen.response = json.dumps(mock_topics)
        await db.flush()
        await db.refresh(gen)
        return AITopicSuggestion(topics=mock_topics)


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

    # Determine provider and model based on configured API keys
    provider = "mock"
    model = "mock"
    if settings.OPENAI_API_KEY:
        provider = "openai"
        model = "gpt-4o"
    elif settings.ANTHROPIC_API_KEY:
        provider = "anthropic"
        model = "claude-sonnet-4-6"

    gen = AIGeneration(
        user_id=current_user.id,
        account_id=account_id,
        generation_type=GenerationType.STRATEGY,
        provider=provider,
        model=model,
        prompt=f"Generate strategy for {business.name}, goals: {body.goals}",
        status=AIGenerationStatus.PENDING,
    )
    db.add(gen)
    await db.flush()

    if provider == "mock":
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
        if provider == "openai":
            raw_text, tokens_in, tokens_out = await _call_openai(user_prompt, system_prompt)
        else:
            raw_text, tokens_in, tokens_out = await _call_anthropic(user_prompt, system_prompt)

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
        import logging
        logging.getLogger("app.api.v1.endpoints.ai").warning(
            "AI strategy generation failed, falling back to mock strategy. Error: %s", exc
        )
        mock = {
            "strategy_text": (
                f"Marketing Strategy for {business.name} (Fallback)\n\n"
                f"Goals: {', '.join(body.goals)}\n"
                f"Budget: ${body.budget or 0}/month\n"
                f"Timeframe: {body.timeframe}\n\n"
                f"⚠️ (Note: AI generator service connection failed, returned a fallback response. Error: {exc})"
            ),
            "recommended_platforms": body.platforms or ["instagram", "facebook"],
            "posting_schedule": {
                "monday": 2, "tuesday": 1, "wednesday": 2,
                "thursday": 1, "friday": 2, "saturday": 1, "sunday": 0,
            },
            "content_themes": ["brand awareness", "customer engagement", "product showcase", "behind the scenes"],
        }
        gen.status = AIGenerationStatus.COMPLETED
        gen.error_message = f"Fallback triggered. Original error: {exc}"[:500]
        gen.response = json.dumps(mock)
        await db.flush()
        await db.refresh(gen)
        return StrategyGenerateResponse(**mock, generation_id=gen.id)
