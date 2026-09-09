"""The YouTube connector.

Publishing and metrics moved verbatim from the old ``platform_service.py``
(publish :1021-1138, metrics :1367-1427), then converted from blocking ``httpx.Client`` to
``httpx.AsyncClient``. Nothing waits on a thread here: the requests are
awaited, so a slow platform costs a coroutine rather than one of the process's
shared worker threads.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from app.connectors.base import (
    Capabilities,
    MediaRef,
    ResolvedContent,
    PublishResult,
    PlatformRateLimited,
    SocialProvider,
    metrics_from,
    mock_inbox_items,
    parse_platform_time,
    retry_after_seconds,
    OAuthTokens,
    tokens_from,
    ProviderAPIError,
    TokenRefreshResult,
    expires_at_from,
    provider_request,
    require_refresh_token,
    classify_retryable,
    is_mock_token,
)
from app.connectors.media import (
    _content_with_hashtags,
    _download_media_bytes,
    _first_media_url,
    _render_image_audio_to_video,
)

from app.core.config import settings

logger = logging.getLogger(__name__)


def _raise_if_rate_limited(slug: str, response: Any) -> None:
    """Turn a 429 into a typed error carrying the platform's Retry-After.

    Applied to the request that actually posts the content -- the one whose
    rate limit decides when the post can go out. Secondary calls (page
    discovery, insights) fall back to exponential backoff, which is the right
    trade: plumbing this through all twenty request sites would be noise for
    the ones a user never waits on.
    """
    if getattr(response, "status_code", None) == 429:
        raise PlatformRateLimited(
            slug,
            f"{slug} rate limited the request: {getattr(response, 'text', '')[:300]}",
            retry_after_seconds(response),
        )


async def publish_to_youtube(post: Any, platform: Any) -> dict[str, Any]:
    """Upload a video to the connected YouTube channel (videos.insert).

    "Posting" to YouTube means uploading a video, so a video attachment is
    required. Uses Google's resumable upload protocol.
    """
    import httpx
    import uuid

    # YouTube posts are one of two upload formats: a standard "video" or a
    # "shorts" clip. Both go through the same videos.insert API — YouTube
    # itself classifies an upload as a Short when it's vertical, under ~3
    # minutes, and tagged #Shorts, so for shorts we make sure that hashtag is
    # present. (Legacy "post"/"community" values fall through to a normal
    # video upload; the Community-tab option has been removed.)
    yt_type = (getattr(post, "youtube_post_type", None) or "").strip().lower()
    is_shorts = yt_type in ("shorts", "short")

    access_token = getattr(platform, "access_token", None)
    if not access_token:
        raise ValueError(
            "This YouTube account has no access token. Reconnect it using "
            "the 'Connect YouTube' button."
        )

    if "mock" in access_token or "test" in access_token or access_token.startswith("refreshed_"):
        logger.info("Mock token detected for YouTube publishing, bypassing API call.")
        return {
            "status": "success",
            "platform": "youtube",
            "external_post_id": f"yt_mock_{uuid.uuid4().hex[:8]}",
            "published_at": datetime.now(timezone.utc).isoformat(),
        }

    # Locate a video attachment.
    video_url = getattr(post, "instagram_video_url", None)
    candidate = _first_media_url(post)
    if candidate and any(
        ext in candidate.lower() for ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"]
    ):
        video_url = candidate
    if not video_url:
        if candidate:
            logger.info("YouTube post has an image but no video — rendering image + music into a short video for YouTube.")
            music_url = getattr(post, "instagram_music_url", None) or getattr(post, "facebook_music_url", None)
            if not music_url:
                music_url = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
            try:
                video_url = await _render_image_audio_to_video(
                    candidate, music_url, start_offset=0, duration=15
                )
            except Exception as render_err:
                logger.error("Failed to render YouTube video from image: %s", render_err)
                raise ValueError(f"Could not convert image to YouTube video: {render_err}")
        else:
            raise ValueError(
                "YouTube publishing requires a video file or an image. Please attach media to your post."
            )

    logger.info(
        "Uploading video to YouTube channel %s", getattr(platform, "account_name", "unknown")
    )
    video_bytes = await _download_media_bytes(video_url)

    title = (getattr(post, "title", None) or (post.content or "")[:90] or "New video").strip()
    description = _content_with_hashtags(post)
    if is_shorts and "#shorts" not in description.lower():
        # The #Shorts tag is what tells YouTube to treat a vertical, short
        # clip as a Short rather than a regular video.
        description = f"{description}\n\n#Shorts".strip()
    metadata = {
        "snippet": {"title": title[:100], "description": description},
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }

    async with httpx.AsyncClient() as client:
        init = await client.post(
            "https://www.googleapis.com/upload/youtube/v3/videos"
            "?uploadType=resumable&part=snippet,status",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Type": "video/*",
                "X-Upload-Content-Length": str(len(video_bytes)),
            },
            json=metadata,
            timeout=30.0,
        )
        _raise_if_rate_limited("youtube", init)
        if init.status_code not in (200, 201):
            raise ValueError(f"YouTube upload initiation failed: {init.text}")
        upload_url = init.headers.get("location") or init.headers.get("Location")
        if not upload_url:
            raise ValueError("YouTube did not return a resumable upload URL.")

        put = await client.put(
            upload_url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "video/*",
            },
            content=video_bytes,
            timeout=600.0,
        )
        if put.status_code not in (200, 201):
            raise ValueError(
                f"YouTube video upload failed: {put.status_code} {put.text}"
            )
        video_id = put.json().get("id")

    post_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else None
    return {
        "status": "success",
        "platform": "youtube",
        "external_post_id": video_id,
        "post_url": post_url,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }



async def _fetch_metrics(post_id: str, platform: Any) -> dict[str, Any]:
    """Moved from the ``youtube`` branch of PlatformService.fetch_performance.

    The no-token short-circuit that guarded the whole if/elif chain is
    reproduced here so each provider keeps it.
    """
    platform_type = (
        platform.platform.slug if platform and platform.platform else "unknown"
    ).lower()
    logger.info("Fetching performance for post %s on %s", post_id, platform_type)

    access_token = getattr(platform, "access_token", None)
    if is_mock_token(access_token):
        # A placeholder token means there is no account to measure, so nothing
        # is reported. This used to return mock_metrics_untokened() -- random
        # integers -- which is not a development-only hazard: is_mock_token()
        # matches any token merely *containing* "test", and returns True for an
        # empty one, so a real credential with "test" in it, or an account whose
        # token failed to decrypt, would have been served fabricated engagement.
        # An empty result writes no performance row, which reads as "not
        # measured" everywhere downstream.
        return {}

    import httpx
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={
                    "part": "statistics,snippet",
                    "id": post_id,
                    "access_token": access_token,
                },
                timeout=15.0
            )
            if res.status_code != 200:
                logger.error("Failed to fetch basic YouTube video metrics: %s", res.text)
                raise ValueError(f"YouTube API error: {res.text}")
        
            items = res.json().get("items", [])
            if not items:
                raise ValueError(f"YouTube video not found: {post_id}")
        
            stats = items[0].get("statistics", {})
            view_count = int(stats.get("viewCount", 0))
            like_count = int(stats.get("likeCount", 0))
            comment_count = int(stats.get("commentCount", 0))
        
            engagement_rate = 0.0
            if view_count > 0:
                engagement_rate = round(((like_count + comment_count) / view_count) * 100, 2)
        
            return {
                "platform": "youtube",
                "impressions": view_count,
                "reach": view_count,
                "likes": like_count,
                "comments": comment_count,
                "shares": 0,
                "saves": 0,
                "clicks": 0,
                "video_views": view_count,
                "engagement_rate": engagement_rate,
                "click_through_rate": 0.0,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
    except Exception as e:
        # A failed fetch reports nothing. This used to log "falling back to
        # mock" and return random integers -- on a real account, with real
        # credentials, precisely when something was wrong. An expired token, a
        # rate limit or a provider outage produced plausible engagement that
        # was indistinguishable from a measurement, and hid the failure that
        # caused it.
        #
        # An empty result leaves any existing performance row untouched, so the
        # last real measurement stands with its original fetched_at rather than
        # being overwritten by an invention.
        logger.warning(
            "Could not fetch live %s metrics for %s; reporting nothing: %s",
            "YouTube", post_id, e,
        )
        return {}



class YouTubeProvider(SocialProvider):
    slug = "youtube"
    name = "YouTube"
    capabilities = Capabilities(
        supports_images=False,
        supports_video=True,
        supports_carousel=False,
        supports_link_posts=False,
        supports_comments_api=True,
        supports_dm_api=False,
        max_chars=5000,
        max_images=0,
        max_video_seconds=12 * 60 * 60,
        max_video_bytes=256 * 1024 * 1024 * 1024,
    )

    async def publish_post(
        self,
        variant: ResolvedContent,
        media: list[MediaRef],
        social_account: Any,
    ) -> PublishResult:
        try:
            result = await publish_to_youtube(variant.post, social_account)
        except PlatformRateLimited as exc:
            # The one case where the platform tells us when to come back.
            return PublishResult(
                status="failed",
                error=exc.detail,
                retryable=True,
                retry_after=exc.retry_after,
            )
        except Exception as exc:  # noqa: BLE001 - every failure becomes a result
            message = str(exc)
            # YouTube Community posts have no API. The publisher signals that by
            # raising with this prefix; it becomes a distinct status rather than
            # a red error so the UI can offer a "publish by hand" helper.
            if message.startswith("MANUAL_YOUTUBE_COMMUNITY:"):
                return PublishResult(
                    status="manual_required",
                    error=message.replace("MANUAL_YOUTUBE_COMMUNITY:", "").strip(),
                )
            return PublishResult(
                status="failed",
                error=message,
                retryable=classify_retryable(message),
            )

        return PublishResult(
            status="published",
            external_post_id=result.get("external_post_id"),
            post_url=result.get("post_url"),
        )

    async def get_post_metrics(
        self, external_post_id: str, social_account: Any
    ) -> dict[str, Any]:
        return await _fetch_metrics(external_post_id, social_account)

    async def refresh_token(self, social_account: Any) -> TokenRefreshResult:
        """Moved from social_accounts.py:870-919 (and posts.py:253-283, which
        was a second copy of the same grant)."""
        token = require_refresh_token(self.slug, social_account)
        payload = await provider_request(
            self.slug,
            "https://oauth2.googleapis.com/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": token,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
            },
        )
        access = payload.get("access_token")
        if not access:
            raise ProviderAPIError(self.slug, "Google returned no access token")
        return TokenRefreshResult(
            access_token=access,
            # Google only returns a refresh token on first consent.
            refresh_token=payload.get("refresh_token") or token,
            expires_at=expires_at_from(payload),
            message="YouTube access token refreshed successfully",
        )

    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    SCOPES = (
        "https://www.googleapis.com/auth/youtube.upload "
        "https://www.googleapis.com/auth/youtube.readonly"
    )

    @property
    def redirect_uri(self) -> str:
        return settings.YOUTUBE_REDIRECT_URI

    def is_configured(self) -> bool:
        return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)

    def build_authorize_url(self, state: str) -> str:
        from urllib.parse import urlencode

        return f"{self.AUTH_URL}?" + urlencode({
            "response_type": "code",
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": self.redirect_uri,
            "scope": self.SCOPES,
            "state": state,
            # Google returns a refresh token only on first consent, so
            # re-consent is forced to guarantee one.
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
        })

    async def exchange_code(self, code: str) -> OAuthTokens:
        payload = await provider_request(
            self.slug,
            self.TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
            },
        )
        return tokens_from(payload)

    async def get_comments(
        self, social_account: Any, external_post_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Top-level comments on the channel's videos."""
        return await _yt_comments(social_account)

    async def reply_to_comment(
        self, social_account: Any, comment_external_id: str, body: str
    ) -> dict[str, Any]:
        return await _yt_reply(social_account, comment_external_id, body)

    async def get_analytics(
        self, social_account: Any, since: datetime, until: datetime
    ) -> dict[str, Any]:
        """YouTube channel statistics.

        Subscribers, video count and lifetime views. Per-day reach and
        impressions need the YouTube Analytics API (a separate OAuth scope),
        so they are absent here.
        """
        return await _account_metrics(social_account, since, until)


