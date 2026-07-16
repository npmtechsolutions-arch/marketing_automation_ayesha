"""Manually run the soft-deleted-user hard purge.

Mirrors the scheduled Celery task (``app.workers.tasks.purge_soft_deleted_users``)
but runs inline, so it works in environments without Redis/Celery. Useful for
ops, testing, or a one-off cleanup.

Usage:
    python purge_deleted_users.py                # use configured retention window
    python purge_deleted_users.py --days 30      # override retention window
    python purge_deleted_users.py --dry-run      # report what would be purged
"""

import argparse
import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.account import Account
from app.models.user import User
from app.services.purge_service import purge_soft_deleted_users


async def _dry_run(cutoff: datetime) -> None:
    async with AsyncSessionLocal() as session:
        user_ids = (
            await session.execute(
                select(User.id, User.email, User.deleted_at).where(
                    User.deleted_at.is_not(None),
                    User.deleted_at < cutoff,
                )
            )
        ).all()
        account_count = 0
        if user_ids:
            ids = [u[0] for u in user_ids]
            account_count = len(
                (
                    await session.execute(
                        select(Account.id).where(Account.owner_id.in_(ids))
                    )
                ).scalars().all()
            )
        print(f"[dry-run] {len(user_ids)} user(s) eligible for purge, "
              f"{account_count} owned account(s):")
        for _id, email, deleted_at in user_ids:
            print(f"  - {email} (deleted_at={deleted_at.isoformat()})")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Hard-purge soft-deleted users.")
    parser.add_argument(
        "--days",
        type=int,
        default=settings.SOFT_DELETE_RETENTION_DAYS,
        help="Retention window in days (default: SOFT_DELETE_RETENTION_DAYS).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report eligible users without deleting anything.",
    )
    args = parser.parse_args()

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)

    if args.dry_run:
        await _dry_run(cutoff)
        return

    summary = await purge_soft_deleted_users(cutoff)
    print(
        f"Purged {summary['users']} user(s) and {summary['accounts']} "
        f"account(s) soft-deleted before {cutoff.isoformat()}."
    )


if __name__ == "__main__":
    asyncio.run(main())
