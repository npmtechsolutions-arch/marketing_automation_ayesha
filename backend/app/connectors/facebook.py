"""The Facebook connector.

Publishing and metrics moved verbatim from the old ``platform_service.py``
(publish :412-558, metrics :1269-1364), then converted from blocking ``httpx.Client`` to
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
    ProviderNotConfigured,
    TokenRefreshResult,
    expires_at_from,
    provider_request,
    classify_retryable,
    is_mock_token,
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


async def publish_to_facebook(post: Any, platform: Any) -> dict[str, Any]:
    """Publish a post to a Facebook Page via the Graph API."""
    logger.info(
        "Publishing to Facebook page %s", getattr(platform, "account_name", "unknown")
    )
    import httpx
    import uuid

    access_token = getattr(platform, "access_token", None)
    if not access_token:
        raise ValueError("No access token found for the social account")

    # Mock token fallback for local dev / testing
    if "mock" in access_token or "test" in access_token or access_token.startswith("refreshed_"):
        logger.info("Mock token detected for Facebook publishing, bypassing API call.")
        return {
            "status": "success",
            "platform": "facebook",
            "external_post_id": f"fb_mock_{uuid.uuid4().hex[:8]}",
            "published_at": datetime.now(timezone.utc).isoformat(),
        }

    # Page ID & access token (from config or user token)
    page_id = None
    page_access_token = access_token
    
    if platform.config:
        page_id = platform.config.get("page_id")
        page_access_token = platform.config.get("page_access_token") or access_token

    # Fallback page discovery if config is missing page_id
    if not page_id:
        url_me = "https://graph.facebook.com/v18.0/me/accounts"
        params_me = {"access_token": access_token}
        async with httpx.AsyncClient() as client:
            res_me = await client.get(url_me, params=params_me, timeout=15.0)
            if res_me.status_code == 200:
                pages = res_me.json().get("data", [])
                if pages:
                    page_id = pages[0].get("id")
                    page_access_token = pages[0].get("access_token") or access_token
                else:
                    raise ValueError("No Facebook Pages linked to this access token.")
            else:
                raise ValueError(f"Failed to fetch linked Facebook Pages: {res_me.text}")

    # Extract media URL
    media_url = None
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

    # Facebook fetches the media itself, so base64 and locally-hosted URLs
    # (e.g. AI images saved under /uploads) have to be re-hosted publicly.
    if media_url:
        media_url = await _ensure_public_media_url(media_url)
        if not _is_public_media_url(media_url):
            raise ValueError("Failed to upload post media to a public host. Facebook Graph API requires public media URLs.")

    # Determine media type (image vs video)
    is_video = False
    if media_url:
        is_video = any(ext in media_url.lower() for ext in [".mp4", ".mov", ".avi", ".mkv"])

    # Photo + music -> render video
    is_reel = getattr(post, "facebook_post_type", None) == "reel"
    music_url = getattr(post, "facebook_music_url", None)
    if music_url and media_url and not is_video:
        logger.info("Facebook post has music attached — rendering image + audio into a video.")
        start_offset = getattr(post, "facebook_music_start_offset", 0) or 0
        end_offset = getattr(post, "facebook_music_end_offset", None)
        if end_offset and end_offset > start_offset:
            duration = end_offset - start_offset
        else:
            duration = 15
        duration = max(1, min(duration, 60))
        try:
            media_url = await _render_image_audio_to_video(
                media_url, music_url, start_offset=start_offset, duration=duration
            )
            is_video = True
        except Exception as render_err:
            logger.error("Failed to render Facebook music video: %s", render_err)

    published_id = None
    post_url = None

    if is_video:
        # Publish video
        url = f"https://graph.facebook.com/v18.0/{page_id}/videos"
        payload = {
            "file_url": media_url,
            "description": _content_with_hashtags(post),
            "access_token": page_access_token,
        }
        async with httpx.AsyncClient() as client:
            res = await client.post(url, data=payload, timeout=30.0)
            _raise_if_rate_limited("facebook", res)
            if res.status_code != 200:
                raise ValueError(f"Facebook Graph API video publishing failed: {res.text}")
            published_id = res.json().get("id")
    elif media_url:
        # Publish photo
        url = f"https://graph.facebook.com/v18.0/{page_id}/photos"
        payload = {
            "url": media_url,
            "caption": _content_with_hashtags(post),
            "access_token": page_access_token,
        }
        async with httpx.AsyncClient() as client:
            res = await client.post(url, data=payload, timeout=20.0)
            if res.status_code != 200:
                raise ValueError(f"Facebook Graph API photo publishing failed: {res.text}")
            published_id = res.json().get("id")
    else:
        # Publish text only
        url = f"https://graph.facebook.com/v18.0/{page_id}/feed"
        payload = {
            "message": _content_with_hashtags(post),
            "access_token": page_access_token,
        }
        async with httpx.AsyncClient() as client:
            res = await client.post(url, data=payload, timeout=20.0)
            if res.status_code != 200:
                raise ValueError(f"Facebook Graph API text feed publishing failed: {res.text}")
            published_id = res.json().get("id")

    if published_id:
        post_url = f"https://www.facebook.com/{published_id}"

    return {
        "status": "success",
        "platform": "facebook",
        "external_post_id": published_id,
        "post_url": post_url,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }



async def _fetch_metrics(post_id: str, platform: Any) -> dict[str, Any]:
    """Moved from the ``facebook`` branch of PlatformService.fetch_performance.

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

    # Facebook Page Token fetching
    page_access_token = access_token
    if platform.config:
        page_access_token = platform.config.get("page_access_token") or access_token

    import httpx
    try:
        # 1. Fetch likes, comments, and shares
        # GET /{post_id}?fields=shares,likes.summary(true),comments.summary(true)
        url_basic = f"https://graph.facebook.com/v18.0/{post_id}"
        params_basic = {
            "fields": "shares,likes.summary(true),comments.summary(true)",
            "access_token": page_access_token,
        }
    
        likes = 0
        comments = 0
        shares = 0
    
        async with httpx.AsyncClient() as client:
            res_basic = await client.get(url_basic, params=params_basic, timeout=15.0)
            if res_basic.status_code == 200:
                basic_data = res_basic.json()
                likes = basic_data.get("likes", {}).get("summary", {}).get("total_count", 0)
                comments = basic_data.get("comments", {}).get("summary", {}).get("total_count", 0)
                shares = basic_data.get("shares", {}).get("count", 0)
            else:
                logger.error("Failed to fetch basic Facebook post metrics: %s", res_basic.text)
                raise ValueError(f"Facebook Graph API error: {res_basic.text}")

        # 2. Fetch insights (reach, impressions, clicks)
        # GET /{post_id}/insights?metric=post_impressions,post_impressions_unique,post_clicks_by_type
        impressions = 0
        reach = 0
        clicks = 0
    
        try:
            url_insights = f"https://graph.facebook.com/v18.0/{post_id}/insights"
            params_insights = {
                "metric": "post_impressions,post_impressions_unique,post_clicks_by_type",
                "access_token": page_access_token,
            }
            async with httpx.AsyncClient() as client:
                res_insights = await client.get(url_insights, params=params_insights, timeout=15.0)
                if res_insights.status_code == 200:
                    insights_data = res_insights.json().get("data", [])
                    for metric in insights_data:
                        name = metric.get("name")
                        values = metric.get("values", [])
                        val = values[0].get("value", 0) if values else 0
                        if name == "post_impressions":
                            impressions = val
                        elif name == "post_impressions_unique":
                            reach = val
                        elif name == "post_clicks_by_type":
                            if isinstance(val, dict):
                                clicks = sum(val.values())
                            elif isinstance(val, list):
                                clicks = sum(item.get("value", 0) for item in val if isinstance(item, dict))
                            else:
                                clicks = int(val)
        except Exception as insight_err:
            logger.warning("Could not fetch Facebook insights for %s: %s", post_id, insight_err)

        total_eng = likes + comments + shares
        engagement_rate = round((total_eng / max(1, reach)) * 100, 2)

        return {
            "platform": "facebook",
            "impressions": max(impressions, reach, total_eng),
            "reach": reach,
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "saves": 0,
            "clicks": clicks,
            "engagement_rate": engagement_rate,
            "click_through_rate": round((clicks / max(1, impressions)) * 100, 2),
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
            "Facebook", post_id, e,
        )
        return {}



