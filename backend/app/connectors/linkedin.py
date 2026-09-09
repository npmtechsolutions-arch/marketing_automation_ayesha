"""The LinkedIn connector.

Publishing and metrics moved verbatim from the old ``platform_service.py``
(publish :831-935, image upload :781-829), then converted from blocking ``httpx.Client`` to
``httpx.AsyncClient``. Nothing waits on a thread here: the requests are
awaited, so a slow platform costs a coroutine rather than one of the process's
shared worker threads.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from app.connectors.base import (
    NotSupportedError,
    Capabilities,
    MediaRef,
    ResolvedContent,
    PublishResult,
    PlatformRateLimited,
    SocialProvider,
    is_mock_token,
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
)
from app.connectors.media import (
    _content_with_hashtags,
    _download_media_bytes,
    _first_media_url,
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


async def _linkedin_upload_image(author_urn: str, media_url: str, access_token: str) -> str:
    """Register + upload an image to LinkedIn and return its asset URN."""
    import httpx

    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }
    register_payload = {
        "registerUploadRequest": {
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "owner": author_urn,
            "serviceRelationships": [
                {
                    "relationshipType": "OWNER",
                    "identifier": "urn:li:userGeneratedContent",
                }
            ],
        }
    }
    async with httpx.AsyncClient() as client:
        reg = await client.post(
            "https://api.linkedin.com/v2/assets?action=registerUpload",
            headers=headers,
            json=register_payload,
            timeout=30.0,
        )
        if reg.status_code not in (200, 201):
            raise ValueError(f"LinkedIn image registerUpload failed: {reg.text}")
        value = reg.json()["value"]
        asset_urn = value["asset"]
        upload_url = value["uploadMechanism"][
            "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
        ]["uploadUrl"]

        image_bytes = await _download_media_bytes(media_url)
        up = await client.put(
            upload_url,
            headers={"Authorization": f"Bearer {access_token}"},
            content=image_bytes,
            timeout=90.0,
        )
        if up.status_code not in (200, 201):
            raise ValueError(
                f"LinkedIn image binary upload failed: {up.status_code} {up.text}"
            )
    return asset_urn


async def publish_to_linkedin(post: Any, platform: Any) -> dict[str, Any]:
    """Publish a post to LinkedIn (personal profile or organization page).

    Supports text and single-image posts via the UGC Posts API. The author
    URN and target ('personal'/'organization') come from the account's
    ``config`` populated during the OAuth connect flow.

    Note: LinkedIn *Job postings* and *Ads* require a vetted LinkedIn
    partnership (Talent Solutions / Marketing Developer Platform) and are
    not available through a standard app — those are surfaced as errors.
    """
    import httpx
    import uuid

    access_token = getattr(platform, "access_token", None)
    if not access_token:
        raise ValueError(
            "This LinkedIn account has no access token. Reconnect it using "
            "the 'Connect LinkedIn' button."
        )

    # Mock token fallback for local dev / testing
    if "mock" in access_token or "test" in access_token or access_token.startswith("refreshed_"):
        logger.info("Mock token detected for LinkedIn publishing, bypassing API call.")
        return {
            "status": "success",
            "platform": "linkedin",
            "external_post_id": f"li_mock_{uuid.uuid4().hex[:8]}",
            "published_at": datetime.now(timezone.utc).isoformat(),
        }

    config = getattr(platform, "config", None) or {}
    author_urn = config.get("author_urn")
    if not author_urn and config.get("member_id"):
        author_urn = f"urn:li:person:{config['member_id']}"
    if not author_urn:
        raise ValueError(
            "This LinkedIn account is missing its author URN. Please "
            "reconnect it using the 'Connect LinkedIn' button."
        )

    logger.info("Publishing to LinkedIn author %s", author_urn)

    text = _content_with_hashtags(post)
    media_url = _first_media_url(post)

    share_media: list[dict[str, Any]] = []
    media_category = "NONE"

    if media_url:
        is_video = any(
            ext in media_url.lower() for ext in [".mp4", ".mov", ".avi", ".mkv"]
        )
        if is_video:
            raise ValueError(
                "LinkedIn video publishing is not supported yet. Post text or "
                "an image, or remove the video attachment."
            )
        asset_urn = await _linkedin_upload_image(
            author_urn, media_url, access_token
        )
        share_media = [{"status": "READY", "media": asset_urn}]
        media_category = "IMAGE"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }
    share_content: dict[str, Any] = {
        "shareCommentary": {"text": text},
        "shareMediaCategory": media_category,
    }
    if share_media:
        share_content["media"] = share_media

    ugc_payload = {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {"com.linkedin.ugc.ShareContent": share_content},
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }

    async with httpx.AsyncClient() as client:
        res = await client.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers=headers,
            json=ugc_payload,
            timeout=30.0,
        )
        _raise_if_rate_limited("linkedin", res)
        if res.status_code not in (200, 201):
            raise ValueError(f"LinkedIn UGC post failed: {res.text}")
        post_urn = res.headers.get("x-restli-id") or res.json().get("id")

    post_url = (
        f"https://www.linkedin.com/feed/update/{post_urn}" if post_urn else None
    )
    return {
        "status": "success",
        "platform": "linkedin",
        "external_post_id": post_urn,
        "post_url": post_url,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }



class LinkedInProvider(SocialProvider):
    slug = "linkedin"
    name = "LinkedIn"
    capabilities = Capabilities(
        supports_images=True,
        # publish_to_linkedin rejects video outright (platform_service.py:885-889),
        # so this reports what the connector does, not what LinkedIn allows.
        supports_video=False,
        supports_carousel=False,
        supports_link_posts=True,
        supports_comments_api=True,
        # LinkedIn's messaging API is partner-gated and not generally
        # available, so get_messages stays unsupported rather than pretending.
        supports_dm_api=False,
        max_chars=3000,
        max_images=9,
        max_video_seconds=None,
        max_video_bytes=None,
    )

    async def publish_post(
        self,
        variant: ResolvedContent,
        media: list[MediaRef],
        social_account: Any,
    ) -> PublishResult:
        try:
            result = await publish_to_linkedin(variant.post, social_account)
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
        """LinkedIn exposes no implemented metrics fetch, so this reports nothing.

        Same history and same reasoning as
        :meth:`app.connectors.twitter.TwitterConnector.get_post_metrics`: this
        returned fabricated integers on real accounts. A real implementation
        would use the ``socialActions`` and ``organizationalEntityShareStatistics``
        endpoints, both of which need an approved Marketing Developer Platform
        application.
        """
        raise NotSupportedError(self.slug, "get_post_metrics")

    async def refresh_token(self, social_account: Any) -> TokenRefreshResult:
        """Moved from social_accounts.py:754-810."""
        token = require_refresh_token(self.slug, social_account)
        payload = await provider_request(
            self.slug,
            "https://www.linkedin.com/oauth/v2/accessToken",
            data={
                "grant_type": "refresh_token",
                "refresh_token": token,
                "client_id": settings.LINKEDIN_CLIENT_ID,
                "client_secret": settings.LINKEDIN_CLIENT_SECRET,
            },
        )
        access = payload.get("access_token")
        if not access:
            raise ProviderAPIError(self.slug, "LinkedIn returned no access token")
        return TokenRefreshResult(
            access_token=access,
            refresh_token=payload.get("refresh_token") or token,
            expires_at=expires_at_from(payload),
            message="LinkedIn access token refreshed successfully",
        )

    AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
    TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
    # Personal scopes come with "Sign In with LinkedIn"; organization scopes
    # additionally need the Community Management API product.
    SCOPES = {
        "personal": "openid profile email w_member_social",
        "organization": (
            "openid profile email w_member_social "
            "r_organization_social w_organization_social rw_organization_admin"
        ),
    }

    @property
    def redirect_uri(self) -> str:
        return settings.LINKEDIN_REDIRECT_URI

    def is_configured(self) -> bool:
        return bool(settings.LINKEDIN_CLIENT_ID and settings.LINKEDIN_CLIENT_SECRET)

    def build_authorize_url(self, state: str, target: str = "personal") -> str:
        from urllib.parse import urlencode

        return f"{self.AUTH_URL}?" + urlencode({
            "response_type": "code",
            "client_id": settings.LINKEDIN_CLIENT_ID,
            "redirect_uri": self.redirect_uri,
            "state": state,
            "scope": self.SCOPES[target],
        })

    async def exchange_code(self, code: str) -> OAuthTokens:
        payload = await provider_request(
            self.slug,
            self.TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "client_id": settings.LINKEDIN_CLIENT_ID,
                "client_secret": settings.LINKEDIN_CLIENT_SECRET,
            },
        )
        return tokens_from(payload)

    async def get_comments(
        self, social_account: Any, external_post_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Comments on the organization's recent posts."""
        return await _li_comments(social_account)

    async def reply_to_comment(
        self, social_account: Any, comment_external_id: str, body: str
    ) -> dict[str, Any]:
        return await _li_reply(social_account, comment_external_id, body)

    async def get_analytics(
        self, social_account: Any, since: datetime, until: datetime
    ) -> dict[str, Any]:
        """LinkedIn follower statistics.

        Organization pages expose follower counts and share statistics;
        personal profiles expose almost nothing. Saves and profile visits do
        not exist in the API at all, so they stay absent rather than zero.
        """
        return await _account_metrics(social_account, since, until)


