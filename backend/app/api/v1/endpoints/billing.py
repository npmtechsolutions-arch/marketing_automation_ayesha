"""Billing and Stripe integration endpoints."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.account import Account, SubscriptionStatus, SubscriptionTier
from app.models.team_member import TeamMember, TeamRole
from app.schemas.billing import (
    BillingInfo,
    CheckoutSession,
    InvoiceResponse,
    PlanChange,
    PlanSummary,
    UsageMetric,
)
from app.schemas.common import MessageResponse
from app.services.entitlements import (
    TIER_LIMITS,
    TIER_NAMES,
    TIER_PRICING,
    TIER_RANK,
    apply_tier as _apply_tier,
    count_connected_platforms,
    count_posts_this_month,
    count_team_members,
)

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


async def _get_account_or_404(account_id: uuid.UUID, db: AsyncSession) -> Account:
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account


def _get_stripe():
    """Lazy-import stripe to avoid hard dependency when key is not set."""
    try:
        import stripe

        stripe.api_key = settings.STRIPE_SECRET_KEY
        return stripe
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Stripe library not installed",
        )


def _tier_price_id(tier: SubscriptionTier) -> str:
    return {
        SubscriptionTier.STARTER: settings.STRIPE_PRICE_STARTER,
        SubscriptionTier.GROWTH: settings.STRIPE_PRICE_GROWTH,
        SubscriptionTier.PRO: settings.STRIPE_PRICE_PRO,
    }.get(tier, "")


def _parse_tier(value: str) -> SubscriptionTier:
    try:
        return SubscriptionTier(value.strip().lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown subscription tier '{value}'",
        )


def _stripe_enabled() -> bool:
    return bool(settings.STRIPE_SECRET_KEY)


def _manual_plan_change_enabled() -> bool:
    """Whether a tier may be switched without a Stripe payment.

    Explicitly opt-in via BILLING_ALLOW_MANUAL_PLAN_CHANGE, or implicitly for a
    local DEBUG run that has no Stripe credentials at all (so the plan flow is
    usable in development). Never true for a production deployment.
    """
    if settings.BILLING_ALLOW_MANUAL_PLAN_CHANGE:
        return True
    return settings.DEBUG and not _stripe_enabled()


def _plan_catalog() -> list[PlanSummary]:
    plans: list[PlanSummary] = []
    for tier in sorted(TIER_RANK, key=lambda t: TIER_RANK[t]):
        limits = TIER_LIMITS[tier]
        monthly, annual = TIER_PRICING[tier]
        plans.append(
            PlanSummary(
                id=tier.value,
                name=TIER_NAMES[tier],
                rank=TIER_RANK[tier],
                monthly_price=monthly,
                annual_price=annual,
                posts=limits["posts"],
                members=limits["members"],
                platforms=limits["platforms"],
                purchasable=bool(_tier_price_id(tier)),
                contact_sales=tier is SubscriptionTier.ENTERPRISE,
            )
        )
    return plans


async def _get_usage(account: Account, db: AsyncSession) -> dict[str, UsageMetric]:
    """Current-period consumption, counted exactly as the limits are enforced."""
    return {
        "posts": UsageMetric(
            used=await count_posts_this_month(db, account.id),
            limit=account.monthly_post_limit,
        ),
        "members": UsageMetric(
            used=await count_team_members(db, account.id),
            limit=account.max_team_members,
        ),
        "platforms": UsageMetric(
            used=await count_connected_platforms(db, account.id),
            limit=account.max_platforms,
        ),
    }


async def _build_billing_info(account: Account, db: AsyncSession) -> BillingInfo:
    current_period_end = None
    cancel_at_period_end = False
    if account.stripe_subscription_id and _stripe_enabled():
        try:
            stripe = _get_stripe()
            subscription = stripe.Subscription.retrieve(account.stripe_subscription_id)
            current_period_end = datetime.fromtimestamp(
                subscription.current_period_end, tz=timezone.utc
            )
            cancel_at_period_end = bool(subscription.get("cancel_at_period_end"))
        except Exception:
            pass  # Gracefully fall back

    return BillingInfo(
        subscription_tier=account.subscription_tier.value,
        subscription_status=account.subscription_status.value,
        current_period_end=current_period_end,
        stripe_customer_id=account.stripe_customer_id,
        cancel_at_period_end=cancel_at_period_end,
        stripe_enabled=_stripe_enabled(),
        manual_plan_change_enabled=_manual_plan_change_enabled(),
        usage=await _get_usage(account, db),
        plans=_plan_catalog(),
    )


# ---------------------------------------------------------------------------
# Response extras
# ---------------------------------------------------------------------------

class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


class PortalResponse(BaseModel):
    portal_url: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/", response_model=BillingInfo)
async def get_billing_info(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Get billing information, live usage and the plan catalog for the account."""
    await _verify_account_access(account_id, current_user, db)
    account = await _get_account_or_404(account_id, db)
    return await _build_billing_info(account, db)


