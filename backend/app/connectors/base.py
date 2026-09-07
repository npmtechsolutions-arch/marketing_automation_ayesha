"""The SocialProvider abstraction.

Before this, platform-specific behaviour was spread across three layers and the
same ``if "facebook" in slug ... elif`` chain was written four times, each with
different coverage: publishing handled five platforms, pre-publish token refresh
handled two, and account verification and manual refresh each had their own
shape. Adding a platform meant finding all four.

A provider owns one platform. The registry resolves a slug to one, and callers
stop branching.

**Async all the way down.** Every platform call is awaited: the providers use
``httpx.AsyncClient`` and ``media.py`` awaits even the ffmpeg render, via
``asyncio.create_subprocess_exec``. Only genuine disk work -- reading and
writing the render's temporary files -- still goes through
``asyncio.to_thread``.

That matters because the thread pool is shared with bcrypt password hashing.
Waiting on Instagram's encoder (up to two minutes) or a YouTube upload (up to
ten) used to occupy one of sixteen threads for the duration, so a publish burst
could slow logins.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar, Literal, Optional

logger = logging.getLogger(__name__)


class NotSupportedError(NotImplementedError):
    """The platform has no API for this capability.

    Deliberately distinct from "we have not built it yet": a caller that gets
    this should stop asking rather than retry or open a ticket. Instagram has no
    DM API on this tier; that is not a gap in our code.
    """

    def __init__(self, slug: str, capability: str) -> None:
        super().__init__(f"{slug} does not support {capability}")
        self.slug = slug
        self.capability = capability


class ProviderNotConfigured(Exception):
    """The platform's app credentials are missing from settings."""

    def __init__(self, slug: str, detail: str) -> None:
        super().__init__(detail)
        self.slug = slug
        self.detail = detail


class ProviderAPIError(Exception):
    """The platform's API refused or could not be reached.

    Carries ``retryable`` so a caller can tell a rate limit from a revoked
    token. The endpoints that used to hold this logic raised HTTPException
    directly from inside the HTTP call, which meant the platform's status code
    and our API's status code were decided in the same breath -- and a provider
    could not be called from anywhere but a request handler.
    """

    def __init__(self, slug: str, detail: str, *, status_code: int | None = None) -> None:
        super().__init__(detail)
        self.slug = slug
        self.detail = detail
        self.status_code = status_code
        self.retryable = classify_retryable(status_code if status_code else detail)


class PlatformRateLimited(Exception):
    """The platform returned 429 and told us when to come back.

    Carried as its own type because ``Retry-After`` is the one piece of retry
    information a platform gives us directly, and stringifying it into an error
    message -- which is what every failure used to become -- throws it away.
    """

    def __init__(self, slug: str, detail: str, retry_after: int | None = None) -> None:
        super().__init__(detail)
        self.slug = slug
        self.detail = detail
        self.retry_after = retry_after


def retry_after_seconds(response: Any) -> int | None:
    """Parse ``Retry-After`` from a response. Seconds only.

    The header may also be an HTTP date; those are rare from these platforms
    and a wrong parse would be worse than falling back to exponential backoff,
    so a non-numeric value is ignored.
    """
    raw = None
    try:
        raw = response.headers.get("retry-after")
    except Exception:  # noqa: BLE001 - a mock or an odd response object
        return None
    if not raw:
        return None
    try:
        seconds = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return seconds if seconds > 0 else None


class MissingCredential(ProviderAPIError):
    """The account has no stored credential for this operation.

    A subclass rather than a bare ProviderAPIError because the two map to
    different HTTP statuses: not being able to reach a platform is a 502, but
    never having stored a refresh token is the caller's state -- a 400, which
    is what the endpoints this replaced returned.
    """


