"""Inline calendar intelligence: where the month is empty, and filling it.

The smaller sibling of the monthly plan. Same discipline, narrower window:
``/suggestions`` says nothing but what it can point at, and ``/suggest-fill``
produces **proposals**, not posts. Accepting them goes through the monthly
plan's accept endpoint -- one path to a draft, not two, so the "never publish,
never schedule" guarantee is enforced in one place.
"""

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import verify_account_access as _verify_account_access
from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.core.entitlement_deps import meter_ai_request
from app.core.permissions import CONTENT_CREATE, CONTENT_VIEW
from app.core.ratelimit import ai_generation_rate_limit
from app.models.account import Account
from app.models.content_plan import ContentPlan, ContentPlanItem, PlanGoal
from app.services import ai_assist, calendar_gaps, content_plan, recurrence
from app.services.activity_service import log_activity
from app.services import entitlement_service as ent

router = APIRouter()

# Generating copy costs the AI allowance, so that route carries the same
# metering and rate limiting the AI router applies to everything else. The
# read-only analysis does not: it is arithmetic over rows this workspace
# already owns, and charging for looking at your own calendar would be absurd.
fill_router = APIRouter(
    dependencies=[Depends(ai_generation_rate_limit), Depends(meter_ai_request)]
)


@router.get("/suggestions")
async def calendar_suggestions(
    account_id: uuid.UUID,
    from_: date = Query(..., alias="from"),
    to: date = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Gaps in the range, measured against what this workspace already declared.

    Read-only and unmetered. Every gap carries the strength of the claim behind
    it -- a queue slot the workspace committed to, an observed best time from
    its own history, or a platform convention -- because presenting the third
    like the first is how a suggestion becomes a fabrication.
    """
    await _verify_account_access(
        account_id, current_user, db, permission=CONTENT_VIEW
    )
    account = (
        await db.execute(select(Account).where(Account.id == account_id))
    ).scalar_one()

    try:
        return await calendar_gaps.analyse(db, account, from_, to)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class FillSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # A naive local reading on the workspace's clock, exactly as the analysis
    # returned it. Not an instant: the workspace's timezone decides what this
    # means, which is the rule the composer's schedule field also follows.
    local_datetime: datetime
    social_account_id: uuid.UUID


class SuggestFillRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slots: list[FillSlot] = Field(min_length=1, max_length=20)
    goal: PlanGoal = PlanGoal.ENGAGEMENT
    topic_hints: str | None = Field(None, max_length=2000)
    provider: str | None = None


@fill_router.post("/suggest-fill", status_code=status.HTTP_201_CREATED)
async def suggest_fill(
    account_id: uuid.UUID,
    body: SuggestFillRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Draft proposals for chosen gaps.

    Delegates to the monthly plan's generator with a narrow window, and stores
    the result as a plan -- so these are accepted through the same endpoint,
    with the same atomic reservation and the same drafts-not-schedules
    guarantee. A second acceptance path would be a second chance to get that
    wrong.
    """
    await _verify_account_access(
        account_id, current_user, db, permission=CONTENT_CREATE
    )
    account = (
        await db.execute(select(Account).where(Account.id == account_id))
    ).scalar_one()

    organization = await ent.get_organization_for_account(db, account_id)
    remaining = content_plan.AI_REQUEST_WEIGHT - 1
    if remaining > 0:
        await ent.check_and_increment(
            db, organization, ent.AI_REQUESTS_PER_MONTH, amount=remaining
        )

    grounding = await content_plan.gather_grounding(db, account)
    by_id = {c["social_account_id"]: c for c in grounding["connections"]}

    slots = []
    for chosen in body.slots:
        connection = by_id.get(str(chosen.social_account_id))
        if connection is None:
            raise HTTPException(
                status_code=404,
                detail="One of those accounts is not connected to this workspace.",
            )
        if chosen.local_datetime.tzinfo is not None:
            raise HTTPException(
                status_code=422,
                detail=(
                    "local_datetime is a reading on the workspace's clock and "
                    "must not carry an offset."
                ),
            )
        platform = connection["platform"]
        info = grounding.get("slots", {}).get(platform) or {}
        observed = any(
            s["weekday"] == chosen.local_datetime.weekday()
            and s["hour"] == chosen.local_datetime.hour
            and s["observed"]
            for s in info.get("suggestions", [])
        )
        slots.append({
            "platform": platform,
            "social_account_id": connection["social_account_id"],
            "account_name": connection["account_name"],
            "local": chosen.local_datetime,
            "slot_source": "observed" if observed else info.get("source", "default"),
            "observed": observed,
        })

    system_prompt, user_prompt = content_plan.build_prompts(
        body.goal, slots, grounding, body.topic_hints
    )
    try:
        raw, provider_name, model_name = await content_plan.generate_copy(
            db, system_prompt, user_prompt,
            account_id=account_id, user_id=current_user.id,
            provider=body.provider,
        )
        copy_by_index = content_plan.parse_items(raw, slots)
    except ai_assist.ProviderNotConfigured as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except content_plan.PlanGenerationFailed as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    earliest = min(s["local"] for s in slots).date()
    plan = ContentPlan(
        id=uuid.uuid4(),
        account_id=account_id,
        created_by=current_user.id,
        month=earliest.replace(day=1),
        goal=body.goal,
        grounding=grounding,
        provider=provider_name,
        model=model_name,
        generated_at=datetime.now(timezone.utc),
    )
    db.add(plan)
    await db.flush()

    zone = recurrence.zone(grounding["timezone"])
    for index, slot in enumerate(slots):
        copy = copy_by_index.get(index)
        if copy is None:
            continue
        db.add(ContentPlanItem(
            id=uuid.uuid4(),
            plan_id=plan.id,
            scheduled_local=slot["local"],
            scheduled_at=recurrence.to_utc(slot["local"], zone),
            target_account_ids=[slot["social_account_id"]],
            content=copy["content"],
            hashtags=copy["hashtags"],
            rationale=content_plan.rationale_for(slot, grounding),
            slot_source=slot["slot_source"],
            position=index,
        ))
    await db.flush()
    await db.refresh(plan, ["items"])

    await log_activity(
        db, user_id=current_user.id, account_id=account_id,
        action="ai.calendar_fill", category="ai",
        description=f"Drafted {len(plan.items)} proposal(s) for calendar gaps",
        resource_type="content_plan", resource_id=str(plan.id),
    )

    from app.api.v1.endpoints.ai import _serialise_plan

    return _serialise_plan(plan)