@router.get("/plans", response_model=list[PlanSummary])
async def list_plans(current_user=Depends(get_current_active_user)):
    """The subscription tiers offered, in upgrade order."""
    return _plan_catalog()


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    account_id: uuid.UUID,
    body: CheckoutSession,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Create a Stripe Checkout session for a subscription upgrade."""
    await _verify_account_access(account_id, current_user, db, min_role=TeamRole.ADMIN)
    account = await _get_account_or_404(account_id, db)

    if not _stripe_enabled():
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Stripe is not configured. Set STRIPE_SECRET_KEY.",
        )

    # SECURITY: resolve the price server-side. A caller may name a tier, or pass
    # a price id only if it is one this deployment actually sells — otherwise a
    # client could check out against any (e.g. $0) price in the Stripe account.
    configured_prices = {
        pid
        for pid in (
            settings.STRIPE_PRICE_STARTER,
            settings.STRIPE_PRICE_GROWTH,
            settings.STRIPE_PRICE_PRO,
        )
        if pid
    }
    if body.tier:
        tier = _parse_tier(body.tier)
        price_id = _tier_price_id(tier)
        if not price_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"The {TIER_NAMES.get(tier, body.tier)} plan is not available for online purchase.",
            )
    elif body.price_id and body.price_id in configured_prices:
        price_id = body.price_id
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid plan tier is required to start checkout.",
        )

    stripe = _get_stripe()

    # Create or retrieve Stripe customer
    if not account.stripe_customer_id:
        customer = stripe.Customer.create(
            email=current_user.email,
            name=current_user.full_name,
            metadata={"account_id": str(account.id)},
        )
        account.stripe_customer_id = customer.id
        await db.flush()

    success_url = body.success_url or f"{settings.FRONTEND_URL}/billing?checkout=success"
    cancel_url = body.cancel_url or f"{settings.FRONTEND_URL}/billing?checkout=cancelled"

    try:
        session = stripe.checkout.Session.create(
            customer=account.stripe_customer_id,
            payment_method_types=["card"],
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"account_id": str(account.id)},
        )
        return CheckoutResponse(checkout_url=session.url, session_id=session.id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to create checkout session: {exc}")


@router.post("/change-plan", response_model=BillingInfo)
async def change_plan(
    account_id: uuid.UUID,
    body: PlanChange,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Switch the account's plan directly, without a Stripe payment.

    Only available on deployments that opt in (see
    BILLING_ALLOW_MANUAL_PLAN_CHANGE) — on a Stripe-backed deployment the tier
    is owned by Stripe and only the webhook may change it.
    """
    await _verify_account_access(account_id, current_user, db, min_role=TeamRole.ADMIN)
    account = await _get_account_or_404(account_id, db)

    if not _manual_plan_change_enabled():
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                "Plan changes go through Stripe Checkout on this deployment."
                if _stripe_enabled()
                else "Billing is not configured. Set STRIPE_SECRET_KEY, or enable "
                "BILLING_ALLOW_MANUAL_PLAN_CHANGE for a demo deployment."
            ),
        )

    tier = _parse_tier(body.tier)
    if tier is SubscriptionTier.ENTERPRISE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The Enterprise plan is arranged with sales.",
        )
    if tier is account.subscription_tier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You are already on the {TIER_NAMES[tier]} plan.",
        )

    _apply_tier(account, tier)
    account.subscription_status = SubscriptionStatus.ACTIVE
    await db.flush()
    return await _build_billing_info(account, db)