async def _account_metrics(platform: Any, since, until) -> dict[str, Any]:
    """YouTube channel statistics."""
    import httpx

    token = getattr(platform, "access_token", None)
    if is_mock_token(token):
        # No real account behind a placeholder token, so no metrics. Absent
        # metrics stay absent and store as NULL -- see collect_account().
        return {}

    out: dict[str, Any] = {}
    async with httpx.AsyncClient() as client:
        res = await client.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "statistics", "mine": "true"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=15.0,
        )
        _raise_if_rate_limited("youtube", res)
        if res.status_code == 200:
            items = res.json().get("items") or []
            if items:
                stats = items[0].get("statistics") or {}
                out.update(metrics_from(stats, {
                    "followers": "subscriberCount",
                    "posts_count": "videoCount",
                    "video_views": "viewCount",
                }))
    return out


# ---------------------------------------------------------------------------
# Inbox
# ---------------------------------------------------------------------------

async def _yt_comments(social_account: Any) -> list[dict[str, Any]]:
    import httpx

    token = getattr(social_account, "access_token", None)
    if is_mock_token(token):
        return mock_inbox_items("youtube", "comment")

    headers = {"Authorization": f"Bearer {token}"}
    out: list[dict[str, Any]] = []
    async with httpx.AsyncClient() as client:
        channels = await client.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "id", "mine": "true"},
            headers=headers, timeout=20.0,
        )
        _raise_if_rate_limited("youtube", channels)
        if channels.status_code != 200:
            raise ProviderAPIError(
                "youtube", channels.text[:200], status_code=channels.status_code
            )
        items = channels.json().get("items") or []
        if not items:
            return []

        threads = await client.get(
            "https://www.googleapis.com/youtube/v3/commentThreads",
            params={
                "part": "snippet", "allThreadsRelatedToChannelId": items[0]["id"],
                "maxResults": 50, "order": "time",
            },
            headers=headers, timeout=20.0,
        )
        _raise_if_rate_limited("youtube", threads)
        if threads.status_code != 200:
            raise ProviderAPIError(
                "youtube", threads.text[:200], status_code=threads.status_code
            )

        for row in threads.json().get("items", []):
            top = (row.get("snippet") or {}).get("topLevelComment") or {}
            snippet = top.get("snippet") or {}
            out.append({
                "external_id": top.get("id"),
                "thread_external_id": row.get("id"),
                "author": snippet.get("authorDisplayName") or "Someone",
                "author_handle": snippet.get("authorChannelUrl"),
                "body": snippet.get("textOriginal") or "",
                "created_at": parse_platform_time(snippet.get("publishedAt")),
                "permalink": (
                    f"https://www.youtube.com/watch?v={snippet.get('videoId')}"
                    if snippet.get("videoId") else None
                ),
            })
    return out


async def _yt_reply(social_account: Any, comment_id: str, body: str) -> dict[str, Any]:
    import httpx

    token = getattr(social_account, "access_token", None)
    if is_mock_token(token):
        return {"external_id": f"mock_reply_{comment_id}"}

    async with httpx.AsyncClient() as client:
        res = await client.post(
            "https://www.googleapis.com/youtube/v3/comments",
            params={"part": "snippet"},
            json={"snippet": {"parentId": comment_id, "textOriginal": body}},
            headers={"Authorization": f"Bearer {token}"}, timeout=20.0,
        )
        _raise_if_rate_limited("youtube", res)
        if res.status_code not in (200, 201):
            raise ProviderAPIError(
                "youtube", res.text[:200], status_code=res.status_code
            )
        return {"external_id": res.json().get("id")}
