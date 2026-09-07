"""The LinkedIn connector.

Publishing and metrics moved verbatim from ``app/services/platform_service.py``
(publish :831-935, image upload :781-829). The bodies are unchanged, including their quirks -- this was a move,
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
    mock_metrics_fallback,
)
from app.connectors.media import (
    _content_with_hashtags,
    _download_media_bytes,
    _first_media_url,
)

from app.core.config import settings

logger = logging.getLogger(__name__)


def _linkedin_upload_image(author_urn: str, media_url: str, access_token: str) -> str:
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
    with httpx.Client() as client:
        reg = client.post(
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

        image_bytes = _download_media_bytes(media_url)
        up = client.put(
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


def publish_to_linkedin(post: Any, platform: Any) -> dict[str, Any]:
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
        asset_urn = _linkedin_upload_image(
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

    with httpx.Client() as client:
        res = client.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers=headers,
            json=ugc_payload,
            timeout=30.0,
        )
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
        supports_dm_api=False,
        max_chars=3000,
        max_images=9,
        max_video_seconds=None,
        max_video_bytes=None,
    )

    async def publish_post(
        self,
        variant: PostVariant,
        media: list[MediaRef],
        social_account: Any,
    ) -> PublishResult:
        try:
            result = await asyncio.to_thread(
                publish_to_linkedin, variant.post, social_account
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
        """LinkedIn has no implemented metrics fetch.

        Returns fabricated numbers, exactly as before -- see
        :func:`app.connectors.base.mock_metrics_fallback`.
        """
        return mock_metrics_fallback(self.slug)

    async def refresh_token(self, social_account: Any) -> TokenRefreshResult:
        """Moved from social_accounts.py:754-810."""
        token = require_refresh_token(self.slug, social_account)
        payload = await asyncio.to_thread(
            refresh_sync,
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
        payload = await exchange_code_async(
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
