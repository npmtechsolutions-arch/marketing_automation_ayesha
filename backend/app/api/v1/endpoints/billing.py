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
from app.models.organization import Organization
from app.models.subscription_event import SubscriptionEventSource
from app.services import revenue
from app.schemas.billing import (
    BillingInfo,
    CheckoutSession,
    InvoiceResponse,
    PlanChange,
    PlanSummary,
    UsageMetric,
)
from app.models.plan import Plan, PlanFeature
from app.services import entitlement_service as ent
from app.services.entitlements import apply_tier as _apply_tier
from app.core.authz import verify_account_access as _verify_account_access
from app.core.permissions import (
    BILLING_MANAGE,
)

router = APIRouter()


def _subscription_state(organization) -> dict:
    """The tier and status an organization holds right now.

    Captured before a change and handed to ``revenue.record_transition``
    afterwards, so the event log carries both ends of every move rather than
    just where the organization landed.
    """
    return {
        "from_tier": organization.subscription_tier.value,
        "from_status": organization.subscription_status.value,
    }



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_organization_or_404(
    account_id: uuid.UUID, db: AsyncSession
) -> Organization:
    """Resolve the billing entity from the workspace id in the path.

    Billing lives on the Organization now, but the router is still mounted
    under /accounts/{account_id}/billing so the frontend keeps working.
    """
    result = await db.execute(
        select(Organization)
        .join(Account, Account.organization_id == Organization.id)
        .where(Account.id == account_id)
    )
    organization = result.scalar_one_or_none()
    if not organization:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return organization


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

    Explicit opt-in only. This used to also turn itself on for any run with
    DEBUG set and no Stripe key -- two settings that are easy to end up with by
    accident, and the result hands out paid tiers for free. Granting that
    quietly, from a combination nobody chose, is not something a billing
    control should do; it now requires BILLING_ALLOW_MANUAL_PLAN_CHANGE to be
    set explicitly.
    """
    return settings.BILLING_ALLOW_MANUAL_PLAN_CHANGE is True


async def _plan_catalog(db: AsyncSession) -> list[PlanSummary]:
    """The catalog, read from the plans table rather than a literal.

    Editing a plan's price or limits is now a data change; this endpoint
    reflects it without a deploy.
    """
    rows = (
        await db.execute(
            select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.sort_order)
        )
    ).scalars().all()

    plans: list[PlanSummary] = []
    for plan in rows:
        limits = {
            r.feature_key: r.limit_value
            for r in (
                await db.execute(
                    select(PlanFeature).where(PlanFeature.plan_id == plan.id)
                )
            ).scalars().all()
        }
        # -1 stands in for unlimited in the response, since the schema's fields
        # are ints and NULL is how the table spells it.
        def _limit(key: str) -> int:
            value = limits.get(key)
            return -1 if value is None else int(value)

        monthly = float(plan.price_monthly)
        plans.append(
            PlanSummary(
                id=plan.key,
                name=plan.name,
                rank=plan.sort_order,
                monthly_price=monthly,
                # The annual price was a second literal; it is 80% of monthly,
                # which is what the old TIER_PRICING pairs encoded.
                annual_price=round(monthly * 0.8, 2) if monthly else 0.0,
                posts=_limit("posts_per_month"),
                members=_limit("team_members"),
                platforms=_limit("social_accounts"),
                purchasable=bool(plan.stripe_price_id or _tier_price_id_by_key(plan.key)),
                contact_sales=plan.key == SubscriptionTier.ENTERPRISE.value,
            )
        )
    return plans


def _tier_price_id_by_key(key: str) -> str:
    mapping = {
        "starter": settings.STRIPE_PRICE_STARTER,
        "growth": settings.STRIPE_PRICE_GROWTH,
        "pro": settings.STRIPE_PRICE_PRO,
    }
    return (mapping.get(key) or "").strip()


async def _get_usage(organization: Organization, db: AsyncSession) -> dict[str, UsageMetric]:
    """Current-period consumption, counted exactly as the limits are enforced.

    Both halves come from the entitlement service. The limits used to be read
    off denormalised columns on the organization, which stopped being the
    source of truth and could show a customer a cap that enforcement would not
    honour. GET /organizations/{id}/usage reports all nine features; this keeps
    the three the billing page has always shown.
    """
    return {
        "posts": UsageMetric(
            used=await ent.current_usage(db, organization, ent.POSTS_PER_MONTH),
            limit=await ent.get_limit(db, organization, ent.POSTS_PER_MONTH),
        ),
        "members": UsageMetric(
            used=await ent.current_usage(db, organization, ent.TEAM_MEMBERS),
            limit=await ent.get_limit(db, organization, ent.TEAM_MEMBERS),
        ),
        "platforms": UsageMetric(
            used=await ent.current_usage(db, organization, ent.SOCIAL_ACCOUNTS),
            limit=await ent.get_limit(db, organization, ent.SOCIAL_ACCOUNTS),
        ),
    }


async def _build_billing_info(organization: Organization, db: AsyncSession) -> BillingInfo:
    current_period_end = None
    cancel_at_period_end = False
    if organization.stripe_subscription_id and _stripe_enabled():
        try:
            stripe = _get_stripe()
            subscription = stripe.Subscription.retrieve(organization.stripe_subscription_id)
            current_period_end = datetime.fromtimestamp(
                subscription.current_period_end, tz=timezone.utc
            )
            cancel_at_period_end = bool(subscription.get("cancel_at_period_end"))
        except Exception:
            pass  # Gracefully fall back

    return BillingInfo(
        subscription_tier=organization.subscription_tier.value,
        subscription_status=organization.subscription_status.value,
        current_period_end=current_period_end,
        stripe_customer_id=organization.stripe_customer_id,
        cancel_at_period_end=cancel_at_period_end,
        stripe_enabled=_stripe_enabled(),
        manual_plan_change_enabled=_manual_plan_change_enabled(),
        usage=await _get_usage(organization, db),
        plans=await _plan_catalog(db),
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
    """Get billing information, live usage and the plan catalog for the organization."""
    await _verify_account_access(account_id, current_user, db)
    organization = await _get_organization_or_404(account_id, db)
    return await _build_billing_info(organization, db)


@router.get("/plans", response_model=list[PlanSummary])
async def list_plans(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """The subscription tiers offered, in upgrade order."""
    return await _plan_catalog(db)


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    account_id: uuid.UUID,
    body: CheckoutSession,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Create a Stripe Checkout session for a subscription upgrade."""
    await _verify_account_access(account_id, current_user, db, permission=BILLING_MANAGE)
    organization = await _get_organization_or_404(account_id, db)

    if not _stripe_enabled():
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Stripe is not configured. Set STRIPE_SECRET_KEY.",
        )

    # SECURITY: resolve the price server-side. A caller may name a tier, or pass
    # a price id only if it is one this deployment actually sells — otherwise a
    # client could check out against any (e.g. $0) price in the Stripe organization.
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
                detail=f"The {tier.value.title()} plan is not available for online purchase.",
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
    if not organization.stripe_customer_id:
        customer = stripe.Customer.create(
            email=current_user.email,
            name=current_user.full_name,
            metadata={"organization_id": str(organization.id)},
        )
        organization.stripe_customer_id = customer.id
        await db.flush()

    success_url = body.success_url or f"{settings.FRONTEND_URL}/billing?checkout=success"
    cancel_url = body.cancel_url or f"{settings.FRONTEND_URL}/billing?checkout=cancelled"

    try:
        session = stripe.checkout.Session.create(
            customer=organization.stripe_customer_id,
            payment_method_types=["card"],
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"organization_id": str(organization.id)},
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
    await _verify_account_access(account_id, current_user, db, permission=BILLING_MANAGE)
    organization = await _get_organization_or_404(account_id, db)

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
    if tier is organization.subscription_tier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You are already on the {tier.value.title()} plan.",
        )

    before = _subscription_state(organization)
    await _apply_tier(db, organization, tier)
    organization.subscription_status = SubscriptionStatus.ACTIVE
    await revenue.record_transition(
        db, organization, **before,
        source=SubscriptionEventSource.CHECKOUT,
        note="plan change",
    )
    await db.flush()
    return await _build_billing_info(organization, db)


