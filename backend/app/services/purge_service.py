"""Hard-purge service.

Permanently removes users that were soft-deleted (``deleted_at`` set) more
than the configured retention window ago, together with the workspaces they
own and every record scoped to those users/accounts.

Soft delete (setting ``deleted_at``) is what the ``DELETE /users/me`` endpoint
performs. This service is the second, irreversible stage: it satisfies the
"we delete your data within 30 days" promise on the Data Deletion page.

Deletion is done with explicit, dependency-ordered bulk statements because the
schema declares no database-level ``ON DELETE CASCADE``. The order below is
children-before-parents; changing it can raise foreign-key violations.
"""

import logging
from datetime import datetime

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.models.account import Account
from app.models.ai_generation import AIGeneration
from app.models.audit_log import ActivityLog
from app.models.business import Business
from app.models.campaign import Campaign
from app.models.notification import Notification
from app.models.permission import UserPermission
from app.models.platform import SocialAccount, SocialPlatform
from app.models.post import Post
from app.models.post_performance import PostPerformance
from app.models.strategy import Strategy
from app.models.team_member import TeamMember
from app.models.user import User

logger = logging.getLogger(__name__)


def _scope(model, user_ids, account_ids):
    """Build an OR filter matching rows owned by the target users/accounts.

    Returns ``None`` when the model has no matching, populated scope column so
    the caller can skip the statement entirely (an empty ``IN ()`` is wasteful
    and, historically, warning-prone).
    """
    conditions = []
    if user_ids and hasattr(model, "user_id"):
        conditions.append(model.user_id.in_(user_ids))
    if account_ids and hasattr(model, "account_id"):
        conditions.append(model.account_id.in_(account_ids))
    if not conditions:
        return None
    return or_(*conditions)


async def _purge(session: AsyncSession, cutoff: datetime) -> dict:
    """Run the purge inside an existing session (no commit)."""
    # 1. Users soft-deleted before the cutoff.
    user_ids = (
        await session.execute(
            select(User.id).where(
                User.deleted_at.is_not(None),
                User.deleted_at < cutoff,
            )
        )
    ).scalars().all()

    if not user_ids:
        return {"users": 0, "accounts": 0}

    # 2. Workspaces those users own.
    account_ids = (
        await session.execute(
            select(Account.id).where(Account.owner_id.in_(user_ids))
        )
    ).scalars().all()

    # 3. Null out nullable "soft" references from surviving rows so that
    #    deleting the users below does not violate a foreign key. Rows that are
    #    themselves being deleted are unaffected by this no-op.
    await session.execute(
        update(Post)
        .where(Post.approved_by.in_(user_ids))
        .values(approved_by=None)
    )
    await session.execute(
        update(TeamMember)
        .where(TeamMember.invited_by.in_(user_ids))
        .values(invited_by=None)
    )

    # 4. Delete dependent rows, children before parents.
    post_scope = _scope(Post, user_ids, account_ids)
    if post_scope is not None:
        await session.execute(
            delete(PostPerformance).where(
                PostPerformance.post_id.in_(select(Post.id).where(post_scope))
            )
        )
        await session.execute(delete(Post).where(post_scope))

    # campaigns reference strategies; strategies reference businesses.
    ordered_models = [
        Campaign,
        Strategy,
        Business,
        SocialAccount,   # references SocialPlatform
        SocialPlatform,
        AIGeneration,
        Notification,
        ActivityLog,
        UserPermission,
        TeamMember,
    ]
    for model in ordered_models:
        scope = _scope(model, user_ids, account_ids)
        if scope is not None:
            await session.execute(delete(model).where(scope))

    # 5. Finally the parents.
    if account_ids:
        await session.execute(delete(Account).where(Account.id.in_(account_ids)))
    await session.execute(delete(User).where(User.id.in_(user_ids)))

    return {"users": len(user_ids), "accounts": len(account_ids)}


async def purge_soft_deleted_users(
    cutoff: datetime,
    session: AsyncSession | None = None,
) -> dict:
    """Permanently delete users soft-deleted before ``cutoff``.

    If a ``session`` is supplied the work runs within it and the caller owns
    the transaction. Otherwise a short-lived engine/session is created and
    committed here — the mode used by the Celery task, which runs outside the
    request lifecycle and its own event loop.

    Returns a summary dict: ``{"users": <int>, "accounts": <int>}``.
    """
    if session is not None:
        return await _purge(session, cutoff)

    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    maker = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    try:
        async with maker() as owned_session:
            async with owned_session.begin():
                result = await _purge(owned_session, cutoff)
            return result
    finally:
        await engine.dispose()