@router.post("/portal", response_model=PortalResponse)
async def create_portal_session(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Create a Stripe Customer Portal session for managing subscriptions."""
    await _verify_account_access(account_id, current_user, db, min_role=TeamRole.ADMIN)
    account = await _get_account_or_404(account_id, db)

    if not account.stripe_customer_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No Stripe customer found for this account")

    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Stripe is not configured")

    stripe = _get_stripe()
    try:
        session = stripe.billing_portal.Session.create(
            customer=account.stripe_customer_id,
            return_url=f"{settings.FRONTEND_URL}/billing",
        )
        return PortalResponse(portal_url=session.url)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to create portal session: {exc}")


@router.get("/invoices", response_model=list[InvoiceResponse])
async def list_invoices(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """List invoices for the account from Stripe."""
    await _verify_account_access(account_id, current_user, db)
    account = await _get_account_or_404(account_id, db)

    if not account.stripe_customer_id or not settings.STRIPE_SECRET_KEY:
        return []

    stripe = _get_stripe()
    try:
        invoices = stripe.Invoice.list(customer=account.stripe_customer_id, limit=50)
        return [
            InvoiceResponse(
                id=inv.id,
                amount=inv.amount_due / 100.0,  # Stripe amounts are in cents
                currency=inv.currency,
                status=inv.status or "unknown",
                created=datetime.fromtimestamp(inv.created, tz=timezone.utc),
                pdf_url=inv.invoice_pdf,
            )
            for inv in invoices.data
        ]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Stripe Webhook (no auth required)
# ---------------------------------------------------------------------------

def _price_to_tier(price_id: str) -> SubscriptionTier:
    mapping = {
        settings.STRIPE_PRICE_STARTER: SubscriptionTier.STARTER,
        settings.STRIPE_PRICE_GROWTH: SubscriptionTier.GROWTH,
        settings.STRIPE_PRICE_PRO: SubscriptionTier.PRO,
    }
    return mapping.get(price_id, SubscriptionTier.STARTER)


@router.post("/webhook", include_in_schema=True)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    stripe_signature: str | None = Header(None, alias="Stripe-Signature"),
):
    """Handle Stripe webhook events. No authentication required - verified via signature."""
    payload = await request.body()

    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Stripe not configured")

    stripe = _get_stripe()

    # SECURITY: webhook events mutate billing state (subscription tier/limits),
    # so they MUST be authenticated by their Stripe signature. Never fall back
    # to parsing the raw body — an attacker who omits the signature header (or
    # when the secret is unset) could otherwise forge events, e.g. grant their
    # own account a paid tier.
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Stripe webhook secret not configured",
        )
    if not stripe_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe-Signature header",
        )
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

    event_type = event.get("type") if isinstance(event, dict) else event.type
    data_object = event.get("data", {}).get("object", {}) if isinstance(event, dict) else event.data.object

    # Handle subscription events
    if event_type == "checkout.session.completed":
        account_id_str = (
            data_object.get("metadata", {}).get("account_id")
            if isinstance(data_object, dict)
            else data_object.metadata.get("account_id")
        )
        subscription_id = (
            data_object.get("subscription")
            if isinstance(data_object, dict)
            else data_object.subscription
        )
        if account_id_str:
            result = await db.execute(
                select(Account).where(Account.id == uuid.UUID(account_id_str))
            )
            account = result.scalar_one_or_none()
            if account and subscription_id:
                account.stripe_subscription_id = subscription_id
                account.subscription_status = SubscriptionStatus.ACTIVE

                # Determine tier from the subscription line items
                try:
                    sub = stripe.Subscription.retrieve(subscription_id)
                    price_id = sub["items"]["data"][0]["price"]["id"]
                    _apply_tier(account, _price_to_tier(price_id))
                except Exception:
                    pass

                await db.flush()

    elif event_type == "customer.subscription.updated":
        sub_id = data_object.get("id") if isinstance(data_object, dict) else data_object.id
        sub_status = data_object.get("status") if isinstance(data_object, dict) else data_object.status

        result = await db.execute(
            select(Account).where(Account.stripe_subscription_id == sub_id)
        )
        account = result.scalar_one_or_none()
        if account:
            status_mapping = {
                "active": SubscriptionStatus.ACTIVE,
                "past_due": SubscriptionStatus.PAST_DUE,
                "canceled": SubscriptionStatus.CANCELLED,
                "trialing": SubscriptionStatus.TRIALING,
            }
            account.subscription_status = status_mapping.get(sub_status, SubscriptionStatus.ACTIVE)

            # A plan switch made in the Stripe customer portal arrives as an
            # update, not a new checkout — re-read the tier from the line items
            # so the account's plan and limits do not go stale.
            try:
                items = (
                    data_object.get("items", {}).get("data", [])
                    if isinstance(data_object, dict)
                    else data_object["items"]["data"]
                )
                price_id = items[0]["price"]["id"]
                if price_id:
                    _apply_tier(account, _price_to_tier(price_id))
            except Exception:
                pass

            await db.flush()

    elif event_type == "customer.subscription.deleted":
        sub_id = data_object.get("id") if isinstance(data_object, dict) else data_object.id
        result = await db.execute(
            select(Account).where(Account.stripe_subscription_id == sub_id)
        )
        account = result.scalar_one_or_none()
        if account:
            account.subscription_status = SubscriptionStatus.CANCELLED
            _apply_tier(account, SubscriptionTier.FREE)
            account.stripe_subscription_id = None
            await db.flush()

    elif event_type == "invoice.payment_failed":
        customer_id = data_object.get("customer") if isinstance(data_object, dict) else data_object.customer
        result = await db.execute(
            select(Account).where(Account.stripe_customer_id == customer_id)
        )
        account = result.scalar_one_or_none()
        if account:
            account.subscription_status = SubscriptionStatus.PAST_DUE
            await db.flush()

    return {"status": "ok"}
