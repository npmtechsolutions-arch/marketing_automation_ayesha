"""Helper for recording ActivityLog entries.

Activity logging is best-effort: it must never break the user action it is
recording. Every write runs inside a SAVEPOINT (``begin_nested``) so that if the
insert fails, only the savepoint is rolled back and the caller's main
transaction survives intact.
"""

import logging
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import ActivityLog

logger = logging.getLogger(__name__)


async def log_activity(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    account_id: Optional[uuid.UUID],
    action: str,
    category: str,
    description: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    resource_name: Optional[str] = None,
    status: str = "success",
) -> None:
    """Record a single activity log entry.

    Does not commit — the entry participates in (and is committed by) the
    caller's transaction. Any failure is swallowed and logged so activity
    tracking can never break the underlying operation.
    """
    try:
        async with db.begin_nested():
            db.add(
                ActivityLog(
                    user_id=user_id,
                    account_id=account_id,
                    action=action,
                    category=category,
                    description=description,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    resource_name=resource_name,
                    status=status,
                )
            )
    except Exception:
        logger.exception("Failed to record activity log for action '%s'", action)
