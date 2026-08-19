from datetime import datetime

from pydantic import BaseModel


class CheckoutSession(BaseModel):
    """Request body for starting a Stripe Checkout.

    Either ``tier`` (preferred) or ``price_id`` may be supplied. ``price_id`` is
    only accepted when it matches one of the price ids configured on the server,
    so a client can never check out against an arbitrary Stripe price.
    """

    tier: str | None = None
    price_id: str | None = None
    success_url: str | None = None
    cancel_url: str | None = None


class PlanChange(BaseModel):
    """Request body for a direct (non-Stripe) plan change."""

    tier: str


class UsageMetric(BaseModel):
    used: int
    limit: int  # -1 means unlimited


class PlanSummary(BaseModel):
    """One purchasable tier, as advertised to the billing UI."""

    id: str
    name: str
    rank: int
    monthly_price: float
    annual_price: float
    posts: int
    members: int
    platforms: int
    purchasable: bool  # a Stripe price is configured for this tier
    contact_sales: bool = False


class BillingInfo(BaseModel):
    subscription_tier: str
    subscription_status: str
    current_period_end: datetime | None = None
    stripe_customer_id: str | None = None
    cancel_at_period_end: bool = False
    # Whether checkout/portal can actually be started on this deployment.
    stripe_enabled: bool = False
    # Whether the plan may be switched directly, without going through Stripe
    # (development / demo deployments only).
    manual_plan_change_enabled: bool = False
    usage: dict[str, UsageMetric] = {}
    plans: list[PlanSummary] = []


class InvoiceResponse(BaseModel):
    id: str
    amount: float
    currency: str
    status: str
    created: datetime
    pdf_url: str | None = None