@dataclass(frozen=True)
class TokenRefreshResult:
    """New credentials from a refresh. ``refresh_token`` is None when the
    platform does not rotate it (Meta) or did not return one (Google, on
    re-consent)."""

    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    message: str = "Access token refreshed successfully"


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Capabilities:
    """What a platform will accept.

    Served to the composer so it can validate before a user spends effort on a
    post the platform will reject. The counter in the composer is currently a
    hardcoded 2,200 for every platform, so a user targeting X is told 2,200
    characters is fine and finds out otherwise at publish time.

    ``None`` means "no limit", which is why the numeric fields are optional
    rather than using a sentinel -- a 0 or -1 here would be the same ambiguity
    the entitlement work removed.
    """

    supports_images: bool = False
    supports_video: bool = False
    supports_carousel: bool = False
    supports_link_posts: bool = False
    supports_comments_api: bool = False
    supports_dm_api: bool = False
    max_chars: Optional[int] = None
    max_images: int = 0
    max_video_seconds: Optional[int] = None
    max_video_bytes: Optional[int] = None


# ---------------------------------------------------------------------------
# Publish inputs and outputs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MediaRef:
    """One attachment. ``url`` may be private; providers re-host as needed."""

    url: str
    kind: Literal["image", "video", "audio", "unknown"] = "unknown"


@dataclass(frozen=True)
class PostVariant:
    """The content to publish, resolved for one platform.

    Not a database model. Per-platform content lives in fifteen flat columns on
    ``Post`` (``instagram_music_url``, ``facebook_post_type``, ...) and
    :func:`variant_for` picks the right ones for a slug. The provider bodies
    moved in this refactor still read ``variant.post`` directly so their
    behaviour is unchanged; the resolved fields below are what capability
    validation reads, and what those bodies should be weaned onto next.
    """

    post: Any
    platform: str
    content: str = ""
    title: Optional[str] = None
    media_urls: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)
    post_type: Optional[str] = None
    music_url: Optional[str] = None
    music_start_offset: Optional[int] = None
    music_end_offset: Optional[int] = None
    video_url: Optional[str] = None


@dataclass(frozen=True)
class PublishResult:
    """The outcome of one publish to one account.

    ``manual_required`` is its own status because YouTube Community posts have
    no API: the UI shows a "publish by hand" helper rather than a red error.
    That used to be signalled by raising an exception whose message began with
    ``MANUAL_YOUTUBE_COMMUNITY:`` and string-matching it at the call site.

    ``retryable`` records whether the failure could plausibly succeed later (a
    429 or a 5xx) as opposed to never (a 400, a revoked token). Nothing acts on
    it yet -- the scheduler's retry counter is crash-recovery only -- but
    classifying at the point where the HTTP status is still in hand is the only
    place it can be done honestly.
    """

    status: Literal["published", "failed", "manual_required"]
    external_post_id: Optional[str] = None
    post_url: Optional[str] = None
    error: Optional[str] = None
    retryable: bool = False
    # Seconds the platform asked us to wait, from a 429's Retry-After. The
    # scheduler honours it over its own backoff: guessing shorter gets us rate
    # limited again, guessing longer delays the post for nothing.
    retry_after: Optional[int] = None

    @property
    def succeeded(self) -> bool:
        return self.status == "published"


# Statuses that are retryable when a platform returns them. 429 is rate
# limiting and 5xx is the platform being unwell; both pass with time. A 4xx is
# our request being wrong, and repeating it just burns quota.
_RETRYABLE_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})


def classify_retryable(error: str | int | None) -> bool:
    """Whether a failure is worth retrying, from an HTTP status or message."""
    if error is None:
        return False
    if isinstance(error, int):
        return error in _RETRYABLE_STATUSES
    text = str(error)
    for status in _RETRYABLE_STATUSES:
        if str(status) in text:
            return True
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in ("timeout", "timed out", "temporarily", "try again")
    )


def variant_for(post: Any, slug: str) -> PostVariant:
    """Resolve a Post's per-platform columns for one platform."""
    from app.connectors import media as media_helpers

    prefix = {"twitter": "twitter", "x": "twitter"}.get(slug, slug)
    raw_media = post.media_urls
    if isinstance(raw_media, str):
        import json

        try:
            raw_media = json.loads(raw_media)
        except Exception:  # noqa: BLE001 - malformed JSON means "no media"
            raw_media = []

    return PostVariant(
        post=post,
        platform=slug,
        content=post.content or "",
        title=getattr(post, "title", None),
        media_urls=list(raw_media or []),
        hashtags=media_helpers._normalize_hashtags(getattr(post, "hashtags", None)),
        post_type=getattr(post, f"{prefix}_post_type", None),
        music_url=getattr(post, f"{prefix}_music_url", None),
        music_start_offset=getattr(post, f"{prefix}_music_start_offset", None),
        music_end_offset=getattr(post, f"{prefix}_music_end_offset", None),
        video_url=getattr(post, f"{prefix}_video_url", None),
    )


