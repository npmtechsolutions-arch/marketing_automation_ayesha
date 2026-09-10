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
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
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


class AccountNotFound(ProviderAPIError):
    """The platform can see no such account.

    Its own type because the caller does something different with it: a handle
    the platform cannot find is a typo to correct at the moment of typing, not
    a fault to log and retry weekly. Tracking it silently would produce a row
    that is empty forever and looks like a competitor with no followers.
    """


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
    # Some platforms do not merely accept video, they publish nothing else.
    # TikTok's Content Posting API has no text-only and no image post at all,
    # so a caption-only post is not a thin post there -- it is not a post. The
    # composer needs to say so while the author can still fix it, and the only
    # place that knows is the connector.
    requires_video: bool = False
    supports_carousel: bool = False
    supports_link_posts: bool = False
    supports_comments_api: bool = False
    supports_dm_api: bool = False
    # Mentions are a separate permission and a separate endpoint everywhere
    # they exist, so they get their own flag rather than being folded into
    # comments -- X has mentions and no comments, which one flag cannot say.
    supports_mentions_api: bool = False
    # Searching *other people's* posts, which is a different permission
    # everywhere it exists at all. Meta has no public search on any tier, so
    # this is X-only and the UI has to say which platform a listening feature
    # actually covers rather than implying all of them.
    supports_recent_search: bool = False
    # Looking up a *named* account that has not authorised this app. Instagram
    # Business Discovery is the only official route to one anywhere, and it
    # returns two numbers and a name -- no engagement, no cadence, no audience.
    # The flag says the lookup exists; it does not promise analysis.
    supports_competitor_lookup: bool = False
    # How far back that search can reach, in days. X's pay-per-use tier is a
    # rolling seven; full-archive needs a tier not open to us. None means the
    # platform has no search at all, which is not the same as "unlimited" --
    # supports_recent_search is what says whether to ask.
    search_window_days: Optional[int] = None
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
class ResolvedContent:
    """What one platform actually publishes, after resolution.

    Named for what it is rather than ``PostVariant``, which is now a table: a
    variant is what an author *wrote* for a platform, this is what publishing
    *arrived at* after layering that over the master post. Two things called
    the same name, one of them not a model, would be a trap.

    Per-platform detail comes from three places, in order: the PostVariant row
    for this platform if one exists, then the fifteen flat columns on ``Post``
    (``instagram_music_url``, ``facebook_post_type``, ...), then the master
    content. The provider bodies still read ``.post`` directly so their
    behaviour is unchanged; the resolved fields are what validation reads.
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
    # From a PostVariant when one exists for this platform.
    link_url: Optional[str] = None
    alt_texts: dict = field(default_factory=dict)
    thumbnail_media_id: Optional[Any] = None
    first_comment: Optional[str] = None
    # Which fields the variant overrode, for logging and the composer.
    overridden: tuple[str, ...] = ()

    @property
    def is_customised(self) -> bool:
        return bool(self.overridden)


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
    # Something true about a *successful* publish that the user needs told.
    # TikTok is why it exists: an app TikTok has not yet audited may only post
    # SELF_ONLY, so the video really is live and really is visible to nobody
    # but its author. That is a state, not a failure -- putting it in `error`
    # would paint the one working path to getting audited red, and dropping it
    # would leave someone waiting for views that cannot come.
    notice: Optional[str] = None

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


def resolve_content(
    post: Any, slug: str, variant: Any = None
) -> ResolvedContent:
    """What this platform publishes: the variant layered over the master post.

    ``variant`` is a PostVariant row for this platform, or None. Each of its
    fields overrides only when it is not NULL -- NULL means "inherit", so a
    variant that exists purely to set a first comment still tracks the master
    content as it is edited.

    The caller loads the variant rather than this function querying for it:
    resolution runs inside the publish path where the session is already open,
    and a hidden query here would be a lazy load in an async context.
    """
    from app.connectors import media as media_helpers

    prefix = {"twitter": "twitter", "x": "twitter"}.get(slug, slug)
    raw_media = post.media_urls
    if isinstance(raw_media, str):
        import json

        try:
            raw_media = json.loads(raw_media)
        except Exception:  # noqa: BLE001 - malformed JSON means "no media"
            raw_media = []

    content = post.content or ""
    media_urls = list(raw_media or [])
    link_url = None
    alt_texts: dict = {}
    thumbnail_media_id = None
    first_comment = None
    overridden: list[str] = []

    if variant is not None:
        # `is not None` throughout, never truthiness: an override to "" or []
        # is a deliberate choice to publish nothing there, and treating it as
        # absent would quietly republish the master instead.
        if variant.content is not None:
            content = variant.content
            overridden.append("content")
        if variant.media is not None:
            # Media ids, not URLs. The publish path resolves them; validation
            # only needs the count and the ids.
            media_urls = list(variant.media)
            overridden.append("media")
        if variant.link_url is not None:
            link_url = variant.link_url
            overridden.append("link_url")
        if variant.alt_texts is not None:
            alt_texts = dict(variant.alt_texts)
            overridden.append("alt_texts")
        if variant.thumbnail_media_id is not None:
            thumbnail_media_id = variant.thumbnail_media_id
            overridden.append("thumbnail_media_id")
        if variant.first_comment is not None:
            first_comment = variant.first_comment
            overridden.append("first_comment")

    return ResolvedContent(
        post=post,
        platform=slug,
        content=content,
        title=getattr(post, "title", None),
        media_urls=media_urls,
        hashtags=media_helpers._normalize_hashtags(getattr(post, "hashtags", None)),
        post_type=getattr(post, f"{prefix}_post_type", None),
        music_url=getattr(post, f"{prefix}_music_url", None),
        music_start_offset=getattr(post, f"{prefix}_music_start_offset", None),
        music_end_offset=getattr(post, f"{prefix}_music_end_offset", None),
        video_url=getattr(post, f"{prefix}_video_url", None),
        link_url=link_url,
        alt_texts=alt_texts,
        thumbnail_media_id=thumbnail_media_id,
        first_comment=first_comment,
        overridden=tuple(overridden),
    )


def variant_for_slug(post: Any, slug: str) -> Any:
    """The post's variant for a platform, from already-loaded rows.

    ``Post.variants`` is eager-loaded, so this is a list scan rather than a
    query -- which is what keeps it safe to call from inside the publish path.
    """
    for variant in getattr(post, "variants", None) or []:
        if (variant.platform_slug or "").lower() == slug.lower():
            return variant
    return None


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
        variant: ResolvedContent,
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
        """Account-level metrics for a day.

        Returns a mapping of metric name to value, containing **only the
        metrics this platform actually reports**. A metric the platform does
        not expose must be absent, not zero: the caller stores absence as NULL,
        and a stored 0 would render as a real flat line and drag every
        cross-platform average down.

        Per-post metrics are :meth:`get_post_metrics`.
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

    async def search_recent(
        self,
        social_account: Any,
        query: str,
        *,
        since_id: str | None = None,
        max_results: int = 25,
    ) -> dict[str, Any]:
        """Public posts matching a search, from as far back as the tier allows.

        Returns ``{"items": [...], "requests": int, "posts_read": int}``. The
        counts are part of the result rather than something the caller
        estimates because on X this is **billed per post read**, and a number
        inferred at the call site would drift from what was actually spent the
        first time a request returned fewer posts than it asked for.

        Items are the same shape the inbox uses -- external_id, author,
        author_handle, body, created_at, permalink -- so a mention does not
        have to learn a platform's vocabulary to be stored.
        """
        raise NotSupportedError(self.slug, "search_recent")

    async def lookup_account(
        self, social_account: Any, handle: str
    ) -> dict[str, Any]:
        """Public facts about a named account that has not authorised us.

        Returns ``{"handle", "display_name", "followers", "media_count"}`` with
        **absent fields left out**, not zeroed: a private or non-business
        account yields a name and nothing else, and a stored 0 would be a
        measurement claiming it has no followers.

        Raises :class:`AccountNotFound` when the platform says no such account
        is visible -- a typo and a real account must not look the same, because
        one of them can be fixed by the person typing it.
        """
        raise NotSupportedError(self.slug, "lookup_account")

    # -- inbox ---------------------------------------------------------------
    #
    # Each returns a list of dicts in the shape ``inbox_sync`` expects, so the
    # sync never learns a platform's own vocabulary:
    #
    #   {"external_id", "thread_external_id", "author", "author_handle",
    #    "body", "created_at" (aware datetime), "media": [...], "permalink"}
    #
    # A platform whose API does not offer one of these -- or whose terms do not
    # let *this* application use it -- raises NotSupportedError rather than
    # returning an empty list. Empty means "nothing new"; unsupported means
    # "never ask again", and the UI says so instead of showing a silent void.

    async def get_comments(
        self, social_account: Any, external_post_id: str | None = None
    ) -> list[dict[str, Any]]:
        raise NotSupportedError(self.slug, "get_comments")

    async def get_messages(self, social_account: Any) -> list[dict[str, Any]]:
        raise NotSupportedError(self.slug, "get_messages")

    async def get_mentions(self, social_account: Any) -> list[dict[str, Any]]:
        """Public posts that name this account.

        Distinct from comments: a mention lives on someone else's post, so it
        has no parent of ours and cannot be fetched by walking our own content.
        On X it is the only inbound signal the current tier exposes at all.
        """
        raise NotSupportedError(self.slug, "get_mentions")

    async def reply_to_comment(
        self, social_account: Any, comment_external_id: str, body: str
    ) -> dict[str, Any]:
        """Reply to a comment. Returns at least ``{"external_id": ...}``."""
        raise NotSupportedError(self.slug, "reply_to_comment")

    async def send_message(
        self, social_account: Any, recipient_external_id: str, body: str
    ) -> dict[str, Any]:
        """Send a direct message into an existing conversation."""
        raise NotSupportedError(self.slug, "send_message")

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



