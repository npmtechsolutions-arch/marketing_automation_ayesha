"""Validate a post against each target platform's capabilities.

The composer used to count every platform against a hardcoded 2,200
characters, so someone targeting X was told 2,200 was fine and found out at
publish time that the limit is 280 -- after the post had been scheduled,
approved, and missed its slot.

Errors are structured per platform and per field rather than flattened into a
sentence, because the composer needs to put each one next to the input that
caused it. A single "validation failed" string would send the author hunting
through five tabs.

Every rule reads from the provider's :class:`Capabilities`, so a platform's
limits live in exactly one place -- the connector -- and adding a platform
cannot forget to add its validation.
"""

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import Capabilities, resolve_content, variant_for_slug
from app.connectors.registry import get_provider
from app.models.media import Media, MediaKind
from app.models.platform import SocialAccount

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ValidationError:
    """One problem, addressed to one field of one platform's tab."""

    platform: str
    field: str
    message: str
    # Advisory problems do not block saving. A missing alt text is worth
    # telling an author about; refusing to let them schedule over it would be
    # the tool overruling them.
    severity: str = "error"

    def as_dict(self) -> dict:
        return {
            "platform": self.platform,
            "field": self.field,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass
class PlatformValidation:
    platform: str
    account_names: list[str] = field(default_factory=list)
    errors: list[ValidationError] = field(default_factory=list)
    # What the counter shows, so the composer does not recompute it.
    character_count: int = 0
    character_limit: Optional[int] = None
    media_count: int = 0

    @property
    def ok(self) -> bool:
        return not any(e.severity == "error" for e in self.errors)


def _plain_length(content: str, hashtags: list[str] | None) -> int:
    """Characters as the platform will count them.

    Hashtags are stored separately but published in the body, so a count that
    ignores them under-reports -- and the author discovers the shortfall at
    publish time, which is exactly what this exists to prevent.

    This does *not* model X's URL shortening (every link counts as 23
    characters regardless of length). That would make the counter optimistic
    where being wrong is expensive, so links are counted in full: the estimate
    errs toward refusing a post that would have fit, not accepting one that
    will not.
    """
    body = content or ""
    for tag in hashtags or []:
        token = tag if tag.startswith("#") else f"#{tag}"
        if token not in body:
            body += f" {token}"
    return len(body)


def _validate_one(
    slug: str,
    caps: Capabilities,
    content,
    media_rows: dict[uuid.UUID, Media],
) -> PlatformValidation:
    result = PlatformValidation(
        platform=slug,
        character_limit=caps.max_chars,
        character_count=_plain_length(content.content, content.hashtags),
    )

    resolved_media = [
        media_rows[mid]
        for mid in _as_ids(content.media_urls)
        if mid in media_rows
    ]
    result.media_count = len(resolved_media)
    images = [m for m in resolved_media if m.kind is MediaKind.IMAGE]
    videos = [m for m in resolved_media if m.kind is MediaKind.VIDEO]

    def fail(field_name: str, message: str, severity: str = "error") -> None:
        result.errors.append(ValidationError(slug, field_name, message, severity))

    # -- text ---------------------------------------------------------------
    if caps.max_chars is not None and result.character_count > caps.max_chars:
        over = result.character_count - caps.max_chars
        fail(
            "content",
            f"{over} character{'s' if over != 1 else ''} over the "
            f"{caps.max_chars:,} limit for {slug}.",
        )
    if not (content.content or "").strip() and not resolved_media:
        fail("content", f"{slug} needs text or media -- this would post nothing.")

    # -- media --------------------------------------------------------------
    if images and not caps.supports_images:
        fail(
            "media",
            f"{slug} cannot publish images through this integration; they "
            "would be dropped silently.",
        )
    if videos and not caps.supports_video:
        fail("media", f"{slug} cannot publish video through this integration.")
    if caps.requires_video and not videos:
        fail(
            "media",
            f"{slug} publishes video only -- a post without one cannot be "
            "sent there at all.",
        )
    if len(images) > caps.max_images:
        if caps.max_images == 0:
            fail("media", f"{slug} does not accept images.")
        else:
            fail(
                "media",
                f"{len(images)} images, but {slug} accepts at most "
                f"{caps.max_images}.",
            )
    if len(videos) > 1:
        fail("media", f"{slug} accepts one video per post, not {len(videos)}.")
    if videos and images:
        fail(
            "media",
            f"{slug} cannot mix video and images in one post.",
        )

    for video in videos:
        if (
            caps.max_video_seconds is not None
            and video.duration_seconds
            and video.duration_seconds > caps.max_video_seconds
        ):
            fail(
                "media",
                f"'{video.filename}' is {int(video.duration_seconds)}s; "
                f"{slug} allows {caps.max_video_seconds}s.",
            )
        if (
            caps.max_video_bytes is not None
            and video.size_bytes > caps.max_video_bytes
        ):
            fail(
                "media",
                f"'{video.filename}' is "
                f"{video.size_bytes // (1024 * 1024)}MB; {slug} allows "
                f"{caps.max_video_bytes // (1024 * 1024)}MB.",
            )

    # -- links --------------------------------------------------------------
    if content.link_url and not caps.supports_link_posts:
        fail(
            "link_url",
            f"A link will not be clickable on {slug}.",
            severity="warning",
        )

    # -- accessibility ------------------------------------------------------
    missing_alt = [
        m.filename
        for m in images
        if not (content.alt_texts or {}).get(str(m.id)) and not m.alt_text
    ]
    if missing_alt:
        fail(
            "alt_texts",
            f"No alt text for {', '.join(missing_alt[:3])}"
            + ("…" if len(missing_alt) > 3 else "")
            + ". Screen readers will announce nothing.",
            severity="warning",
        )

    # -- first comment ------------------------------------------------------
    if content.first_comment and not caps.supports_comments_api:
        fail(
            "first_comment",
            f"{slug} has no comments API, so a first comment cannot be posted "
            "automatically.",
        )

    return result


def _as_ids(values: list) -> list[uuid.UUID]:
    """Media ids from a variant's list, ignoring anything that is not one.

    A variant stores ids; the master post's ``media_urls`` stores URLs. Both
    reach here, and only the ids can be validated against real files -- a
    pasted external URL is outside our knowledge, so it is skipped rather than
    reported as broken.
    """
    ids = []
    for value in values or []:
        try:
            ids.append(uuid.UUID(str(value)))
        except (ValueError, TypeError, AttributeError):
            continue
    return ids


async def validate_post(
    db: AsyncSession, post: Any, *, account_id: uuid.UUID
) -> dict:
    """Validate a post against every platform it targets.

    Returns the per-platform breakdown the composer renders, including the
    character counts so it does not have to reimplement them.
    """
    targets = post.target_accounts or []
    social_ids = _as_ids([t.get("social_account_id") for t in targets])

    accounts = (
        (
            await db.execute(
                select(SocialAccount).where(SocialAccount.id.in_(social_ids))
            )
        ).scalars().all()
        if social_ids
        else []
    )

    # Group by platform: two X accounts on one post share one variant and one
    # set of rules, so validating twice would report every problem twice.
    by_platform: dict[str, list[SocialAccount]] = {}
    for account in accounts:
        slug = get_provider(
            account.platform.slug if account.platform else None
        ).slug
        by_platform.setdefault(slug, []).append(account)

    # Every media id any platform might use, in one query.
    wanted: set[uuid.UUID] = set(_as_ids(post.media_urls))
    for variant in getattr(post, "variants", None) or []:
        wanted.update(_as_ids(variant.media or []))
    media_rows = {
        row.id: row
        for row in (
            (
                await db.execute(
                    select(Media).where(
                        Media.id.in_(wanted),
                        Media.account_id == account_id,
                        Media.deleted_at.is_(None),
                    )
                )
            ).scalars().all()
            if wanted
            else []
        )
    }

    results: list[PlatformValidation] = []
    for slug, slug_accounts in sorted(by_platform.items()):
        provider = get_provider(slug)
        content = resolve_content(post, slug, variant_for_slug(post, slug))
        validation = _validate_one(slug, provider.capabilities, content, media_rows)
        validation.account_names = [a.account_name for a in slug_accounts]
        results.append(validation)

    if not results:
        return {
            "valid": False,
            "platforms": [],
            "errors": [
                ValidationError(
                    platform="",
                    field="target_accounts",
                    message="Choose at least one account to publish to.",
                ).as_dict()
            ],
        }

    all_errors = [e.as_dict() for r in results for e in r.errors]
    return {
        "valid": all(r.ok for r in results),
        "platforms": [
            {
                "platform": r.platform,
                "accounts": r.account_names,
                "ok": r.ok,
                "character_count": r.character_count,
                "character_limit": r.character_limit,
                "media_count": r.media_count,
                "errors": [e.as_dict() for e in r.errors],
            }
            for r in results
        ],
        "errors": all_errors,
    }