async def _account_metrics(platform: Any, since, until) -> dict[str, Any]:
    """LinkedIn follower statistics. Organization pages only."""
    import httpx

    token = getattr(platform, "access_token", None)
    if is_mock_token(token):
        # No real account behind a placeholder token, so no metrics. Absent
        # metrics stay absent and store as NULL -- see collect_account().
        return {}

    config = getattr(platform, "config", None) or {}
    urn = config.get("author_urn") or ""
    if "organization" not in urn:
        # A personal profile exposes no statistics endpoint. Absent rather
        # than zero -- there is nothing to report, which is not the same as
        # reporting nothing.
        return {}

    out: dict[str, Any] = {}
    async with httpx.AsyncClient() as client:
        res = await client.get(
            "https://api.linkedin.com/v2/networkSizes/" + urn,
            params={"edgeType": "CompanyFollowedByMember"},
            headers={
                "Authorization": f"Bearer {token}",
                "X-Restli-Protocol-Version": "2.0.0",
            },
            timeout=15.0,
        )
        _raise_if_rate_limited("linkedin", res)
        if res.status_code == 200:
            out.update(metrics_from(res.json(), {"followers": "firstDegreeSize"}))
    return out


# ---------------------------------------------------------------------------
# Inbox
# ---------------------------------------------------------------------------