def mock_metrics_untokened(platform_type: str) -> dict[str, Any]:
    """Metrics for an account whose token is a development placeholder.

    Moved verbatim from platform_service.py:1155-1168. Note it carries
    ``engagement_rate`` and ``click_through_rate``; :func:`mock_metrics_fallback`
    does not. The two blocks were written separately and drifted -- preserved
    as-is rather than reconciled, so this stays a pure move.
    """
    import random
    return {
        "platform": platform_type,
        "impressions": random.randint(500, 8000),
        "reach": random.randint(300, 5000),
        "likes": random.randint(50, 800),
        "comments": random.randint(10, 150),
        "shares": random.randint(5, 80),
        "saves": random.randint(5, 50),
        "clicks": random.randint(20, 300),
        "engagement_rate": round(random.uniform(2.0, 9.0), 2),
        "click_through_rate": round(random.uniform(0.5, 4.0), 2),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def mock_metrics_fallback(platform_type: str) -> dict[str, Any]:
    """Metrics for a platform with no implemented API (LinkedIn, X).

    Moved verbatim from platform_service.py:1431-1441. A dashboard number for
    those two platforms is fabricated; that is pre-existing and is centralised
    here so it is at least findable.
    """
    return {
        "platform": platform_type,
        "impressions": random.randint(500, 8000),
        "reach": random.randint(300, 5000),
        "likes": random.randint(50, 800),
        "comments": random.randint(10, 150),
        "shares": random.randint(5, 80),
        "saves": random.randint(5, 50),
        "clicks": random.randint(20, 300),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def is_mock_token(token: str | None) -> bool:
    """Whether a token is a development placeholder rather than a real one.

    The five publishers each had their own version of this check and X's was
    stricter than the rest (platform_service.py:955-960). This is the lenient
    one they shared, kept as-is: note it matches any token merely *containing*
    "test", which is a real hazard with live credentials and is recorded in the
    plan as a follow-up rather than changed here.
    """
    if not token:
        return True
    return "mock" in token or "test" in token or token.startswith("refreshed_")


# ---------------------------------------------------------------------------
# The interface
# ---------------------------------------------------------------------------

class SocialProvider:
    """One social platform.

    Every method raises :class:`NotSupportedError` by default, so a subclass
    implements only what its platform actually offers and callers get a clear
    signal for the rest instead of an AttributeError or a silent ``None``.
    """

    slug: ClassVar[str] = ""
    name: ClassVar[str] = ""
    capabilities: ClassVar[Capabilities] = Capabilities()

    # -- connection lifecycle ------------------------------------------------

    async def connect(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Exchange an OAuth code for tokens and identity."""
        raise NotSupportedError(self.slug, "connect")

    async def disconnect(self, social_account: Any) -> None:
        """Revoke access at the platform.

        The default is a no-op with a log line, which matches today's
        behaviour: disconnecting only deletes our row
        (``social_accounts.py::delete_social_account``) and never tells the
        platform. Overriding this per provider is a genuine improvement, not a
        move, so it is left for a follow-up.
        """
        logger.info(
            "Disconnecting %s account %s locally; no token revocation is sent "
            "to the platform.",
            self.slug,
            getattr(social_account, "id", "?"),
        )

    async def refresh_token(self, social_account: Any) -> dict[str, Any]:
        """Exchange the refresh token for a new access token."""
        raise NotSupportedError(self.slug, "refresh_token")

    # -- publishing ----------------------------------------------------------

    async def publish_post(
        self,
        variant: PostVariant,
        media: list[MediaRef],
        social_account: Any,
    ) -> PublishResult:
        raise NotSupportedError(self.slug, "publish_post")

    # -- reading -------------------------------------------------------------

    async def get_profile(self, social_account: Any) -> dict[str, Any]:
        """Follower counts and profile details for the connected account."""
        raise NotSupportedError(self.slug, "get_profile")

    async def get_analytics(
        self, social_account: Any, since: datetime, until: datetime
    ) -> dict[str, Any]:
        """Account-level metrics over a date range.

        No platform implements this yet: nothing in the app has ever fetched a
        range. Per-post metrics are :meth:`get_post_metrics`.
        """
        raise NotSupportedError(self.slug, "get_analytics")

    async def get_post_metrics(
        self, external_post_id: str, social_account: Any
    ) -> dict[str, Any]:
        """Engagement for one published post.

        Not in the original interface sketch, but the existing
        ``fetch_performance`` code needs a home and it is per-post, not a range.
        """
        raise NotSupportedError(self.slug, "get_post_metrics")

    async def get_posts(self, social_account: Any) -> list[dict[str, Any]]:
        raise NotSupportedError(self.slug, "get_posts")

    async def get_comments(
        self, social_account: Any, external_post_id: str | None = None
    ) -> list[dict[str, Any]]:
        raise NotSupportedError(self.slug, "get_comments")

    async def get_messages(self, social_account: Any) -> list[dict[str, Any]]:
        raise NotSupportedError(self.slug, "get_messages")

    # -- helpers -------------------------------------------------------------

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{type(self).__name__} slug={self.slug!r}>"


# ---------------------------------------------------------------------------
# Shared OAuth refresh plumbing
# ---------------------------------------------------------------------------

async def provider_request(
    slug: str,
    url: str,
    *,
    method: str = "post",
    data: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    auth: tuple[str, str] | None = None,
    timeout: float = 20.0,
    operation: str = "Request",
) -> dict[str, Any]:
    """One HTTP round-trip to a platform's OAuth endpoint.

    ``operation`` names the caller in the error detail, which reaches the user
    for a manual refresh -- "Token refresh failed: ..." rather than a bare
    "Request failed".

    Used by both token refresh and the authorization-code exchange. They were
    two near-identical functions -- one blocking, one async -- which differed
    only in their default timeout and would have drifted apart.

    The platform branches this replaces were the same twenty lines four times
    over, differing only in URL, verb, and whether credentials travel in the
    body or in HTTP Basic.
    """
    import httpx

    try:
        async with httpx.AsyncClient() as client:
            request = client.get if method == "get" else client.post
            kwargs: dict[str, Any] = {"timeout": timeout}
            if data is not None:
                kwargs["data"] = data
                kwargs["headers"] = {"Content-Type": "application/x-www-form-urlencoded"}
            if params is not None:
                kwargs["params"] = params
            if auth is not None:
                kwargs["auth"] = auth
            response = await request(url, **kwargs)
    except Exception as exc:  # noqa: BLE001 - a network failure is a provider error
        raise ProviderAPIError(slug, f"{operation} call failed: {exc}") from exc

    if response.status_code != 200:
        raise ProviderAPIError(
            slug,
            f"{operation} failed: {response.text}",
            status_code=response.status_code,
        )
    return response.json()


def expires_at_from(payload: dict[str, Any]) -> Optional[datetime]:
    """``expires_in`` seconds into an absolute timestamp, or None if absent."""
    from datetime import timedelta

    expires_in = payload.get("expires_in")
    if not expires_in:
        return None
    return datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))


def require_refresh_token(slug: str, social_account: Any) -> str:
    """The stored refresh token, or a clear error.

    Meta has no refresh token at all, which is why its provider does not call
    this -- it re-exchanges the access token instead.
    """
    token = getattr(social_account, "refresh_token", None)
    if not token:
        raise MissingCredential(
            slug,
            "No refresh token stored for this account. Reconnect the account to "
            "grant offline access.",
        )
    return token


# ---------------------------------------------------------------------------
# OAuth connect
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OAuthTokens:
    """What a code-for-token exchange yields."""

    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    raw: dict[str, Any] = field(default_factory=dict)


def tokens_from(payload: dict[str, Any]) -> OAuthTokens:
    """Normalise an exchange response. Identical arithmetic to the five
    callbacks it replaces, which computed this the same way character for
    character."""
    return OAuthTokens(
        access_token=payload.get("access_token", ""),
        refresh_token=payload.get("refresh_token"),
        expires_at=expires_at_from(payload),
        raw=payload,
    )
