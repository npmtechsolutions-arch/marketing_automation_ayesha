"""FastAPI dependencies that spend entitlements.

Kept apart from ``app.services.entitlement_service`` so the service stays a
plain library: the endpoints depend on these, the service depends on nothing
from FastAPI's request cycle, and the tests can drive the service directly.
"""

import uuid

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.services import entitlement_service as ent


async def meter_ai_request(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> None:
    """Charge one AI request against the organization's monthly allowance.

    Applied to the whole AI router. Spent *before* the provider is called: a
    generation that fails downstream has still cost us the call, and metering
    afterwards would let a caller retry a failing request without limit.

    The commit is what makes that true. ``get_db`` rolls the session back on
    any exception, so without it every request that ended in an error -- a 404,
    a provider timeout, a validation failure raised after the model had already
    been billed -- would silently refund its own increment, and a caller could
    spend the provider budget without ever moving the counter. Nothing else is
    pending in the session at this point: dependencies run before the endpoint
    body, so this commits the increment and nothing more.
    """
    organization = await ent.get_organization_for_account(db, account_id)
    await ent.check_and_increment(db, organization, ent.AI_REQUESTS_PER_MONTH)
    await db.commit()