def _li_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": "202405",
    }


async def _li_comments(social_account: Any) -> list[dict[str, Any]]:
    import httpx

    token = getattr(social_account, "access_token", None)
    if is_mock_token(token):
        return mock_inbox_items("linkedin", "comment")

    config = getattr(social_account, "config", None) or {}
    urn = config.get("author_urn") or ""
    if "organization" not in urn:
        # Comments are readable on organization posts. A personal profile has
        # no equivalent endpoint, and saying so is better than an empty inbox.
        raise NotSupportedError(
            "linkedin", "get_comments on a personal profile"
        )

    out: list[dict[str, Any]] = []
    async with httpx.AsyncClient() as client:
        posts = await client.get(
            "https://api.linkedin.com/rest/posts",
            params={"author": urn, "q": "author", "count": 20},
            headers=_li_headers(token), timeout=20.0,
        )
        _raise_if_rate_limited("linkedin", posts)
        if posts.status_code != 200:
            raise ProviderAPIError(
                "linkedin", posts.text[:200], status_code=posts.status_code
            )

        for post in posts.json().get("elements", []):
            post_urn = post.get("id")
            if not post_urn:
                continue
            comments = await client.get(
                f"https://api.linkedin.com/rest/socialActions/{post_urn}/comments",
                headers=_li_headers(token), timeout=20.0,
            )
            _raise_if_rate_limited("linkedin", comments)
            if comments.status_code != 200:
                continue
            for row in comments.json().get("elements", []):
                message = (row.get("message") or {}).get("text") or ""
                out.append({
                    "external_id": row.get("$URN") or row.get("id"),
                    "thread_external_id": post_urn,
                    "author": row.get("actor") or "Someone",
                    "author_handle": row.get("actor"),
                    "body": message,
                    "created_at": parse_platform_time(
                        (row.get("created") or {}).get("time")
                    ),
                })
    return out


async def _li_reply(social_account: Any, comment_id: str, body: str) -> dict[str, Any]:
    import httpx

    token = getattr(social_account, "access_token", None)
    if is_mock_token(token):
        return {"external_id": f"mock_reply_{comment_id}"}

    config = getattr(social_account, "config", None) or {}
    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"https://api.linkedin.com/rest/socialActions/{comment_id}/comments",
            json={
                "actor": config.get("author_urn"),
                "message": {"text": body},
            },
            headers=_li_headers(token), timeout=20.0,
        )
        _raise_if_rate_limited("linkedin", res)
        if res.status_code not in (200, 201):
            raise ProviderAPIError(
                "linkedin", res.text[:200], status_code=res.status_code
            )
        return {"external_id": res.headers.get("x-restli-id")}
