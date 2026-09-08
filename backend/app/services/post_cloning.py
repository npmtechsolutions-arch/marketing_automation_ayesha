"""Copying a post's content onto a new post.

One implementation, used by "duplicate" in the UI and by every occurrence a
recurring schedule materialises. The endpoint used to have its own inline copy
that listed thirteen fields by hand, which meant it silently dropped the
per-platform settings added in 1.7 and every PostVariant row -- a duplicated
Instagram Reel came back as a plain feed post, and a carefully tailored
per-platform variant vanished without a message.

The fields are derived from the table rather than listed, so a column added
later is copied by default. The interesting list is the *exclusions*: what
belongs to one occurrence and must not be inherited.
"""

import logging
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.post import Post, PostStatus
from app.models.post_variant import PostVariant

logger = logging.getLogger(__name__)

# Identity and bookkeeping. Never copied.
_IDENTITY = {"id", "created_at", "updated_at", "deleted_at"}

# State belonging to one particular run of one particular post. Copying any of
# these would make the new post claim the original's history: a copy that is
# already "published", already approved, or already carries the original's
# platform post ids and error messages.
_PER_OCCURRENCE = {
    "status",
    "scheduled_at",
    "published_at",
    "posting_results",
    "error_message",
    "retry_count",
    "approved_by",
    "approved_at",
    "rejection_reason",
    "assigned_to",
    "due_at",
}

_EXCLUDED = _IDENTITY | _PER_OCCURRENCE

# Ownership, which the caller decides rather than inherits.
_OVERRIDABLE = {"user_id", "account_id"}


def content_fields() -> list[str]:
    """Every column that carries content rather than state."""
    return [
        column.name
        for column in Post.__table__.columns
        if column.name not in _EXCLUDED and column.name not in _OVERRIDABLE
    ]


async def clone_post(
    db: AsyncSession,
    original: Post,
    *,
    user_id: uuid.UUID,
    account_id: Optional[uuid.UUID] = None,
    status: PostStatus = PostStatus.DRAFT,
    scheduled_at=None,
    copy_variants: bool = True,
) -> Post:
    """A new post carrying the original's content and nothing of its history.

    ``copy_variants`` is on by default because a variant *is* content: a post
    whose LinkedIn version was rewritten for a professional audience is not
    the same post without it, and silently publishing the generic text to
    LinkedIn is worse than refusing to copy at all.
    """
    values = {name: getattr(original, name) for name in content_fields()}

    # JSON columns hand back the same object the original holds. Sharing it
    # would mean editing the copy's media list edits the original's -- and,
    # because a plain JSON column has no change tracking, doing so on the
    # original would not even be saved. Shallow-copy the containers.
    for key, value in list(values.items()):
        if isinstance(value, dict):
            values[key] = dict(value)
        elif isinstance(value, list):
            values[key] = [dict(item) if isinstance(item, dict) else item for item in value]

    clone = Post(
        id=uuid.uuid4(),
        user_id=user_id,
        account_id=account_id or original.account_id,
        status=status,
        scheduled_at=scheduled_at,
        **values,
    )
    db.add(clone)
    await db.flush()

    if copy_variants:
        variants = (
            await db.execute(
                select(PostVariant).where(PostVariant.post_id == original.id)
            )
        ).scalars().all()
        for variant in variants:
            db.add(
                PostVariant(
                    id=uuid.uuid4(),
                    post_id=clone.id,
                    platform_slug=variant.platform_slug,
                    content=variant.content,
                    media=list(variant.media) if variant.media else variant.media,
                    alt_texts=dict(variant.alt_texts) if variant.alt_texts else variant.alt_texts,
                    first_comment=variant.first_comment,
                    link_url=variant.link_url,
                    thumbnail_media_id=variant.thumbnail_media_id,
                )
            )
        if variants:
            await db.flush()

    return clone
