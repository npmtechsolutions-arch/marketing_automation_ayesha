"""The Instagram connector.

Publishing and metrics moved verbatim from the old ``platform_service.py``
(publish :560-779, metrics :1171-1266), then converted from blocking ``httpx.Client`` to
``httpx.AsyncClient``. Nothing waits on a thread here: the requests are
awaited, so a slow platform costs a coroutine rather than one of the process's
shared worker threads.
"""

import asyncio
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
    retry_after_seconds,
    OAuthTokens,
    provider_request,
    tokens_from,
    TokenRefreshResult,
    classify_retryable,
    is_mock_token,
    mock_metrics_untokened,
)
from app.connectors.media import (
    _content_with_hashtags,
    _ensure_public_media_url,
    _is_public_media_url,
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


async def publish_to_instagram(post: Any, platform: Any) -> dict[str, Any]:
    """Publish a post to Instagram via the Graph API (requires media URL)."""
    logger.info(
        "Publishing to Instagram account %s",
        getattr(platform, "account_name", "unknown"),
    )
    import httpx
    import uuid

    access_token = getattr(platform, "access_token", None)
    if not access_token:
        raise ValueError("No access token found for the social account")

    # Mock token fallback for local dev / testing
    if "mock" in access_token or "test" in access_token or access_token.startswith("refreshed_"):
        logger.info("Mock token detected for Instagram publishing, bypassing API call.")
        return {
            "status": "success",
            "platform": "instagram",
            "external_post_id": f"ig_mock_{uuid.uuid4().hex[:8]}",
            "published_at": datetime.now(timezone.utc).isoformat(),
        }

    is_instagram_token = access_token.startswith("IG")
    base_url = "https://graph.instagram.com/v18.0" if is_instagram_token else "https://graph.facebook.com/v18.0"

    # 1. Discover or use connected page's Instagram Business Account ID
    ig_user_id = None
    if platform.config:
        ig_user_id = platform.config.get("instagram_business_account_id") or platform.config.get("page_id")

    if not ig_user_id:
        if is_instagram_token:
            # Discover via Instagram Graph API /me
            url_me = f"{base_url}/me"
            params_me = {
                "fields": "id,username",
                "access_token": access_token
            }
            async with httpx.AsyncClient() as client:
                res_me = await client.get(url_me, params=params_me, timeout=15.0)
                if res_me.status_code == 200:
                    ig_user_id = res_me.json().get("id")
                else:
                    raise ValueError(f"Failed to fetch Instagram account details: {res_me.text}")
        else:
            # Discover via Facebook Graph API /me/accounts
            url_me = f"{base_url}/me/accounts"
            params_me = {
                "fields": "instagram_business_account,name",
                "access_token": access_token
            }
            async with httpx.AsyncClient() as client:
                res_me = await client.get(url_me, params=params_me, timeout=15.0)
                if res_me.status_code == 200:
                    pages = res_me.json().get("data", [])
                    for page in pages:
                        ig_acc = page.get("instagram_business_account")
                        if ig_acc:
                            ig_user_id = ig_acc.get("id")
                            break
                else:
                    raise ValueError(f"Failed to fetch linked Facebook Pages/Instagram accounts: {res_me.text}")

    if not ig_user_id:
        raise ValueError("No linked Instagram Business Account was found on this Meta token. Please ensure your Instagram Creator/Business account is linked to a Facebook Page.")

    # 2. Get media URL (Instagram requires media)
    is_reel = getattr(post, "instagram_post_type", None) == "reel"
    media_url = None

    if is_reel:
        media_url = getattr(post, "instagram_video_url", None)
        if not media_url and post.media_urls:
            if isinstance(post.media_urls, list) and post.media_urls:
                media_url = post.media_urls[0]
            elif isinstance(post.media_urls, str):
                import json
                try:
                    urls = json.loads(post.media_urls)
                    if isinstance(urls, list) and urls:
                        media_url = urls[0]
                    else:
                        media_url = post.media_urls
                except json.JSONDecodeError:
                    media_url = post.media_urls
    else:
        if post.media_urls:
            if isinstance(post.media_urls, list) and post.media_urls:
                media_url = post.media_urls[0]
            elif isinstance(post.media_urls, str):
                import json
                try:
                    urls = json.loads(post.media_urls)
                    if isinstance(urls, list) and urls:
                        media_url = urls[0]
                    else:
                        media_url = post.media_urls
                except json.JSONDecodeError:
                    media_url = post.media_urls

    if not media_url:
        if is_reel:
            raise ValueError("Instagram Reel publishing requires a video. Please attach a video to your post.")
        else:
            raise ValueError("Instagram publishing requires an image. Please attach an image to your post.")

    # Instagram fetches the media itself, so base64 and locally-hosted URLs
    # (e.g. AI images saved under /uploads) have to be re-hosted publicly.
    media_url = await _ensure_public_media_url(media_url)
    if not _is_public_media_url(media_url):
        raise ValueError("Failed to upload post media to a public host. Instagram Graph API requires public media URLs.")

    # ── Photo + music → render a Reel ──
    # Instagram feed photos can't carry audio. If the user attached a music
    # track to an image post, turn the image + audio clip into a short video
    # and publish it as a Reel so the selected song actually plays with the photo.
    music_url = getattr(post, "instagram_music_url", None)
    if not is_reel and music_url and media_url:
        logger.info("Image post has music attached — rendering image + audio into a Reel.")
        start_offset = getattr(post, "instagram_music_start_offset", 0) or 0
        end_offset = getattr(post, "instagram_music_end_offset", None)
        # Use the exact trimmed window the user selected (end - start);
        # fall back to a 15s clip when no end was chosen.
        if end_offset and end_offset > start_offset:
            duration = end_offset - start_offset
        else:
            duration = 15
        duration = max(1, min(duration, 60))
        media_url = await _render_image_audio_to_video(
            media_url, music_url, start_offset=start_offset, duration=duration
        )
        is_reel = True

    # 3. Create Media Container
    container_url = f"{base_url}/{ig_user_id}/media"
    payload = {
        "caption": _content_with_hashtags(post),
        "access_token": access_token
    }
    if is_reel:
        payload["media_type"] = "REELS"
        payload["video_url"] = media_url
        # Also surface the Reel on the profile feed grid so the photo is visible.
        payload["share_to_feed"] = "true"
    else:
        payload["image_url"] = media_url

    async with httpx.AsyncClient() as client:
        res = await client.post(container_url, data=payload, timeout=20.0)
        _raise_if_rate_limited("instagram", res)
        if res.status_code != 200:
            raise ValueError(f"Instagram Graph API container creation failed: {res.text}")
        container_id = res.json().get("id")

    if not container_id:
        raise ValueError("Failed to retrieve media container ID from Instagram Graph API")

    # 4. Poll Media Container Status
    status_url = f"{base_url}/{container_id}"
    params_status = {
        "fields": "status_code",
        "access_token": access_token
    }
    processed = False
    # Wait for encoding: 24 attempts, 5s apart. The stated ceiling is ~120s of
    # waiting, though the true worst case is 24 * (10s request timeout + 5s
    # sleep) if every poll times out.
    #
    # The client is opened once around the loop rather than per attempt: this
    # used to build a fresh TCP+TLS connection on each of the 24 iterations and
    # then hold it open, idle, across the sleep. The sleep is awaited, so a
    # publish waiting on Instagram's encoder now occupies nothing at all -- it
    # previously parked a pool thread for the entire wait.
    async with httpx.AsyncClient() as client:
        for _ in range(24):
            res_status = await client.get(status_url, params=params_status, timeout=10.0)
            if res_status.status_code == 200:
                status_code = res_status.json().get("status_code")
                if status_code == "FINISHED":
                    processed = True
                    break
                elif status_code == "ERROR":
                    raise ValueError(f"Instagram media container processing failed: {res_status.text}")
            await asyncio.sleep(5)

    if not processed:
        raise TimeoutError("Timeout waiting for Instagram media container to finish processing.")

    # 5. Publish Media Container
    publish_url = f"{base_url}/{ig_user_id}/media_publish"
    payload_pub = {
        "creation_id": container_id,
        "access_token": access_token
    }
    async with httpx.AsyncClient() as client:
        res_pub = await client.post(publish_url, data=payload_pub, timeout=20.0)
        if res_pub.status_code != 200:
            raise ValueError(f"Instagram Graph API publish failed: {res_pub.text}")
        published_id = res_pub.json().get("id")

    # 6. Fetch permalink if possible
    post_url = None
    if published_id:
        info_url = f"{base_url}/{published_id}"
        params_info = {
            "fields": "permalink",
            "access_token": access_token
        }
        try:
            async with httpx.AsyncClient() as client:
                res_info = await client.get(info_url, params=params_info, timeout=10.0)
                if res_info.status_code == 200:
                    post_url = res_info.json().get("permalink")
        except Exception:
            logger.warning("Could not fetch Instagram post permalink")

    if not post_url:
        post_url = f"https://www.instagram.com/p/{published_id}/" if published_id else None

    return {
        "status": "success",
        "platform": "instagram",
        "external_post_id": published_id,
        "post_url": post_url,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }



async def _fetch_metrics(post_id: str, platform: Any) -> dict[str, Any]:
    """Moved from the ``instagram`` branch of PlatformService.fetch_performance.

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

    is_instagram_token = access_token.startswith("IG")
    base_url = "https://graph.instagram.com/v18.0" if is_instagram_token else "https://graph.facebook.com/v18.0"

    import httpx
    fields = "like_count,comments_count,media_product_type,media_type,permalink"
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                f"{base_url}/{post_id}",
                params={"fields": fields, "access_token": access_token},
                timeout=15.0
            )
            if res.status_code != 200:
                logger.error("Failed to fetch basic Instagram post metrics: %s", res.text)
                raise ValueError(f"Instagram Graph API error: {res.text}")
        
            data = res.json()
            likes = data.get("like_count", 0)
            comments = data.get("comments_count", 0)
            media_type = data.get("media_type")
            media_product_type = data.get("media_product_type")
        
            # Fetch impressions, reach, saves etc from insights if it's an IG Business account
            impressions = 0
            reach = 0
            saves = 0
            shares = 0
            video_views = 0
        
            metrics_list = []
            if media_product_type == "REELS" or media_type == "VIDEO":
                metrics_list = ["views", "reach", "saved", "shares", "total_interactions"]
            else:
                metrics_list = ["impressions", "reach", "saved"]
        
            try:
                res_insights = await client.get(
                    f"{base_url}/{post_id}/insights",
                    params={"metric": ",".join(metrics_list), "access_token": access_token},
                    timeout=15.0
                )
                if res_insights.status_code == 200:
                    insights_data = res_insights.json().get("data", [])
                    for metric in insights_data:
                        name = metric.get("name")
                        values = metric.get("values", [])
                        val = values[0].get("value", 0) if values else 0
                        if name == "impressions":
                            impressions = val
                        elif name == "reach":
                            reach = val
                        elif name == "saved":
                            saves = val
                        elif name == "shares":
                            shares = val
                        elif name == "views":
                            video_views = val
                            impressions = val
            except Exception as insight_err:
                logger.warning("Could not fetch Instagram insights for %s: %s", post_id, insight_err)
        
            total_eng = likes + comments + saves + shares
            engagement_rate = round((total_eng / max(1, reach)) * 100, 2)
        
            return {
                "platform": "instagram",
                "impressions": max(impressions, reach, likes),
                "reach": reach,
                "likes": likes,
                "comments": comments,
                "shares": shares,
                "saves": saves,
                "clicks": 0,
                "video_views": video_views,
                "engagement_rate": engagement_rate,
                "click_through_rate": 0.0,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
    except Exception as e:
        logger.warning("Error fetching live Instagram metrics for %s, falling back to mock: %s", post_id, e)
        import random
        return {
            "platform": "instagram",
            "impressions": random.randint(500, 8000),
            "reach": random.randint(300, 5000),
            "likes": random.randint(50, 800),
            "comments": random.randint(10, 150),
            "shares": random.randint(5, 80),
            "saves": random.randint(5, 50),
            "clicks": 0,
            "video_views": random.randint(100, 2000),
            "engagement_rate": round(random.uniform(2.0, 9.0), 2),
            "click_through_rate": 0.0,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }



class InstagramProvider(SocialProvider):
    slug = "instagram"
    name = "Instagram"
    capabilities = Capabilities(
        supports_images=True,
        supports_video=True,
        supports_carousel=True,
        # A caption's links are not clickable, so a link post is not a thing
        # Instagram offers.
        supports_link_posts=False,
        supports_comments_api=True,
        supports_dm_api=False,
        max_chars=2200,
        max_images=10,
        max_video_seconds=90,
        max_video_bytes=1024 * 1024 * 1024,
    )

    async def publish_post(
        self,
        variant: ResolvedContent,
        media: list[MediaRef],
        social_account: Any,
    ) -> PublishResult:
        try:
            result = await publish_to_instagram(variant.post, social_account)
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
        """Instagram authenticates through Facebook Login, so the same
        long-lived exchange applies. Delegating keeps one implementation."""
        from app.connectors.facebook import FacebookProvider

        return await FacebookProvider().refresh_token(social_account)

    AUTH_URL = "https://www.facebook.com/v18.0/dialog/oauth"
    TOKEN_URL = "https://graph.facebook.com/v18.0/oauth/access_token"
    SCOPES = (
        "instagram_basic,instagram_content_publish,instagram_manage_comments,"
        "instagram_manage_insights,pages_show_list,pages_read_engagement"
    )

    # One redirect_uri, used by both authorize and the exchange. They were
    # derived differently before -- authorize honoured META_REDIRECT_URI and the
    # callback did not (facebook_oauth.py:97 vs :143) -- so configuring it to
    # anything but the derived default made Meta reject every exchange. Deriving
    # it once is the fix, and it is a behaviour change worth naming.
    @property
    def redirect_uri(self) -> str:
        base = settings.META_REDIRECT_URI or settings.LINKEDIN_REDIRECT_URI.replace(
            "/linkedin/callback", "/facebook/callback"
        )
        return base.replace("/facebook/callback", "/instagram/callback")

    def is_configured(self) -> bool:
        return bool(settings.META_APP_ID and settings.META_APP_SECRET)

    def build_authorize_url(self, state: str) -> str:
        from urllib.parse import urlencode

        params = {
            "response_type": "code",
            "client_id": (settings.META_APP_ID or "").strip(),
            "redirect_uri": self.redirect_uri,
            "state": state,
            "scope": self.SCOPES,
        }
        if settings.META_CONFIG_ID:
            params["config_id"] = settings.META_CONFIG_ID.strip()
        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> OAuthTokens:
        payload = await provider_request(
            self.slug,
            self.TOKEN_URL,
            method="get",
            params={
                "client_id": (settings.META_APP_ID or "").strip(),
                "client_secret": (settings.META_APP_SECRET or "").strip(),
                "redirect_uri": self.redirect_uri,
                "code": code,
            },
        )
        return tokens_from(payload)
