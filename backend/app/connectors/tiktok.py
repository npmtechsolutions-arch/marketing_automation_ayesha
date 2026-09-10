"""TikTok.

The first new network added *through* the connector abstraction rather than
alongside it, which is the point of the exercise: everything below is either
the interface the other five implement or a genuine TikTok difference.

Three of those differences shape the whole file.

**SELF_ONLY is a state, not an error.**
Until TikTok audits an app, everything it posts is forced to private
(``SELF_ONLY``) visibility, at most a handful of users a day may post, and each
of those accounts must itself be private. That is not a failure and must not be
reported as one -- it is the tier every new integration starts on, and it is
what makes the audit demo video possible in the first place. A publish under it
**succeeds**, and carries a ``notice`` saying who can see it. Reporting it as an
error would paint the one path to getting audited red; saying nothing at all
would leave someone waiting for views that cannot arrive.

**Publishing is submit-then-poll.**
The Content Posting API accepts an upload and returns a ``publish_id``; the
video is then transcoded asynchronously and the caller polls for the outcome.
The poll opens **one** HTTP client around the whole loop rather than one per
attempt -- the lesson from Instagram's container poll, where every iteration
built a fresh TCP+TLS connection and then held it idle across the sleep.

**Video or nothing.**
There is no text-only and no image post on the Content Posting API. A post with
no video fails immediately with a sentence a user can act on, rather than being
rendered into a video the author never wrote (which is what the YouTube
publisher does with an image, and is not a behaviour to spread).

Metrics follow the null discipline the rest of the project runs on: a field the
granted scope does not cover is **absent**, never zero. TikTok's analytics
scopes are separate from its publishing scopes, so a connection that can post
may legitimately not be able to measure, and reporting that as engagement of
zero would be the fabrication this codebase spent three sessions removing.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlencode

import httpx

from app.connectors.base import (
    Capabilities,
    MediaRef,
    NotSupportedError,
    OAuthTokens,
    PlatformRateLimited,
    ProviderAPIError,
    PublishResult,
    ResolvedContent,
    SocialProvider,
    TokenRefreshResult,
    expires_at_from,
    is_mock_token,
    metrics_from,
    provider_request,
    require_refresh_token,
    retry_after_seconds,
    tokens_from,
)
from app.connectors.media import _content_with_hashtags, _download_media_bytes
from app.core.config import settings

logger = logging.getLogger(__name__)

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
API = "https://open.tiktokapis.com/v2"

# video.publish is Direct Post; video.upload alone can only land a draft in the
# user's inbox. user.info.basic is what get_profile needs; user.info.stats is
# what makes get_analytics return anything at all.
SCOPES = "user.info.basic,user.info.stats,video.publish"

# TikTok's own poll guidance is a few seconds apart; a long video can take a
# while to transcode. 40 x 5s is a little over three minutes.
POLL_ATTEMPTS = 40
POLL_INTERVAL_SECONDS = 5.0

# From TikTok's published limits at the time of writing. Recorded here rather
# than guessed, and cited in docs/WALKTHROUGH-B.md so they can be re-checked.
MAX_CAPTION_CHARS = 2200
MAX_VIDEO_SECONDS = 600
MAX_VIDEO_BYTES = 4 * 1024 * 1024 * 1024  # 4 GB
CHUNK_BYTES = 10 * 1024 * 1024

VIDEO_EXTENSIONS = (".mp4", ".mov", ".webm", ".avi", ".mkv", ".m4v")

# Terminal poll states. Everything else -- PROCESSING_UPLOAD,
# PROCESSING_DOWNLOAD, SEND_TO_USER_INBOX, and anything TikTok adds later --
# means "not finished", and waiting is the honest answer to a state we do not
# recognise.
STATUS_COMPLETE = "PUBLISH_COMPLETE"
STATUS_FAILED = "FAILED"

SELF_ONLY_NOTICE = (
    "Posted privately — on TikTok this video is visible only to your own "
    "account, because this app has not been through TikTok's audit yet."
)


class AuditState:
    """Where this app stands with TikTok's review.

    Stored on the connection's ``config`` rather than inferred, because the
    consequence -- every post forced private -- is something a user has to be
    told before they wonder why nobody saw it.
    """

    KEY = "tiktok_audit_state"
    UNAUDITED = "unaudited"
    AUDITED = "audited"

    @staticmethod
    def of(social_account: Any) -> str:
        config = getattr(social_account, "config", None) or {}
        value = config.get(AuditState.KEY)
        # Unaudited is the honest default: an app is unaudited until TikTok
        # says otherwise, and assuming the generous case would mean promising
        # public posts we cannot actually make.
        if value in (AuditState.AUDITED, AuditState.UNAUDITED):
            return value
        return AuditState.UNAUDITED


def privacy_for(social_account: Any) -> str:
    """The only privacy level this app may actually use for this connection."""
    if AuditState.of(social_account) == AuditState.AUDITED:
        return "PUBLIC_TO_EVERYONE"
    return "SELF_ONLY"


class TikTokProvider(SocialProvider):
    slug = "tiktok"
    name = "TikTok"

    capabilities = Capabilities(
        # Video only, and required. There is no text-only or image post on the
        # Content Posting API, so claiming images would be the lying matrix.
        supports_images=False,
        supports_video=True,
        # Not just accepted -- required. The composer refuses a text-only post
        # targeting TikTok rather than letting it reach publish and fail.
        requires_video=True,
        supports_carousel=False,
        # No link post type, and a URL in a caption is not clickable for most
        # accounts, so claiming link support would over-promise.
        supports_link_posts=False,
        # Comments, DMs and mentions need scopes and endpoints v1 does not
        # request. The methods below refuse, and these flags say so.
        supports_comments_api=False,
        supports_dm_api=False,
        supports_mentions_api=False,
        max_chars=MAX_CAPTION_CHARS,
        max_images=0,
        max_video_seconds=MAX_VIDEO_SECONDS,
        max_video_bytes=MAX_VIDEO_BYTES,
    )

    # -- configuration ----------------------------------------------------

    def is_configured(self) -> bool:
        return bool(
            getattr(settings, "TIKTOK_CLIENT_KEY", "")
            and getattr(settings, "TIKTOK_CLIENT_SECRET", "")
        )

    @property
    def redirect_uri(self) -> str:
        return getattr(settings, "TIKTOK_REDIRECT_URI", "")

    def build_authorize_url(self, state: str, challenge: str) -> str:
        """PKCE, which TikTok requires for the web flow."""
        return f"{AUTH_URL}?" + urlencode({
            "client_key": settings.TIKTOK_CLIENT_KEY,
            "scope": SCOPES,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        })

    async def exchange_code(self, code: str, code_verifier: str) -> OAuthTokens:
        payload = await provider_request(
            self.slug, TOKEN_URL,
            data={
                "client_key": settings.TIKTOK_CLIENT_KEY,
                "client_secret": settings.TIKTOK_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": self.redirect_uri,
                "code_verifier": code_verifier,
            },
            operation="Authorization",
        )
        return tokens_from(payload)

    async def refresh_token(self, social_account: Any) -> TokenRefreshResult:
        refresh = require_refresh_token(self.slug, social_account)
        payload = await provider_request(
            self.slug, TOKEN_URL,
            data={
                "client_key": settings.TIKTOK_CLIENT_KEY,
                "client_secret": settings.TIKTOK_CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": refresh,
            },
            operation="Token refresh",
        )
        access = payload.get("access_token")
        if not access:
            raise ProviderAPIError(self.slug, "TikTok returned no access token")
        return TokenRefreshResult(
            access_token=access,
            # TikTok rotates the refresh token; keeping the old one locks the
            # account out at the next refresh, which is the bug X had.
            refresh_token=payload.get("refresh_token")
            or getattr(social_account, "refresh_token", None),
            expires_at=expires_at_from(payload),
            message="TikTok access token refreshed successfully",
        )

    # -- profile ----------------------------------------------------------

    async def get_profile(self, social_account: Any) -> dict[str, Any]:
        token = getattr(social_account, "access_token", None)
        if is_mock_token(token):
            # No real account behind a placeholder token, so nothing to report.
            return {}

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{API}/user/info/",
                headers={"Authorization": f"Bearer {token}"},
                params={"fields": "open_id,display_name,avatar_url,follower_count"},
            )
        _raise_if_rate_limited(response)
        if response.status_code != 200:
            raise ProviderAPIError(
                self.slug,
                f"TikTok profile fetch failed: {_detail(response)}",
                status_code=response.status_code,
            )

        user = ((response.json() or {}).get("data") or {}).get("user") or {}
        profile = {
            "external_id": user.get("open_id"),
            "username": user.get("display_name"),
            "avatar_url": user.get("avatar_url"),
        }
        # Absent stays absent: a connection without user.info.stats reports no
        # follower count rather than a zero that would render as a real number.
        if user.get("follower_count") is not None:
            profile["followers"] = user["follower_count"]
        return profile

    # -- publishing -------------------------------------------------------

    async def publish_post(
        self,
        variant: ResolvedContent,
        media: list[MediaRef],
        social_account: Any,
    ) -> PublishResult:
        """Submit the video, then poll until TikTok says what happened.

        Succeeds under SELF_ONLY, with a notice. An unaudited app posting
        privately is working correctly.
        """
        token = getattr(social_account, "access_token", None)
        privacy = privacy_for(social_account)
        notice = SELF_ONLY_NOTICE if privacy == "SELF_ONLY" else None

        if is_mock_token(token):
            mock_id = f"tt_mock_{uuid.uuid4().hex[:8]}"
            return PublishResult(
                status="published",
                external_post_id=mock_id,
                post_url=f"https://www.tiktok.com/@mock/video/{mock_id}",
                notice=notice,
            )

        source = _video_url(variant, media)
        if source is None:
            # Not retryable and not a platform fault: a TikTok post without a
            # video is not something TikTok has any way to accept.
            return PublishResult(
                status="failed",
                error=(
                    "TikTok posts need a video. Attach an .mp4 or .mov to this "
                    "post, or remove TikTok from its targets."
                ),
                retryable=False,
            )

        try:
            video = await _download_media_bytes(source)
        except Exception as exc:  # noqa: BLE001 - our own storage, not TikTok's
            return PublishResult(
                status="failed",
                error=f"The video could not be read for upload: {exc}",
                retryable=True,
            )

        if len(video) > MAX_VIDEO_BYTES:
            return PublishResult(
                status="failed",
                error=(
                    f"The video is {len(video) / 1024 ** 3:.1f} GB. TikTok "
                    f"accepts up to {MAX_VIDEO_BYTES // 1024 ** 3} GB."
                ),
                retryable=False,
            )

        headers = {"Authorization": f"Bearer {token}"}
        caption = _content_with_hashtags(variant.post, limit=MAX_CAPTION_CHARS)

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                publish_id, upload_url = await self._init_upload(
                    client, headers, caption, privacy, len(video)
                )
                await self._upload(client, upload_url, video)
                return await self._await_publish(
                    client, headers, publish_id, notice
                )
        except PlatformRateLimited:
            # The one case where the platform says when to come back; the job
            # runner honours it over its own backoff.
            raise
        except ProviderAPIError as exc:
            return PublishResult(
                status="failed", error=exc.detail, retryable=exc.retryable
            )

    async def _init_upload(
        self, client, headers: dict, caption: str, privacy: str, size: int
    ) -> tuple[str, str]:
        chunk = min(CHUNK_BYTES, size) or 1
        response = await client.post(
            f"{API}/post/publish/video/init/",
            headers=headers,
            json={
                "post_info": {
                    "title": caption,
                    # Decided here rather than hoped for: sending
                    # PUBLIC_TO_EVERYONE from an unaudited client is rejected
                    # outright, so the audit state chooses the value.
                    "privacy_level": privacy,
                    "disable_comment": False,
                    "disable_duet": False,
                    "disable_stitch": False,
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": size,
                    "chunk_size": chunk,
                    "total_chunk_count": max(1, -(-size // chunk)),
                },
            },
        )
        _raise_if_rate_limited(response)
        if response.status_code != 200:
            raise ProviderAPIError(
                "tiktok",
                f"TikTok would not accept the upload: {_detail(response)}",
                status_code=response.status_code,
            )
        data = (response.json() or {}).get("data") or {}
        publish_id = data.get("publish_id")
        upload_url = data.get("upload_url")
        if not publish_id or not upload_url:
            raise ProviderAPIError(
                "tiktok",
                "TikTok accepted the upload request but returned no publish id.",
            )
        return publish_id, upload_url

    async def _upload(self, client, upload_url: str, video: bytes) -> None:
        size = len(video)
        response = await client.put(
            upload_url,
            content=video,
            headers={
                "Content-Type": "video/mp4",
                # Single chunk. The whole file is already in memory, so a
                # multi-chunk upload would add failure modes and buy nothing.
                "Content-Range": f"bytes 0-{size - 1}/{size}",
            },
            timeout=600.0,
        )
        if response.status_code not in (200, 201, 204):
            raise ProviderAPIError(
                "tiktok",
                f"TikTok video upload failed: {_detail(response)}",
                status_code=response.status_code,
            )

    async def _await_publish(
        self, client, headers: dict, publish_id: str, notice: Optional[str]
    ) -> PublishResult:
        """Poll until TikTok reaches a terminal state.

        One client for the whole loop -- it is passed in rather than opened per
        attempt, which is the Instagram lesson: a fresh TCP+TLS handshake on
        every iteration, then held idle across the sleep.
        """
        for attempt in range(POLL_ATTEMPTS):
            response = await client.post(
                f"{API}/post/publish/status/fetch/",
                headers=headers,
                json={"publish_id": publish_id},
            )
            _raise_if_rate_limited(response)
            if response.status_code != 200:
                raise ProviderAPIError(
                    "tiktok",
                    f"TikTok status check failed: {_detail(response)}",
                    status_code=response.status_code,
                )

            data = (response.json() or {}).get("data") or {}
            status = (data.get("status") or "").upper()

            if status == STATUS_COMPLETE:
                video_id = _first_public_id(data)
                return PublishResult(
                    status="published",
                    # The publish id is a real handle on the upload even when
                    # no public video id exists (which is what SELF_ONLY
                    # normally returns), so the job still has something to
                    # record rather than a NULL.
                    external_post_id=video_id or publish_id,
                    post_url=(
                        f"https://www.tiktok.com/video/{video_id}"
                        if video_id else None
                    ),
                    notice=notice,
                )
            if status == STATUS_FAILED:
                reason = data.get("fail_reason") or "TikTok gave no reason."
                return PublishResult(
                    status="failed",
                    error=f"TikTok could not publish the video: {reason}",
                    # A rejected video is rejected. Re-uploading the same
                    # bytes would fail the same way and burn the daily quota.
                    retryable=False,
                )

            if attempt < POLL_ATTEMPTS - 1:
                await asyncio.sleep(POLL_INTERVAL_SECONDS)

        return PublishResult(
            status="failed",
            error=(
                "TikTok was still processing the video after "
                f"{int(POLL_ATTEMPTS * POLL_INTERVAL_SECONDS)} seconds. It may "
                "still publish on its own; check TikTok before retrying."
            ),
            # Genuinely retryable: the platform was slow, not wrong.
            retryable=True,
        )

    # -- analytics --------------------------------------------------------

    async def get_analytics(
        self, social_account: Any, since: datetime, until: datetime
    ) -> dict[str, Any]:
        """Account metrics, with anything the scope does not cover left absent.

        TikTok's stats scope is separate from its publishing scope, so a
        connection that can post may legitimately not be able to measure. A
        missing field is missing; it is never a zero.
        """
        token = getattr(social_account, "access_token", None)
        if is_mock_token(token):
            return {}

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{API}/user/info/",
                headers={"Authorization": f"Bearer {token}"},
                params={"fields": "follower_count,likes_count,video_count"},
            )
        _raise_if_rate_limited(response)
        if response.status_code != 200:
            # A failed fetch reports nothing rather than a plausible number.
            logger.warning("TikTok analytics fetch failed: %s", _detail(response))
            return {}

        user = ((response.json() or {}).get("data") or {}).get("user") or {}
        # metrics_from drops keys the payload does not carry, which is what
        # keeps an ungranted scope out of the totals instead of in them as 0.
        return metrics_from(user, {
            "followers": "follower_count",
            "likes": "likes_count",
            "posts_count": "video_count",
        })

    # -- refusals ---------------------------------------------------------

    async def get_post_metrics(
        self, external_post_id: str, social_account: Any
    ) -> dict[str, Any]:
        """Per-video metrics need ``video.list``, which v1 does not request.

        Refused rather than estimated. The alternative -- handing back the
        account's lifetime totals as though they belonged to one video -- is
        the exact shape of the fabrication removed from X and LinkedIn.
        """
        raise NotSupportedError(self.slug, "get_post_metrics")


def _video_url(variant: ResolvedContent, media: list[MediaRef]) -> Optional[str]:
    """The video this post carries, if it has one.

    Three places, in order: an explicit per-platform video URL, a MediaRef the
    caller already typed as video, then anything in the attachments that looks
    like a video file. Nothing here converts an image into a video -- see the
    module docstring.
    """
    if variant.video_url:
        return variant.video_url
    for ref in media or []:
        if getattr(ref, "kind", None) == "video":
            return ref.url
    for ref in media or []:
        if _looks_like_video(ref.url):
            return ref.url
    for url in variant.media_urls or []:
        if isinstance(url, str) and _looks_like_video(url):
            return url
    return None


def _looks_like_video(url: Optional[str]) -> bool:
    if not url:
        return False
    # Query strings are the norm on signed storage URLs, so the extension has
    # to be found in the path rather than at the end of the string.
    path = str(url).split("?", 1)[0].lower()
    return path.endswith(VIDEO_EXTENSIONS)


def _first_public_id(data: dict) -> Optional[str]:
    """The public video id, where the post is public enough to have one.

    TikTok's own field name is misspelled in its documentation and in some
    responses, so both spellings are read. A SELF_ONLY post has no public id at
    all, and the empty list that comes back is the correct answer, not a bug.
    """
    ids = (
        data.get("publicaly_available_post_id")
        or data.get("publicly_available_post_id")
        or []
    )
    return str(ids[0]) if ids else None


def _raise_if_rate_limited(response: httpx.Response) -> None:
    if getattr(response, "status_code", None) == 429:
        raise PlatformRateLimited(
            "tiktok",
            f"TikTok rate limited the request: {_detail(response)}",
            retry_after_seconds(response),
        )


def _detail(response: httpx.Response) -> str:
    """TikTok's own message where it gives one.

    Its errors arrive under ``error.message``; a bare status code sends a user
    to support with nothing to say.
    """
    try:
        body = response.json()
    except Exception:  # noqa: BLE001 - not every error body is JSON
        return (getattr(response, "text", "") or "")[:300] or (
            f"HTTP {getattr(response, 'status_code', '?')}"
        )
    error = (body or {}).get("error") or {}
    message = error.get("message") or error.get("code") or body
    return str(message)[:300]
