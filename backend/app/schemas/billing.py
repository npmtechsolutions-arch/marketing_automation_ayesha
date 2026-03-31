from datetime import datetime

from pydantic import BaseModel


class CheckoutSession(BaseModel):
    price_id: str
    success_url: str
    cancel_url: str


class BillingInfo(BaseModel):
    subscription_tier: str
    subscription_status: str
    current_period_end: datetime | None = None
    stripe_customer_id: str | None = None


class InvoiceResponse(BaseModel):
    id: str
    amount: float
    currency: str
    status: str
    created: datetime
    pdf_url: str | None = None
