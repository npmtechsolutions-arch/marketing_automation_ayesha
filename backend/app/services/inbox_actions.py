"""What a team does to a thread: reply, assign, note, tag, resolve.

The reply is the only one that leaves the building, and it is deliberately
ordered: the provider call happens **first**, and the local message row is
written only if the platform accepted it. The other order -- optimistic write,
then send -- leaves a reply visible in our inbox that the customer never
received, which is worse than an error the sender can see.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import NotSupportedError
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

MAX_TAGS = 20
MAX_TAG_LENGTH = 40


class ReplyNotSupported(Exception):
    """This platform, or this thread type, cannot be replied to from here."""


class ReplyFailed(Exception):
    """The platform refused the reply."""


async def reply(
    db: AsyncSession,
    thread: InboxThread,
    connection: SocialAccount,
    *,
    body: str,
    user_id: uuid.UUID,
) -> InboxMessage:
    """Send a reply through the provider, then record it."""
    slug = connection.platform.slug if connection.platform else None
    provider = get_provider(slug)

    try:
        if thread.type is ThreadType.DM:
            recipient = thread.participant_handle
            if not recipient:
                raise ReplyNotSupported(
                    "This conversation has no participant id to reply to."
                )
            result = await provider.send_message(connection, recipient, body)
        elif thread.type is ThreadType.COMMENT:
            target = await _last_inbound_external_id(db, thread) or thread.external_id
            result = await provider.reply_to_comment(connection, target, body)
        else:
            # A mention lives on someone else's post. Replying means composing
            # a new public post, which is the composer's job, not the inbox's.
            raise ReplyNotSupported(
                "Mentions are replied to by posting publicly, not from the inbox."
            )
    except NotSupportedError as exc:
        raise ReplyNotSupported(
            f"{slug} does not support replying to {thread.type.value}s from here."
        ) from exc
    except ReplyNotSupported:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("Inbox reply failed on %s: %s", slug, exc)
        raise ReplyFailed(str(exc)[:300]) from exc

    external = str(
        (result or {}).get("external_id") or f"local_{uuid.uuid4().hex}"
    )
    now = datetime.now(timezone.utc)
    message = InboxMessage(
        id=uuid.uuid4(),
        thread_id=thread.id,
        direction=MessageDirection.OUTBOUND,
        external_id=external,
        author="You",
        author_user_id=user_id,
        body=body,
        created_at=now,
    )
    db.add(message)

    thread.last_message_at = now
    thread.last_message_preview = body[:280]
    # Answering is not the same as finishing, so the thread stays open; only an
    # explicit resolve closes it. But it has certainly been read.
    thread.unread_count = 0
    await db.flush()
    return message


async def _last_inbound_external_id(
    db: AsyncSession, thread: InboxThread
) -> Optional[str]:
    """The most recent thing the customer said.

    Replying to the latest comment rather than to the thread root keeps the
    conversation threaded the way the platform displays it.
    """
    return (
        await db.execute(
            select(InboxMessage.external_id)
            .where(
                InboxMessage.thread_id == thread.id,
                InboxMessage.direction == MessageDirection.INBOUND,
            )
            .order_by(InboxMessage.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def add_note(
    db: AsyncSession, thread: InboxThread, *, body: str, user_id: uuid.UUID
) -> InboxMessage:
    """An internal note. Never sent anywhere.

    Stored as a message so it appears in the conversation in the right place --
    a note in a separate list would have to be interleaved by every reader, and
    one of them would eventually get it wrong.
    """
    message = InboxMessage(
        id=uuid.uuid4(),
        thread_id=thread.id,
        direction=MessageDirection.INTERNAL,
        # Notes have no platform id. A locally generated one rather than NULL:
        # two NULLs are distinct in SQL, so the unique constraint would not
        # constrain them.
        external_id=f"note_{uuid.uuid4().hex}",
        author="Internal note",
        author_user_id=user_id,
        body=body,
        created_at=datetime.now(timezone.utc),
    )
    db.add(message)
    # Deliberately does not move last_message_at: the inbox sorts by customer
    # activity, and a team member writing to themselves is not that.
    await db.flush()
    return message


def normalise_tags(raw: Optional[list[str]]) -> list[str]:
    """Trim, lowercase, de-duplicate, and bound.

    Lowercased because "Refund" and "refund" filtering as two tags is how a
    tag list becomes useless within a week.
    """
    seen: list[str] = []
    for value in raw or []:
        tag = str(value).strip().lower()[:MAX_TAG_LENGTH]
        if tag and tag not in seen:
            seen.append(tag)
    return seen[:MAX_TAGS]


async def set_status(
    db: AsyncSession, thread: InboxThread, status: ThreadStatus
) -> InboxThread:
    thread.status = status
    if status is ThreadStatus.RESOLVED:
        thread.unread_count = 0
    await db.flush()
    return thread
