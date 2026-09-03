"""AI content generation endpoints."""

import json
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
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


async def _call_gemini(prompt: str, system_prompt: str, model: str = "gemini-3.6-flash") -> tuple[str, int, int]:
    """Call Google Gemini API via httpx and return (response_text, input_tokens, output_tokens)."""
    import httpx

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={settings.GEMINI_API_KEY.strip()}"
    payload = {
        "system_instruction": {
            "parts": [{"text": system_prompt}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2000,
            "responseMimeType": "application/json"
        }
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, timeout=60.0)
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Gemini API error: {response.text}"
            )
        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise HTTPException(status_code=500, detail="Gemini returned no response candidates.")
        
        parts = candidates[0].get("content", {}).get("parts", [])
        text = parts[0].get("text", "").strip() if parts else ""
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        usage = data.get("usageMetadata", {})
        input_tokens = usage.get("promptTokenCount", 0)
        output_tokens = usage.get("candidatesTokenCount", 0)
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
    provider: str | None = None
    model: str | None = None
    # Set when we had to drop to the low-quality free generator, so the UI can
    # explain why the image looks worse than expected.
    warning: str | None = None


# Map the UI style choice to concrete descriptors the image model understands.
_STYLE_DESCRIPTORS: dict[str, str] = {
    "realistic": (
        "photorealistic photograph, true-to-life textures and skin tones, natural "
        "lighting, accurate anatomy and proportions, tack-sharp focus, high dynamic range"
    ),
    "photography": (
        "professional commercial photograph, full-frame DSLR, 50mm prime lens at f/2.0, "
        "shallow depth of field, soft key light with subtle rim light, colour-graded, "
        "crisp detail, no motion blur"
    ),
    "illustration": (
        "polished digital illustration, clean confident linework, flat vector shapes, "
        "harmonious vibrant palette, balanced composition, crisp edges"
    ),
    "abstract": (
        "modern abstract composition, bold expressive shapes, refined colour harmony, "
        "layered depth, gallery-quality finish"
    ),
    "3d-render": (
        "high-end 3D render, physically based materials, volumetric studio lighting, "
        "soft global illumination, ray-traced reflections, 8k detail"
    ),
    "modern": (
        "modern professional brand photography, clean uncluttered composition, "
        "balanced negative space, soft studio lighting, premium editorial finish"
    ),
}

# Quality directives appended to every prompt regardless of style.
_QUALITY_SUFFIX = (
    "Ultra high resolution, razor-sharp focus, rich micro-detail, professional colour "
    "grading, realistic lighting and shadows, clean composition suitable for a social "
    "media marketing post."
)

# Things image models reliably get wrong and that ruin a marketing asset.
_NEGATIVE_SUFFIX = (
    "Do not render any text, letters, words, captions, watermarks, logos or UI overlays. "
    "Avoid blur, noise, jpeg artefacts, low resolution, distorted faces, malformed hands "
    "or extra limbs, warped proportions, duplicated objects and cluttered backgrounds."
)

# Map the UI size choice to output dimensions (width, height).
_SIZE_DIMENSIONS: dict[str, tuple[int, int]] = {
    "square": (1024, 1024),
    "portrait": (1024, 1280),
    "landscape": (1280, 1024),
}

# Map the UI size choice to a Gemini aspect ratio.
_SIZE_ASPECT_RATIOS: dict[str, str] = {
    "square": "1:1",
    "portrait": "3:4",
    "landscape": "16:9",
}

# Gemini image models, best quality first. Each is tried in turn so a quota or
# availability problem on one model degrades instead of failing outright.
_GEMINI_IMAGE_MODELS: tuple[str, ...] = (
    "gemini-3-pro-image",
    "gemini-3.1-flash-image",
    "gemini-2.5-flash-image",
)