# ---------------------------------------------------------------------------
# Inbox helpers, shared by the providers
# ---------------------------------------------------------------------------

def parse_platform_time(value: Any) -> datetime:
    """A platform timestamp as an aware UTC datetime.

    Every platform formats these differently and at least one of them omits the
    colon in the offset. A timestamp we cannot read becomes "now" rather than
    failing the sync: a message with a slightly wrong time is worth having, and
    one dropped because of a format is not.
    """
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value or "").strip()
    if not text:
        return datetime.now(timezone.utc)
    normalised = text.replace("Z", "+00:00")
    # Meta sends +0000; fromisoformat wants +00:00.
    if len(normalised) > 5 and normalised[-5] in "+-" and ":" not in normalised[-5:]:
        normalised = normalised[:-2] + ":" + normalised[-2:]
    try:
        parsed = datetime.fromisoformat(normalised)
    except ValueError:
        logger.debug("Unreadable platform timestamp %r; using now.", value)
        return datetime.now(timezone.utc)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def mock_inbox_items(platform: str, kind: str) -> list[dict[str, Any]]:
    """Believable inbox items for a development token.

    Stable ids, deliberately: the sync is idempotent on ``external_id``, and
    random ids would make every poll look like new mail and hide exactly the
    bug the idempotency exists to prevent.
    """
    now = datetime.now(timezone.utc)
    samples = {
        "comment": [
            ("Priya R", "Does this ship to the EU?"),
            ("Marcus L", "Been waiting for this one. Congrats!"),
        ],
        "dm": [
            ("Dana K", "Hi — is the discount still running?"),
        ],
        "mention": [
            ("Sam T", f"Just tried @{platform} and it is genuinely good."),
        ],
    }.get(kind, [])

    return [
        {
            "external_id": f"mock_{platform}_{kind}_{index}",
            "thread_external_id": f"mock_{platform}_{kind}_thread_{index}",
            "author": author,
            "author_handle": author.lower().replace(" ", "_"),
            "participant": author,
            "participant_handle": author.lower().replace(" ", "_"),
            "body": body,
            "created_at": now - timedelta(hours=index + 1),
            "permalink": f"https://{platform}.example/{kind}/{index}",
        }
        for index, (author, body) in enumerate(samples)
    ]

def metrics_from(payload: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    """Pull our metric names out of a platform's response.

    ``mapping`` is metric -> key in the platform payload. A key the platform
    omitted is left out of the result entirely rather than defaulted, which is
    what keeps "not reported" distinguishable from "zero".
    """
    result: dict[str, Any] = {}
    for metric, source_key in mapping.items():
        raw = payload.get(source_key)
        if raw is None:
            continue
        try:
            result[metric] = int(raw)
        except (TypeError, ValueError):
            continue
    return result
