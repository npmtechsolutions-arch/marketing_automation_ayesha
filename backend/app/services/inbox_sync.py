"""Polling the platforms for comments, messages and mentions.

Polling re-fetches the same items on every pass by design, so **everything here
turns on ``external_id``**. A thread is found or created by the platform's id
for the conversation; a message by the platform's id for the message. Without
that, every poll would duplicate the inbox, and the duplicate would look like
new mail to whoever was watching.

Capability first, call second. A platform whose ``Capabilities`` say it has no
DM API is never asked for one -- and a provider that raises
``NotSupportedError`` anyway is recorded as unsupported rather than as a
failure, because those need different things from the reader: one is a fact
about the platform, the other is a fault to investigate.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.connectors.base import NotSupportedError, PlatformRateLimited
from app.connectors.registry import get_provider
from app.models.inbox import (
    InboxMessage,
    InboxThread,
    MessageDirection,
    ThreadStatus,
    ThreadType,
)
from app.models.platform import SocialAccount

logger = logging.getLogger(__name__)

SYNC_INTERVAL_SECONDS = 5 * 60

# What each thread type is fetched with, and which capability gates it.
SOURCES: tuple[tuple[ThreadType, str, str], ...] = (
    (ThreadType.COMMENT, "get_comments", "supports_comments_api"),
    (ThreadType.DM, "get_messages", "supports_dm_api"),
    (ThreadType.MENTION, "get_mentions", "supports_mentions_api"),
)


def supported_sources(slug: Optional[str]) -> dict[str, bool]:
    """What this platform can offer, for the UI to say so plainly."""
    capabilities = get_provider(slug).capabilities
    return {
        kind.value: bool(getattr(capabilities, flag, False))
        for kind, _, flag in SOURCES
    }


async def _upsert_thread(
    db: AsyncSession,
    connection: SocialAccount,
    kind: ThreadType,
    item: dict[str, Any],
) -> InboxThread:
    """Find this conversation or create it.

    Matched on ``(social_account_id, external_id)`` -- the connection is part
    of the key because two workspaces can follow the same public post, and one
    workspace can connect two accounts on the same platform.
    """
    external = str(item.get("thread_external_id") or item.get("external_id"))
    thread = (
        await db.execute(
            select(InboxThread).where(
                InboxThread.social_account_id == connection.id,
                InboxThread.external_id == external,
            )
        )
    ).scalar_one_or_none()

    if thread is None:
        thread = InboxThread(
            id=uuid.uuid4(),
            account_id=connection.account_id,
            social_account_id=connection.id,
            type=kind,
            external_id=external,
            parent_external_id=(
                item.get("thread_external_id")
                if kind is ThreadType.COMMENT else None
            ),
            participant=item.get("participant") or item.get("author") or "Someone",
            participant_handle=(
                item.get("participant_handle") or item.get("author_handle")
            ),
            permalink=item.get("permalink"),
            status=ThreadStatus.OPEN,
            unread_count=0,
        )
        db.add(thread)
        await db.flush()
    return thread


async def _upsert_message(
    db: AsyncSession, thread: InboxThread, item: dict[str, Any]
) -> bool:
    """Store one message. Returns True only if it was genuinely new.

    An existing message is left exactly as it is rather than updated. A
    platform can re-serve the same comment with a different rendering of the
    author's name, and rewriting it every poll would churn the row and, worse,
    make "has anything happened here" impossible to answer.
    """
    external = str(item.get("external_id"))
    existing = (
        await db.execute(
            select(InboxMessage.id).where(
                InboxMessage.thread_id == thread.id,
                InboxMessage.external_id == external,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return False

    created = item.get("created_at") or datetime.now(timezone.utc)
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)

    db.add(
        InboxMessage(
            id=uuid.uuid4(),
            thread_id=thread.id,
            direction=(
                MessageDirection.OUTBOUND
                if item.get("outbound")
                else MessageDirection.INBOUND
            ),
            external_id=external,
            author=item.get("author") or "Someone",
            author_handle=item.get("author_handle"),
            body=item.get("body") or "",
            media=item.get("media"),
            created_at=created,
        )
    )
    return True


def _touch(thread: InboxThread, item: dict[str, Any], *, inbound: bool) -> None:
    """Move the thread's activity markers forward, never backward.

    A platform can return an older item on a later poll -- a comment edited
    into view, or simply a different page ordering. Letting that rewrite
    ``last_message_at`` would shuffle the inbox under the reader.
    """
    created = item.get("created_at") or datetime.now(timezone.utc)
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)

    # Normalise what came back from the database before comparing. The column
    # is DateTime(timezone=True), which Postgres honours and SQLite does not --
    # comparing a naive value to an aware one raises, and the sync would die on
    # its second pass rather than on its first.
    previous = thread.last_message_at
    if previous is not None and previous.tzinfo is None:
        previous = previous.replace(tzinfo=timezone.utc)

    if previous is None or created > previous:
        thread.last_message_at = created
        thread.last_message_preview = (item.get("body") or "")[:280]
    if inbound:
        thread.unread_count = (thread.unread_count or 0) + 1
        # New inbound mail reopens a resolved thread: a customer who replies
        # to a closed conversation has not been dealt with.
        if thread.status is ThreadStatus.RESOLVED:
            thread.status = ThreadStatus.OPEN


async def sync_connection(db: AsyncSession, connection: SocialAccount) -> dict:
    """Poll one connected account for everything its platform offers."""
    slug = connection.platform.slug if connection.platform else None
    provider = get_provider(slug)
    capabilities = provider.capabilities

    report = {"new_messages": 0, "threads": 0, "unsupported": [], "errors": []}

    for kind, method_name, flag in SOURCES:
        if not getattr(capabilities, flag, False):
            report["unsupported"].append(kind.value)
            continue

        try:
            items = await getattr(provider, method_name)(connection)
        except NotSupportedError:
            # The capability said yes and the provider said no -- usually a
            # connection-level limit, like LinkedIn comments on a personal
            # profile. A fact, not a fault.
            report["unsupported"].append(kind.value)
            continue
        except PlatformRateLimited as exc:
            report["errors"].append(f"{kind.value}: rate limited ({exc})")
            continue
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Inbox sync failed for %s/%s: %s", slug, kind.value, exc
            )
            report["errors"].append(f"{kind.value}: {type(exc).__name__}: {exc}"[:200])
            continue

        seen_threads: set[uuid.UUID] = set()
        for item in items or []:
            if not item.get("external_id"):
                continue
            thread = await _upsert_thread(db, connection, kind, item)
            created = await _upsert_message(db, thread, item)
            if created:
                report["new_messages"] += 1
                _touch(thread, item, inbound=not item.get("outbound"))
            seen_threads.add(thread.id)
        report["threads"] += len(seen_threads)

    await db.flush()
    return report


async def sync_all(db: AsyncSession, *, limit: int = 50) -> dict:
    """One pass over every active connection."""
    connections = (
        await db.execute(
            select(SocialAccount)
            .options(selectinload(SocialAccount.platform))
            .where(SocialAccount.is_active.is_(True))
            .limit(limit)
        )
    ).scalars().all()

    totals = {"connections": 0, "new_messages": 0, "errors": 0}
    for connection in connections:
        try:
            report = await sync_connection(db, connection)
        except Exception:  # noqa: BLE001
            logger.exception("Inbox sync failed for connection %s", connection.id)
            totals["errors"] += 1
            continue
        totals["connections"] += 1
        totals["new_messages"] += report["new_messages"]
        totals["errors"] += len(report["errors"])
    return totals