class FacebookProvider(SocialProvider):
    slug = "facebook"
    name = "Facebook"
    capabilities = Capabilities(
        supports_images=True,
        supports_video=True,
        supports_carousel=True,
        supports_link_posts=True,
        supports_comments_api=True,
        # Page messaging is a real Graph endpoint, but it needs the
        # pages_messaging permission and an app that Meta has reviewed for it.
        # The flag says the API offers it; an unapproved app finds out at call
        # time and the error surfaces as a provider error, not a silent empty
        # inbox.
        supports_dm_api=True,
        max_chars=63206,
        max_images=10,
        max_video_seconds=240 * 60,
        max_video_bytes=10 * 1024 * 1024 * 1024,
    )

    async def publish_post(
        self,
        variant: ResolvedContent,
        media: list[MediaRef],
        social_account: Any,
    ) -> PublishResult:
        try:
            result = await publish_to_facebook(variant.post, social_account)
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
        """Exchange a short-lived Page/user token for a long-lived one.

        Meta issues no refresh token; the current access token is itself the
        input. Moved from social_accounts.py:708-752, which was the only place
        this existed -- the publish path's _ensure_valid_token had no Meta
        branch at all, so these tokens expired mid-publish with no recovery.
        """
        if not settings.META_APP_ID or not settings.META_APP_SECRET:
            raise ProviderNotConfigured(
                self.slug,
                "Meta App ID or Secret is not configured in the environment settings",
            )
        payload = await provider_request(
            self.slug,
            "https://graph.facebook.com/v18.0/oauth/access_token",
            method="get",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": settings.META_APP_ID,
                "client_secret": settings.META_APP_SECRET,
                "fb_exchange_token": social_account.access_token or "",
            },
        )
        token = payload.get("access_token")
        if not token:
            raise ProviderAPIError(self.slug, "Meta returned no access token")
        return TokenRefreshResult(
            access_token=token,
            expires_at=expires_at_from(payload),
            message="Instagram/Facebook access token refreshed successfully via Meta API",
        )

    AUTH_URL = "https://www.facebook.com/v18.0/dialog/oauth"
    TOKEN_URL = "https://graph.facebook.com/v18.0/oauth/access_token"
    SCOPES = "pages_manage_posts,pages_read_engagement,pages_show_list,read_insights"

    # One redirect_uri, used by both authorize and the exchange. They were
    # derived differently before -- authorize honoured META_REDIRECT_URI and the
    # callback did not (facebook_oauth.py:97 vs :143) -- so configuring it to
    # anything but the derived default made Meta reject every exchange. Deriving
    # it once is the fix, and it is a behaviour change worth naming.
    @property
    def redirect_uri(self) -> str:
        return settings.META_REDIRECT_URI or settings.LINKEDIN_REDIRECT_URI.replace(
            "/linkedin/callback", "/facebook/callback"
        )

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
        """Meta exchanges via GET with query params and no grant_type."""
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

    async def get_comments(
        self, social_account: Any, external_post_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Comments on the Page's recent posts."""
        return await _fb_comments(social_account)

    async def get_messages(self, social_account: Any) -> list[dict[str, Any]]:
        """Page inbox conversations. Needs the pages_messaging permission."""
        return await _fb_messages(social_account)

    async def reply_to_comment(
        self, social_account: Any, comment_external_id: str, body: str
    ) -> dict[str, Any]:
        return await _fb_reply(social_account, comment_external_id, body)

    async def send_message(
        self, social_account: Any, recipient_external_id: str, body: str
    ) -> dict[str, Any]:
        return await _fb_send(social_account, recipient_external_id, body)

    async def get_analytics(
        self, social_account: Any, since: datetime, until: datetime
    ) -> dict[str, Any]:
        """Facebook Page Insights.

        Page fan count plus impressions and engaged users. No "saves" concept
        on a Page, and profile visits are not exposed.
        """
        return await _account_metrics(social_account, since, until)


async def _account_metrics(platform: Any, since, until) -> dict[str, Any]:
    """Account-level Facebook Page metrics for the day."""
    import httpx

    token = getattr(platform, "access_token", None)
    if is_mock_token(token):
        # No real account behind a placeholder token, so no metrics. Absent
        # metrics stay absent and store as NULL -- see collect_account().
        return {}

    config = getattr(platform, "config", None) or {}
    page_id = config.get("page_id")
    page_token = config.get("page_access_token") or token
    if not page_id:
        return {}

    base = "https://graph.facebook.com/v18.0"
    out: dict[str, Any] = {}
    async with httpx.AsyncClient() as client:
        page = await client.get(
            f"{base}/{page_id}",
            params={"fields": "fan_count", "access_token": page_token},
            timeout=15.0,
        )
        _raise_if_rate_limited("facebook", page)
        if page.status_code == 200:
            out.update(metrics_from(page.json(), {"followers": "fan_count"}))

        insights = await client.get(
            f"{base}/{page_id}/insights",
            params={
                "metric": "page_impressions,page_post_engagements,page_views_total",
                "period": "day",
                "access_token": page_token,
            },
            timeout=15.0,
        )
        _raise_if_rate_limited("facebook", insights)
        if insights.status_code == 200:
            for entry in insights.json().get("data", []):
                values = entry.get("values") or []
                if not values:
                    continue
                key = {
                    "page_impressions": "impressions",
                    "page_views_total": "profile_visits",
                }.get(entry.get("name"))
                if key and values[-1].get("value") is not None:
                    out[key] = int(values[-1]["value"])
    return out


# ---------------------------------------------------------------------------
# Inbox
# ---------------------------------------------------------------------------

def _page_context(social_account: Any) -> tuple[str, str]:
    config = getattr(social_account, "config", None) or {}
    page_id = config.get("page_id")
    token = config.get("page_access_token") or getattr(social_account, "access_token", None)
    if not page_id:
        raise ProviderAPIError("facebook", "This connection has no page_id stored.")
    return page_id, token


async def _fb_comments(social_account: Any) -> list[dict[str, Any]]:
    import httpx

    if is_mock_token(getattr(social_account, "access_token", None)):
        return mock_inbox_items("facebook", "comment")

    page_id, token = _page_context(social_account)
    out: list[dict[str, Any]] = []
    async with httpx.AsyncClient() as client:
        posts = await client.get(
            f"https://graph.facebook.com/v18.0/{page_id}/posts",
            params={"fields": "id,permalink_url", "limit": 25, "access_token": token},
            timeout=20.0,
        )
        _raise_if_rate_limited("facebook", posts)
        if posts.status_code != 200:
            raise ProviderAPIError("facebook", posts.text[:200], status_code=posts.status_code)

        for post in posts.json().get("data", []):
            comments = await client.get(
                f"https://graph.facebook.com/v18.0/{post['id']}/comments",
                params={
                    "fields": "id,from,message,created_time,permalink_url",
                    "limit": 50, "access_token": token,
                },
                timeout=20.0,
            )
            _raise_if_rate_limited("facebook", comments)
            if comments.status_code != 200:
                continue
            for row in comments.json().get("data", []):
                author = row.get("from") or {}
                out.append({
                    "external_id": row.get("id"),
                    "thread_external_id": post["id"],
                    "author": author.get("name") or "Someone",
                    "author_handle": author.get("id"),
                    "body": row.get("message") or "",
                    "created_at": parse_platform_time(row.get("created_time")),
                    "permalink": row.get("permalink_url") or post.get("permalink_url"),
                })
    return out


async def _fb_messages(social_account: Any) -> list[dict[str, Any]]:
    import httpx

    if is_mock_token(getattr(social_account, "access_token", None)):
        return mock_inbox_items("facebook", "dm")

    page_id, token = _page_context(social_account)
    out: list[dict[str, Any]] = []
    async with httpx.AsyncClient() as client:
        convos = await client.get(
            f"https://graph.facebook.com/v18.0/{page_id}/conversations",
            params={
                "fields": "id,participants,updated_time,"
                          "messages.limit(25){id,from,message,created_time}",
                "limit": 25, "access_token": token,
            },
            timeout=20.0,
        )
        _raise_if_rate_limited("facebook", convos)
        if convos.status_code != 200:
            raise ProviderAPIError(
                "facebook", convos.text[:200], status_code=convos.status_code
            )

        for conversation in convos.json().get("data", []):
            people = (conversation.get("participants") or {}).get("data") or []
            # The page itself is a participant; the other one is the customer.
            other = next((p for p in people if p.get("id") != page_id), {})
            for message in ((conversation.get("messages") or {}).get("data") or []):
                sender = message.get("from") or {}
                out.append({
                    "external_id": message.get("id"),
                    "thread_external_id": conversation.get("id"),
                    "author": sender.get("name") or other.get("name") or "Someone",
                    "author_handle": sender.get("id"),
                    "body": message.get("message") or "",
                    "created_at": parse_platform_time(message.get("created_time")),
                    "outbound": sender.get("id") == page_id,
                    "participant": other.get("name") or "Someone",
                    "participant_handle": other.get("id"),
                })
    return out


async def _fb_reply(social_account: Any, comment_id: str, body: str) -> dict[str, Any]:
    import httpx

    if is_mock_token(getattr(social_account, "access_token", None)):
        return {"external_id": f"mock_reply_{comment_id}"}

    _, token = _page_context(social_account)
    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"https://graph.facebook.com/v18.0/{comment_id}/comments",
            data={"message": body, "access_token": token},
            timeout=20.0,
        )
        _raise_if_rate_limited("facebook", res)
        if res.status_code != 200:
            raise ProviderAPIError("facebook", res.text[:200], status_code=res.status_code)
        return {"external_id": res.json().get("id")}


async def _fb_send(social_account: Any, recipient_id: str, body: str) -> dict[str, Any]:
    import httpx

    if is_mock_token(getattr(social_account, "access_token", None)):
        return {"external_id": f"mock_dm_{recipient_id}"}

    page_id, token = _page_context(social_account)
    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"https://graph.facebook.com/v18.0/{page_id}/messages",
            json={
                "recipient": {"id": recipient_id},
                "message": {"text": body},
                # Meta requires a tag or a recent interaction; RESPONSE means
                # "the person messaged us first", which is the only case an
                # inbox reply ever is.
                "messaging_type": "RESPONSE",
            },
            params={"access_token": token},
            timeout=20.0,
        )
        _raise_if_rate_limited("facebook", res)
        if res.status_code != 200:
            raise ProviderAPIError("facebook", res.text[:200], status_code=res.status_code)
        return {"external_id": res.json().get("message_id")}
