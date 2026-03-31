"""Strategy management endpoints."""

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.ai_generation import AIGeneration, AIGenerationStatus, GenerationType
from app.models.business import Business
from app.models.post import Post, PostStatus
from app.models.strategy import Strategy
from app.models.team_member import TeamMember, TeamRole
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.strategy import StrategyGenerate, StrategyResponse, StrategyUpdate

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _verify_account_access(
    account_id: uuid.UUID, user, db: AsyncSession, *, min_role: TeamRole | None = None
) -> TeamMember:
    result = await db.execute(
        select(TeamMember).where(
            TeamMember.account_id == account_id,
            TeamMember.user_id == user.id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this account")

    role_hierarchy = [TeamRole.VIEWER, TeamRole.EDITOR, TeamRole.MANAGER, TeamRole.ADMIN, TeamRole.OWNER]
    if min_role and role_hierarchy.index(member.role) < role_hierarchy.index(min_role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Requires at least {min_role.value} role")
    return member


async def _get_strategy_or_404(
    strategy_id: uuid.UUID, account_id: uuid.UUID, db: AsyncSession
) -> Strategy:
    result = await db.execute(
        select(Strategy).where(Strategy.id == strategy_id, Strategy.account_id == account_id)
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")
    return strategy


# ---------------------------------------------------------------------------
# Response extras
# ---------------------------------------------------------------------------

class ApplyStrategyResponse(BaseModel):
    message: str
    posts_created: int
    post_ids: list[uuid.UUID]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/", response_model=PaginatedResponse[StrategyResponse])
async def list_strategies(
    account_id: uuid.UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """List all strategies for the account."""
    await _verify_account_access(account_id, current_user, db)

    from sqlalchemy import func as sa_func

    total_result = await db.execute(
        select(sa_func.count(Strategy.id)).where(Strategy.account_id == account_id)
    )
    total = total_result.scalar() or 0

    stmt = (
        select(Strategy)
        .where(Strategy.account_id == account_id)
        .order_by(Strategy.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(stmt)
    strategies = result.scalars().all()

    return PaginatedResponse(
        items=[StrategyResponse.model_validate(s) for s in strategies],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page if per_page else 1,
    )


@router.post("/generate", response_model=StrategyResponse, status_code=status.HTTP_201_CREATED)
async def generate_strategy(
    account_id: uuid.UUID,
    body: StrategyGenerate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Generate a new marketing strategy using AI."""
    await _verify_account_access(account_id, current_user, db, min_role=TeamRole.EDITOR)

    # Fetch business
    biz_result = await db.execute(
        select(Business).where(Business.id == body.business_id, Business.account_id == account_id)
    )
    business = biz_result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")

    # Log AI generation
    gen = AIGeneration(
        user_id=current_user.id,
        account_id=account_id,
        generation_type=GenerationType.STRATEGY,
        provider="openai",
        model="gpt-4o",
        prompt=f"Strategy for {business.name}: {body.goal}",
        status=AIGenerationStatus.PENDING,
    )
    db.add(gen)
    await db.flush()

    # Generate strategy content (mock or real)
    if not settings.OPENAI_API_KEY:
        strategy_data = {
            "name": f"AI Strategy: {body.goal[:60]}",
            "reasoning": (
                f"Mock strategy for {business.name}. "
                "Configure OPENAI_API_KEY for real AI-generated strategies."
            ),
            "platform_mix": {p: 1.0 / len(body.platforms) for p in body.platforms} if body.platforms else {"instagram": 0.5, "facebook": 0.5},
            "posting_frequency": {"daily": 1, "weekly_total": 7},
            "content_themes": ["brand awareness", "customer engagement", "product showcase"],
            "confidence_score": 0.75,
        }
        gen.status = AIGenerationStatus.COMPLETED
        gen.provider = "mock"
        gen.response = json.dumps(strategy_data)
    else:
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            system_prompt = (
                "You are a marketing strategist. Generate a strategy. Return ONLY valid JSON with keys: "
                "name (string), reasoning (detailed text), platform_mix (object platform->weight 0-1), "
                "posting_frequency (object), content_themes (list of strings), confidence_score (0-1 float)."
            )
            user_prompt = (
                f"Business: {business.name}\nIndustry: {business.industry or 'general'}\n"
                f"Goal: {body.goal}\nPlatforms: {body.platforms}\nBudget: ${body.budget or 'flexible'}/month"
            )
            completion = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
            )
            raw = completion.choices[0].message.content or "{}"
            gen.tokens_input = completion.usage.prompt_tokens if completion.usage else 0
            gen.tokens_output = completion.usage.completion_tokens if completion.usage else 0
            gen.response = raw
            gen.status = AIGenerationStatus.COMPLETED

            try:
                strategy_data = json.loads(raw)
            except json.JSONDecodeError:
                strategy_data = {
                    "name": f"Strategy: {body.goal[:60]}",
                    "reasoning": raw,
                    "platform_mix": {},
                    "posting_frequency": {},
                    "content_themes": [],
                    "confidence_score": 0.5,
                }
        except Exception as exc:
            gen.status = AIGenerationStatus.FAILED
            gen.error_message = str(exc)[:500]
            await db.flush()
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI generation failed: {exc}")

    await db.flush()

    # Create Strategy record
    strategy = Strategy(
        user_id=current_user.id,
        account_id=account_id,
        business_id=business.id,
        name=strategy_data.get("name", f"Strategy: {body.goal[:60]}"),
        goal=body.goal,
        platform_mix=strategy_data.get("platform_mix", {}),
        posting_frequency=strategy_data.get("posting_frequency", {}),
        content_themes=strategy_data.get("content_themes", []),
        reasoning=strategy_data.get("reasoning", ""),
        confidence_score=strategy_data.get("confidence_score"),
        is_active=False,
    )
    db.add(strategy)
    await db.flush()
    await db.refresh(strategy)
    return StrategyResponse.model_validate(strategy)


@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    account_id: uuid.UUID,
    strategy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Get strategy details."""
    await _verify_account_access(account_id, current_user, db)
    strategy = await _get_strategy_or_404(strategy_id, account_id, db)
    return StrategyResponse.model_validate(strategy)


@router.put("/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    account_id: uuid.UUID,
    strategy_id: uuid.UUID,
    body: StrategyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Update a strategy."""
    await _verify_account_access(account_id, current_user, db, min_role=TeamRole.EDITOR)
    strategy = await _get_strategy_or_404(strategy_id, account_id, db)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(strategy, field, value)

    await db.flush()
    await db.refresh(strategy)
    return StrategyResponse.model_validate(strategy)


@router.delete("/{strategy_id}", response_model=MessageResponse)
async def delete_strategy(
    account_id: uuid.UUID,
    strategy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Delete a strategy."""
    await _verify_account_access(account_id, current_user, db, min_role=TeamRole.MANAGER)
    strategy = await _get_strategy_or_404(strategy_id, account_id, db)
    await db.delete(strategy)
    await db.flush()
    return MessageResponse(message="Strategy deleted successfully")


@router.post("/{strategy_id}/activate", response_model=StrategyResponse)
async def activate_strategy(
    account_id: uuid.UUID,
    strategy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Set a strategy as the active strategy. Deactivates all others for this account."""
    await _verify_account_access(account_id, current_user, db, min_role=TeamRole.MANAGER)
    strategy = await _get_strategy_or_404(strategy_id, account_id, db)

    # Deactivate all other strategies in the same account
    all_result = await db.execute(
        select(Strategy).where(Strategy.account_id == account_id, Strategy.is_active.is_(True))
    )
    for s in all_result.scalars().all():
        s.is_active = False

    strategy.is_active = True
    await db.flush()
    await db.refresh(strategy)
    return StrategyResponse.model_validate(strategy)


@router.post("/{strategy_id}/apply", response_model=ApplyStrategyResponse)
async def apply_strategy(
    account_id: uuid.UUID,
    strategy_id: uuid.UUID,
    count: int = Query(5, ge=1, le=30, description="Number of posts to generate"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Apply strategy recommendations by creating draft posts from the strategy's content themes."""
    await _verify_account_access(account_id, current_user, db, min_role=TeamRole.EDITOR)
    strategy = await _get_strategy_or_404(strategy_id, account_id, db)

    themes = strategy.content_themes or []
    platforms_list = list(strategy.platform_mix.keys()) if strategy.platform_mix else ["instagram"]

    created_ids: list[uuid.UUID] = []
    for i in range(count):
        theme = themes[i % len(themes)] if themes else "general content"
        platforms_data = [{"type": p} for p in platforms_list]

        post = Post(
            user_id=current_user.id,
            account_id=account_id,
            business_id=strategy.business_id,
            strategy_id=strategy.id,
            content=f"[Draft from strategy] Theme: {theme}",
            hashtags=[],
            platforms=platforms_data,
            status=PostStatus.DRAFT,
        )
        db.add(post)
        await db.flush()
        created_ids.append(post.id)

    return ApplyStrategyResponse(
        message=f"Created {len(created_ids)} draft posts from strategy",
        posts_created=len(created_ids),
        post_ids=created_ids,
    )