@router.post("/portal", response_model=PortalResponse)
async def create_portal_session(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Create a Stripe Customer Portal session for managing subscriptions."""
    await _verify_account_access(account_id, current_user, db, permission=BILLING_MANAGE)
    organization = await _get_organization_or_404(account_id, db)

    if not organization.stripe_customer_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No Stripe customer found for this account")

    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Stripe is not configured")

    stripe = _get_stripe()
    try:
        session = stripe.billing_portal.Session.create(
            customer=organization.stripe_customer_id,
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
    organization = await _get_organization_or_404(account_id, db)

    if not organization.stripe_customer_id or not settings.STRIPE_SECRET_KEY:
        return []

    stripe = _get_stripe()
    try:
        invoices = stripe.Invoice.list(customer=organization.stripe_customer_id, limit=50)
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
        organization_id_str = (
            data_object.get("metadata", {}).get("account_id")
            if isinstance(data_object, dict)
            else data_object.metadata.get("organization_id")
        )
        subscription_id = (
            data_object.get("subscription")
            if isinstance(data_object, dict)
            else data_object.subscription
        )
        if organization_id_str:
            result = await db.execute(
                select(Organization).where(
                    Organization.id == uuid.UUID(organization_id_str)
                )
            )
            organization = result.scalar_one_or_none()
            if organization and subscription_id:
                before = _subscription_state(organization)
                organization.stripe_subscription_id = subscription_id
                organization.subscription_status = SubscriptionStatus.ACTIVE

                # Determine tier from the subscription line items
                try:
                    sub = stripe.Subscription.retrieve(subscription_id)
                    price_id = sub["items"]["data"][0]["price"]["id"]
                    await _apply_tier(db, organization, _price_to_tier(price_id))
                except Exception:
                    pass

                await revenue.record_transition(
                    db, organization, **before,
                    source=SubscriptionEventSource.WEBHOOK,
                    note=event_type,
                )
                await db.flush()

    elif event_type == "customer.subscription.updated":
        sub_id = data_object.get("id") if isinstance(data_object, dict) else data_object.id
        sub_status = data_object.get("status") if isinstance(data_object, dict) else data_object.status

        result = await db.execute(
            select(Organization).where(Organization.stripe_subscription_id == sub_id)
        )
        organization = result.scalar_one_or_none()
        if organization:
            before = _subscription_state(organization)
            status_mapping = {
                "active": SubscriptionStatus.ACTIVE,
                "past_due": SubscriptionStatus.PAST_DUE,
                "canceled": SubscriptionStatus.CANCELLED,
                "trialing": SubscriptionStatus.TRIALING,
            }
            organization.subscription_status = status_mapping.get(sub_status, SubscriptionStatus.ACTIVE)

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
                    await _apply_tier(db, organization, _price_to_tier(price_id))
            except Exception:
                pass

            await revenue.record_transition(
                db, organization, **before,
                source=SubscriptionEventSource.WEBHOOK,
                note=event_type,
            )
            await db.flush()

    elif event_type == "customer.subscription.deleted":
        sub_id = data_object.get("id") if isinstance(data_object, dict) else data_object.id
        result = await db.execute(
            select(Organization).where(Organization.stripe_subscription_id == sub_id)
        )
        organization = result.scalar_one_or_none()
        if organization:
            before = _subscription_state(organization)
            organization.subscription_status = SubscriptionStatus.CANCELLED
            await _apply_tier(db, organization, SubscriptionTier.FREE)
            organization.stripe_subscription_id = None
            await revenue.record_transition(
                db, organization, **before,
                source=SubscriptionEventSource.WEBHOOK,
                note=event_type,
            )
            await db.flush()

    elif event_type == "invoice.payment_failed":
        customer_id = data_object.get("customer") if isinstance(data_object, dict) else data_object.customer
        result = await db.execute(
            select(Organization).where(Organization.stripe_customer_id == customer_id)
        )
        organization = result.scalar_one_or_none()
        if organization:
            before = _subscription_state(organization)
            organization.subscription_status = SubscriptionStatus.PAST_DUE
            await revenue.record_transition(
                db, organization, **before,
                source=SubscriptionEventSource.WEBHOOK,
                note=event_type,
            )
            await db.flush()

    return {"status": "ok"}
