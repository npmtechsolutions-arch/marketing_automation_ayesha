"""Persisting unhandled 5xx responses.

The one thing that matters here: this **must not** reuse the request's database
session. By the time the exception handler runs, that session has usually seen
a failed statement, and on Postgres every subsequent statement in the same
transaction raises ``InFailedSQLTransaction``. Writing the error row through it
would fail, be swallowed, and leave nothing recorded -- and the request that
most needs recording is exactly the one whose session is broken. So this opens
its own.

The second thing: recording an error must never turn a 500 into a worse 500.
Every failure in here is caught and logged, and the handler returns its
response regardless.
"""

import logging
import traceback as traceback_module
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, func, select

from app.models.api_error import (
    MAX_MESSAGE_CHARS,
    MAX_TRACEBACK_CHARS,
    ApiError,
)

logger = logging.getLogger(__name__)

# Kept for a quarter: long enough to spot a slow regression across a release
# cycle, short enough that the table stays queryable without partitioning.
RETENTION_DAYS = 90


def _truncate(text: Optional[str], limit: int) -> Optional[str]:
    """Keep the tail, not the head.

    A traceback's last frames are the ones that raised; its first are the ASGI
    plumbing, identical on every row. Truncating from the front would throw
    away the only part that differs.
    """
    if text is None:
        return None
    if len(text) <= limit:
        return text
    return "...[truncated]\n" + text[-limit:]


async def record(
    request,
    exc: BaseException,
    *,
    status_code: int = 500,
) -> Optional[uuid.UUID]:
    """Write one ApiError row. Returns its id, or None if it could not.

    The id is handed back so the 500 response can carry a reference the user
    can quote in a support ticket, which turns "it broke" into a row lookup.
    """
    # Imported here rather than at module scope: app.core.database pulls in
    # settings and the engine, and this module is imported from main.py while
    # that is still being wired up.
    from app.core.database import AsyncSessionLocal

    try:
        user_id, organization_id = _identity_from(request)
        row = ApiError(
            id=uuid.uuid4(),
            path=str(getattr(request.url, "path", ""))[:500],
            method=str(getattr(request, "method", ""))[:10],
            status_code=status_code,
            exception_class=f"{type(exc).__module__}.{type(exc).__name__}"[:200],
            message=_truncate(str(exc), MAX_MESSAGE_CHARS),
            traceback=_truncate(
                "".join(
                    traceback_module.format_exception(
                        type(exc), exc, exc.__traceback__
                    )
                ),
                MAX_TRACEBACK_CHARS,
            ),
            user_id=user_id,
            organization_id=organization_id,
        )
        async with AsyncSessionLocal() as session:
            session.add(row)
            await session.commit()
        return row.id
    except Exception:  # noqa: BLE001
        # Deliberately broad. Whatever went wrong storing the error, the
        # caller still has a response to return.
        logger.exception("Could not persist an ApiError row")
        return None


def _identity_from(request) -> tuple[Optional[uuid.UUID], Optional[uuid.UUID]]:
    """Who was making the request, if anyone knows.

    Read from ``request.state``, which the auth dependency populates on
    success. An unauthenticated request, or one that blew up before auth ran,
    yields nulls -- which is information rather than a gap: it says the failure
    is not specific to one customer.
    """
    state = getattr(request, "state", None)
    if state is None:
        return None, None

    def _as_uuid(value):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        try:
            return uuid.UUID(str(value))
        except (ValueError, AttributeError, TypeError):
            return None

    user = getattr(state, "user", None)
    return (
        _as_uuid(getattr(user, "id", None) if user is not None else None)
        or _as_uuid(getattr(state, "user_id", None)),
        _as_uuid(getattr(state, "organization_id", None)),
    )


async def prune(db, *, days: int = RETENTION_DAYS) -> int:
    """Drop error rows older than the retention window."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(delete(ApiError).where(ApiError.created_at < cutoff))
    deleted = result.rowcount or 0
    if deleted:
        logger.info("Pruned %s api_errors rows older than %s days", deleted, days)
    return deleted


async def count_since(db, since: datetime) -> int:
    """How many errors since a moment. Used by the admin overview."""
    return (
        await db.execute(
            select(func.count()).select_from(ApiError).where(ApiError.created_at >= since)
        )
    ).scalar_one()
