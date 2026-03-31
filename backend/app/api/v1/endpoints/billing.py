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
from app.schemas.billing import BillingInfo, CheckoutSession, InvoiceResponse
from app.schemas.common import MessageResponse

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
    """Get billing information for the account."""
    await _verify_account_access(account_id, current_user, db)
    account = await _get_account_or_404(account_id, db)

    # If Stripe is configured, fetch subscription details
    current_period_end = None
    if account.stripe_subscription_id and settings.STRIPE_SECRET_KEY:
        try:
            stripe = _get_stripe()
            subscription = stripe.Subscription.retrieve(account.stripe_subscription_id)
            current_period_end = datetime.fromtimestamp(
                subscription.current_period_end, tz=timezone.utc
            )
        except Exception:
            pass  # Gracefully fall back

    return BillingInfo(
        subscription_tier=account.subscription_tier.value,
        subscription_status=account.subscription_status.value,
        current_period_end=current_period_end,
        stripe_customer_id=account.stripe_customer_id,
    )


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    account_id: uuid.UUID,
    body: CheckoutSession,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Create a Stripe Checkout session for subscription upgrade."""
    await _verify_account_access(account_id, current_user, db, min_role=TeamRole.ADMIN)
    account = await _get_account_or_404(account_id, db)

    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Stripe is not configured. Set STRIPE_SECRET_KEY.",
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
    else:
        customer_id = account.stripe_customer_id

    try:
        session = stripe.checkout.Session.create(
            customer=account.stripe_customer_id,
            payment_method_types=["card"],
            mode="subscription",
            line_items=[{"price": body.price_id, "quantity": 1}],
            success_url=body.success_url,
            cancel_url=body.cancel_url,
            metadata={"account_id": str(account.id)},
        )
        return CheckoutResponse(checkout_url=session.url, session_id=session.id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to create checkout session: {exc}")


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
            return_url=f"{settings.FRONTEND_URL}/settings/billing",
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

TIER_LIMITS = {
    SubscriptionTier.FREE: {"posts": 10, "members": 1, "platforms": 2},
    SubscriptionTier.STARTER: {"posts": 50, "members": 3, "platforms": 5},
    SubscriptionTier.GROWTH: {"posts": 200, "members": 10, "platforms": 8},
    SubscriptionTier.PRO: {"posts": 1000, "members": 25, "platforms": 8},
    SubscriptionTier.ENTERPRISE: {"posts": 99999, "members": 100, "platforms": 8},
}


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

    # Verify webhook signature
    if settings.STRIPE_WEBHOOK_SECRET and stripe_signature:
        try:
            event = stripe.Webhook.construct_event(
                payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
            )
        except stripe.error.SignatureVerificationError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")
    else:
        import json

        event = json.loads(payload)

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
                    tier = _price_to_tier(price_id)
                    limits = TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.STARTER])
                    account.subscription_tier = tier
                    account.monthly_post_limit = limits["posts"]
                    account.max_team_members = limits["members"]
                    account.max_platforms = limits["platforms"]
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
            await db.flush()

    elif event_type == "customer.subscription.deleted":
        sub_id = data_object.get("id") if isinstance(data_object, dict) else data_object.id
        result = await db.execute(
            select(Account).where(Account.stripe_subscription_id == sub_id)
        )
        account = result.scalar_one_or_none()
        if account:
            account.subscription_status = SubscriptionStatus.CANCELLED
            account.subscription_tier = SubscriptionTier.FREE
            limits = TIER_LIMITS[SubscriptionTier.FREE]
            account.monthly_post_limit = limits["posts"]
            account.max_team_members = limits["members"]
            account.max_platforms = limits["platforms"]
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