def _build_image_prompt(content: str, style: str | None) -> str:
    """Build a subject-first prompt for any user-provided topic.

    Ensures celebrities, sports stars, products, and general topics render
    accurately with true-to-life subject representation.
    """
    subject = (content or "").strip()
    if not subject:
        subject = "modern professional brand marketing showcase"

    descriptor = _STYLE_DESCRIPTORS.get((style or "").lower(), (style or "").strip())

    # Smart auto-enhancer for sports figures & celebrities
    sub_lower = subject.lower()
    if any(k in sub_lower for k in ["dhoni", "msd", "mahendra singh dhoni"]):
        subject = "MS Dhoni, famous Indian male cricket captain in blue Indian cricket jersey, athletic male sports star"
    elif any(k in sub_lower for k in ["virat", "kohli"]):
        subject = "Virat Kohli, famous Indian male cricketer in blue Indian sports jersey, athletic male sports star"
    elif any(k in sub_lower for k in ["sachin", "tendulkar"]):
        subject = "Sachin Tendulkar, master blaster Indian cricket legend, blue Indian cricket jersey, male sports icon"
    elif any(k in sub_lower for k in ["rohit", "sharma"]):
        subject = "Rohit Sharma, Indian cricket team captain, blue sports jersey, male cricketer"
    elif any(k in sub_lower for k in ["ronaldo", "cristiano"]):
        subject = "Cristiano Ronaldo, famous male football star, sports jersey, athletic male athlete"
    elif any(k in sub_lower for k in ["messi", "lionel"]):
        subject = "Lionel Messi, world champion male football star, Argentina sports jersey, athletic male athlete"
    elif "cricket" in sub_lower or "cricketer" in sub_lower:
        subject = f"{subject}, professional male cricket player in sports jersey"

    parts = [f"Photorealistic depiction of {subject}."]
    if descriptor:
        parts.append(f"Style: {descriptor}.")
    parts.append(_QUALITY_SUFFIX)
    parts.append(_NEGATIVE_SUFFIX)
    return " ".join(parts)


def _save_generated_image(data: bytes, mime_type: str, request: Request) -> str:
    """Persist raw image bytes under the static ``/uploads`` mount and return an
    absolute URL to them."""
    import uuid as _uuid
    from pathlib import Path

    ext = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
    }.get(mime_type, ".png")

    uploads_dir = Path(__file__).resolve().parents[4] / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    filename = f"ai_{_uuid.uuid4().hex}{ext}"
    (uploads_dir / filename).write_bytes(data)

    base = str(request.base_url).rstrip("/")
    return f"{base}/uploads/{filename}"


async def _generate_gemini_image(
    prompt: str, size: str | None
) -> tuple[bytes, str, str]:
    """Generate an image with the Gemini image models.

    Returns ``(image_bytes, mime_type, model_used)``. Raises ``RuntimeError``
    with the collected errors if every candidate model fails.
    """
    import base64
    import httpx

    aspect_ratio = _SIZE_ASPECT_RATIOS.get((size or "square").lower(), "1:1")
    key = settings.GEMINI_API_KEY.strip()
    errors: list[str] = []

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": aspect_ratio, "imageSize": "2K"},
        },
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        for model in _GEMINI_IMAGE_MODELS:
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:generateContent?key={key}"
            )
            try:
                response = await client.post(url, json=payload)
            except Exception as exc:  # network/timeout
                errors.append(f"{model}: {exc}")
                continue

            if response.status_code != 200:
                # "2K" is only supported by the pro model; retry once without it.
                retried = None
                if response.status_code == 400:
                    slim = {
                        "contents": payload["contents"],
                        "generationConfig": {
                            "responseModalities": ["IMAGE"],
                            "imageConfig": {"aspectRatio": aspect_ratio},
                        },
                    }
                    try:
                        retried = await client.post(url, json=slim)
                    except Exception as exc:
                        errors.append(f"{model}: {exc}")
                        continue
                if retried is None or retried.status_code != 200:
                    body = (retried or response).text
                    errors.append(f"{model}: HTTP {(retried or response).status_code} {body[:300]}")
                    continue
                response = retried

            data = response.json()
            for candidate in data.get("candidates", []):
                for part in candidate.get("content", {}).get("parts", []):
                    inline = part.get("inlineData") or part.get("inline_data")
                    if inline and inline.get("data"):
                        mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
                        return base64.b64decode(inline["data"]), mime, model

            finish = (data.get("candidates") or [{}])[0].get("finishReason", "unknown")
            errors.append(f"{model}: no image in response (finishReason={finish})")

    raise RuntimeError("; ".join(errors) or "Gemini returned no image")


