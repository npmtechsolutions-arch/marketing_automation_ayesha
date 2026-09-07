"""Slug to provider resolution.

Replaces four separate ``if "facebook" in slug ... elif`` chains that had drifted
apart: publishing covered five platforms, pre-publish token refresh covered two,
and account verification and manual refresh each had their own shape. There is
now one place that knows how a slug maps to behaviour.

Providers are stateless and shared: they hold no per-request data, so one
instance each is created at import and reused.
"""

import logging

from app.connectors.base import Capabilities, SocialProvider
from app.connectors.facebook import FacebookProvider
from app.connectors.instagram import InstagramProvider
from app.connectors.linkedin import LinkedInProvider
from app.connectors.twitter import TwitterProvider
from app.connectors.youtube import YouTubeProvider

logger = logging.getLogger(__name__)

_PROVIDERS: dict[str, SocialProvider] = {
    FacebookProvider.slug: FacebookProvider(),
    InstagramProvider.slug: InstagramProvider(),
    LinkedInProvider.slug: LinkedInProvider(),
    TwitterProvider.slug: TwitterProvider(),
    YouTubeProvider.slug: YouTubeProvider(),
}

# The platform a slug falls back to when nothing matches. This is not a design
# choice -- it reproduces posts.py:639, where the publish dispatch's final
# ``else`` sent any unrecognised platform to Instagram. Preserved so this stays
# a refactor; see get_provider for why it now says so out loud.
_FALLBACK_SLUG = InstagramProvider.slug

# Substring rules, in order. SocialPlatform.slug is user-facing data with no
# unique constraint and rows are per-workspace, so exact matching would be
# fragile -- the old dispatch matched on substrings and this keeps that, so no
# existing row stops resolving.
_ALIASES: tuple[tuple[str, str], ...] = (
    ("facebook", FacebookProvider.slug),
    ("instagram", InstagramProvider.slug),
    ("insta", InstagramProvider.slug),
    ("linkedin", LinkedInProvider.slug),
    ("youtube", YouTubeProvider.slug),
    ("twitter", TwitterProvider.slug),
)


def resolve_slug(slug: str | None) -> str:
    """Canonical provider slug for a SocialPlatform.slug, or the fallback."""
    normalized = (slug or "").strip().lower()
    if normalized in _PROVIDERS:
        return normalized
    if normalized == "x":  # X's slug is a single character; substrings cannot help
        return TwitterProvider.slug
    for needle, target in _ALIASES:
        if needle in normalized:
            return target
    return _FALLBACK_SLUG


def get_provider(slug: str | None) -> SocialProvider:
    """The provider for a platform slug.

    An unknown slug returns the Instagram provider rather than raising, because
    that is what the code this replaces did -- silently, at posts.py:639. The
    warning is the only change: publishing someone's LinkedIn post to Instagram
    should not be quiet. Turning it into an error is a one-line follow-up, kept
    separate so a refactor does not change what publishes where.
    """
    normalized = (slug or "").strip().lower()
    resolved = resolve_slug(normalized)
    if resolved == _FALLBACK_SLUG and normalized != _FALLBACK_SLUG:
        if not any(needle in normalized for needle, t in _ALIASES if t == _FALLBACK_SLUG):
            logger.warning(
                "No connector for platform slug %r; falling back to %s. This "
                "publishes to the wrong platform and is preserved only for "
                "compatibility with the previous dispatch.",
                slug,
                _FALLBACK_SLUG,
            )
    return _PROVIDERS[resolved]


def capabilities_for(slug: str | None) -> Capabilities:
    """What the platform behind this slug accepts."""
    return get_provider(slug).capabilities


def known_slugs() -> tuple[str, ...]:
    return tuple(_PROVIDERS)
