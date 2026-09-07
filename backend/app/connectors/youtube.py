"""The YouTube connector.

Publishing and metrics moved verbatim from ``app/services/platform_service.py``
(publish :1021-1138, metrics :1367-1427). The bodies are unchanged, including their quirks -- this was a move,
not a rewrite. They stay synchronous (blocking ``httpx.Client``) and the async
methods below hand them to ``asyncio.to_thread``, which is exactly what the old
dispatch in posts.py did around each call.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from app.connectors.base import (
    Capabilities,
    MediaRef,
    PostVariant,
    PublishResult,
    SocialProvider,
    OAuthTokens,
    exchange_code_async,
    tokens_from,
    ProviderAPIError,
    TokenRefreshResult,
    expires_at_from,
    refresh_sync,
    require_refresh_token,
    classify_retryable,
    is_mock_token,
    mock_metrics_untokened,
)
from app.connectors.media import (
    _content_with_hashtags,
    _download_media_bytes,
    _first_media_url,
    _render_image_audio_to_video,
)

from app.core.config import settings

logger = logging.getLogger(__name__)


def publish_to_youtube(post: Any, platform: Any) -> dict[str, Any]:
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
                video_url = _render_image_audio_to_video(
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
    video_bytes = _download_media_bytes(video_url)

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

    with httpx.Client() as client:
        init = client.post(
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
        if init.status_code not in (200, 201):
            raise ValueError(f"YouTube upload initiation failed: {init.text}")
        upload_url = init.headers.get("location") or init.headers.get("Location")
        if not upload_url:
            raise ValueError("YouTube did not return a resumable upload URL.")

        put = client.put(
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



def _fetch_metrics_sync(post_id: str, platform: Any) -> dict[str, Any]:
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
        return mock_metrics_untokened(platform_type)

    import httpx
    try:
        with httpx.Client() as client:
            res = client.get(
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
        logger.warning("Error fetching live YouTube metrics for %s, falling back to mock: %s", post_id, e)
        import random
        return {
            "platform": "youtube",
            "impressions": random.randint(500, 8000),
            "reach": random.randint(300, 5000),
            "likes": random.randint(50, 800),
            "comments": random.randint(10, 150),
            "shares": 0,
            "saves": 0,
            "clicks": 0,
            "video_views": random.randint(500, 8000),
            "engagement_rate": round(random.uniform(2.0, 9.0), 2),
            "click_through_rate": 0.0,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }



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
        variant: PostVariant,
        media: list[MediaRef],
        social_account: Any,
    ) -> PublishResult:
        try:
            result = await asyncio.to_thread(
                publish_to_youtube, variant.post, social_account
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
        return await asyncio.to_thread(
            _fetch_metrics_sync, external_post_id, social_account
        )

    async def refresh_token(self, social_account: Any) -> TokenRefreshResult:
        """Moved from social_accounts.py:870-919 (and posts.py:253-283, which
        was a second copy of the same grant)."""
        token = require_refresh_token(self.slug, social_account)
        payload = await asyncio.to_thread(
            refresh_sync,
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
        payload = await exchange_code_async(
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