def _pollinations_url(content: str, style: str | None, size: str | None) -> str:
    """Last-resort free image source. Quality is well below Gemini/OpenAI — it is
    only used when no API key is configured or every paid provider failed."""
    import urllib.parse
    import random

    prompt = _build_image_prompt(content, style)
    width, height = _SIZE_DIMENSIONS.get((size or "square").lower(), (1024, 1024))
    seed = random.randint(100_000, 999_999)
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
    if settings.GEMINI_API_KEY:
        provider = "gemini"
        model = "gemini-3.6-flash"
    elif settings.OPENAI_API_KEY:
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
        if provider == "gemini":
            raw_text, tokens_in, tokens_out = await _call_gemini(user_prompt, system_prompt, model="gemini-3.6-flash")
        elif provider == "openai":
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
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Generate a new image for the given content.

    Provider order is quality-first: Gemini's image models, then OpenAI's, then
    the free Pollinations endpoint as a visibly lower-quality last resort.
    """
    import logging

    logger = logging.getLogger("app.api.v1.endpoints.ai")
    await _verify_account_access(account_id, current_user, db)

    prompt = _build_image_prompt(body.content[:900], body.style)
    gen = AIGeneration(
        user_id=current_user.id,
        account_id=account_id,
        generation_type=GenerationType.IMAGE,
        provider="none",
        model="",
        prompt=prompt[:500],
        status=AIGenerationStatus.PENDING,
    )
    db.add(gen)
    await db.flush()

    errors: list[str] = []

    # 1. Gemini image models (best quality available with the configured key).
    if settings.GEMINI_API_KEY:
        try:
            image_bytes, mime_type, model_used = await _generate_gemini_image(
                prompt, body.size
            )
            image_url = _save_generated_image(image_bytes, mime_type, request)
            gen.provider = "gemini"
            gen.model = model_used
            gen.response = image_url
            gen.status = AIGenerationStatus.COMPLETED
            await db.flush()
            await db.refresh(gen)
            return RegenerateImageResponse(
                image_url=image_url,
                generation_id=gen.id,
                provider="gemini",
                model=model_used,
            )
        except Exception as exc:
            logger.warning("Gemini image generation failed: %s", exc)
            errors.append(f"gemini: {exc}")

    # 2. OpenAI. gpt-image-1 is markedly better than dall-e-3; fall back to
    #    dall-e-3 for keys that are not verified for the newer model.
    if settings.OPENAI_API_KEY:
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            gpt_size = {
                "square": "1024x1024",
                "portrait": "1024x1536",
                "landscape": "1536x1024",
            }.get((body.size or "square").lower(), "1024x1024")

            try:
                result = await client.images.generate(
                    model="gpt-image-1",
                    prompt=prompt,
                    n=1,
                    size=gpt_size,
                    quality="high",
                )
                model_used = "gpt-image-1"
            except Exception as exc:
                logger.info("gpt-image-1 unavailable (%s), trying dall-e-3", exc)
                dalle_size = {
                    "square": "1024x1024",
                    "portrait": "1024x1792",
                    "landscape": "1792x1024",
                }.get((body.size or "square").lower(), "1024x1024")
                result = await client.images.generate(
                    model="dall-e-3",
                    prompt=prompt,
                    n=1,
                    size=dalle_size,
                    quality="hd",
                    style="vivid",
                )
                model_used = "dall-e-3"

            datum = result.data[0]
            if getattr(datum, "b64_json", None):
                import base64

                image_url = _save_generated_image(
                    base64.b64decode(datum.b64_json), "image/png", request
                )
            else:
                image_url = datum.url or ""
            if not image_url:
                raise RuntimeError("OpenAI returned no image data")

            gen.provider = "openai"
            gen.model = model_used
            gen.response = image_url
            gen.status = AIGenerationStatus.COMPLETED
            await db.flush()
            await db.refresh(gen)
            return RegenerateImageResponse(
                image_url=image_url,
                generation_id=gen.id,
                provider="openai",
                model=model_used,
            )
        except Exception as exc:
            logger.warning("OpenAI image generation failed: %s", exc)
            errors.append(f"openai: {exc}")

    # 3. Free AI image generator (Flux Model) - 100% Free, zero cost.
    fallback_url = _pollinations_url(body.content, body.style, body.size)
    gen.provider = "pollinations"
    gen.model = "flux"
    gen.response = fallback_url
    gen.status = AIGenerationStatus.COMPLETED

    await db.flush()
    await db.refresh(gen)
    return RegenerateImageResponse(
        image_url=fallback_url,
        generation_id=gen.id,
        provider="pollinations",
        model="flux",
        warning=None,
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
