"""The X (Twitter) connector.

Publishing and metrics moved verbatim from the old ``platform_service.py``
(publish :937-1019), then converted from blocking ``httpx.Client`` to
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
    PostVariant,
    PublishResult,
    SocialProvider,
    OAuthTokens,
    tokens_from,
    ProviderAPIError,
    TokenRefreshResult,
    expires_at_from,
    provider_request,
    require_refresh_token,
    classify_retryable,
    mock_metrics_fallback,
)
from app.connectors.media import (
    _content_with_hashtags,
    _first_media_url,
)

from app.core.config import settings

logger = logging.getLogger(__name__)


async def publish_to_twitter(post: Any, platform: Any) -> dict[str, Any]:
    """Publish a text tweet via the X (Twitter) API v2.

    Note: media (image/video) upload uses X's separate chunked-upload API
    and is not implemented yet, so any attachment is ignored and only the
    text is posted.
    """
    import httpx
    import uuid

    access_token = getattr(platform, "access_token", None)
    if not access_token:
        raise ValueError(
            "This X account has no access token. Reconnect it using the "
            "'Connect X (Twitter)' button."
        )

    token_lower = access_token.lower()
    if (
        token_lower == "mock_token"
        or token_lower.startswith("mock_")
        or token_lower.startswith("test_")
    ):
        logger.info("Explicit mock token detected for X publishing, using simulated success.")
        tweet_id = f"tw_mock_{uuid.uuid4().hex[:8]}"
        username = (getattr(platform, "config", None) or {}).get("username") or "user"
        return {
            "status": "success",
            "platform": "twitter",
            "external_post_id": tweet_id,
            "post_url": f"https://x.com/{username}/status/{tweet_id}",
            "published_at": datetime.now(timezone.utc).isoformat(),
        }

    # Include hashtags, trimming content if needed to stay within X's 280 chars.
    text = _content_with_hashtags(post, limit=280)
    if not text.strip():
        raise ValueError("X requires non-empty text content to post a tweet.")

    if _first_media_url(post):
        logger.info("X media upload is not supported yet — posting text only.")

    logger.info("Publishing tweet for X account %s", getattr(platform, "account_name", "unknown"))
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        res = await client.post(
            "https://api.twitter.com/2/tweets",
            headers=headers,
            json={"text": text},
            timeout=30.0,
        )
        if res.status_code in (200, 201):
            res_data = res.json().get("data", {})
            tweet_id = res_data.get("id")
            username = (getattr(platform, "config", None) or {}).get("username")
            post_url = f"https://x.com/{username}/status/{tweet_id}" if username and tweet_id else f"https://x.com/i/status/{tweet_id}"
            logger.info("Successfully published tweet to X: %s", post_url)
            return {
                "status": "success",
                "platform": "twitter",
                "external_post_id": tweet_id,
                "post_url": post_url,
                "published_at": datetime.now(timezone.utc).isoformat(),
            }
        else:
            logger.error("X tweet publishing failed with status %s: %s", res.status_code, res.text)
            err_detail = res.text
            try:
                err_json = res.json()
                err_detail = err_json.get("detail") or err_json.get("title") or err_json.get("message") or res.text
            except Exception:
                pass
            if res.status_code == 402 or "credits-depleted" in res.text or "credits depleted" in res.text:
                raise ValueError(
                    "X (Twitter) API Error (402 Payment Required): Your X Developer API monthly posting credits have been depleted. "
                    "Please check your X Developer portal subscription or billing on developer.x.com."
                )
            raise ValueError(f"X (Twitter) API error ({res.status_code}): {err_detail}")



class TwitterProvider(SocialProvider):
    slug = "twitter"
    name = "X (Twitter)"
    capabilities = Capabilities(
        # publish_to_twitter drops media silently (platform_service.py:977-978);
        # this reports the connector's real capability rather than the API's.
        supports_images=False,
        supports_video=False,
        supports_carousel=False,
        supports_link_posts=True,
        supports_comments_api=False,
        supports_dm_api=False,
        # The 280 the composer should be enforcing. It is also what
        # _content_with_hashtags is already called with at platform_service.py:973.
        max_chars=280,
        max_images=0,
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
            result = await publish_to_twitter(variant.post, social_account)
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
        """X (Twitter) has no implemented metrics fetch.

        Returns fabricated numbers, exactly as before -- see
        :func:`app.connectors.base.mock_metrics_fallback`.
        """
        return mock_metrics_fallback(self.slug)

    async def refresh_token(self, social_account: Any) -> TokenRefreshResult:
        """Moved from social_accounts.py:812-868.

        X puts the client credentials in HTTP Basic when a secret is
        configured, and in the body otherwise (a public PKCE client).
        """
        token = require_refresh_token(self.slug, social_account)
        auth = (
            (settings.TWITTER_CLIENT_ID, settings.TWITTER_CLIENT_SECRET)
            if settings.TWITTER_CLIENT_SECRET
            else None
        )
        payload = await provider_request(
            self.slug,
            "https://api.twitter.com/2/oauth2/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": token,
                "client_id": settings.TWITTER_CLIENT_ID,
            },
            auth=auth,
        )
        access = payload.get("access_token")
        if not access:
            raise ProviderAPIError(self.slug, "X returned no access token")
        return TokenRefreshResult(
            access_token=access,
            # X rotates the refresh token; keeping the old one locks the
            # account out at the next refresh.
            refresh_token=payload.get("refresh_token") or token,
            expires_at=expires_at_from(payload),
            message="X (Twitter) access token refreshed successfully",
        )

    AUTH_URL = "https://twitter.com/i/oauth2/authorize"
    TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
    # offline.access is what makes X return a refresh token at all.
    SCOPES = "tweet.read tweet.write users.read offline.access"

    @property
    def redirect_uri(self) -> str:
        return settings.TWITTER_REDIRECT_URI

    def is_configured(self) -> bool:
        return bool(settings.TWITTER_CLIENT_ID)

    @staticmethod
    def pkce_pair() -> tuple[str, str]:
        """(code_verifier, code_challenge) for PKCE S256."""
        import base64
        import hashlib
        import secrets

        verifier = secrets.token_urlsafe(64)[:100]
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        return verifier, challenge

    def build_authorize_url(self, state: str, challenge: str) -> str:
        from urllib.parse import urlencode

        return f"{self.AUTH_URL}?" + urlencode({
            "response_type": "code",
            "client_id": settings.TWITTER_CLIENT_ID,
            "redirect_uri": self.redirect_uri,
            "scope": self.SCOPES,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        })

    async def exchange_code(self, code: str, code_verifier: str) -> OAuthTokens:
        auth = (
            (settings.TWITTER_CLIENT_ID, settings.TWITTER_CLIENT_SECRET)
            if settings.TWITTER_CLIENT_SECRET
            else None
        )
        payload = await provider_request(
            self.slug,
            self.TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "code_verifier": code_verifier,
                "client_id": settings.TWITTER_CLIENT_ID,
            },
            auth=auth,
        )
        return tokens_from(payload)
