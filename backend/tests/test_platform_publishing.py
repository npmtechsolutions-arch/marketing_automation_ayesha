"""Publishing to X/Twitter.

These call the moved function directly. It came from
``PlatformService.publish_to_twitter`` and is unchanged, so these passing
against ``app.connectors.twitter`` is the check that the move preserved
behaviour.

Migrated from the ad-hoc ``backend/test_twitter_publishing.py``, which was the
only one of the old manual scripts carrying real assertions -- the rest printed
results, needed a running server, or called live third-party APIs with real
credentials, so they were deleted rather than moved.
"""

from unittest.mock import MagicMock

import httpx
import pytest

from app.connectors.twitter import publish_to_twitter

pytestmark = pytest.mark.asyncio


def _mock_x_api(monkeypatch, status_code: int, payload: dict, text: str = ""):
    """Answer X's tweet endpoint with a canned response.

    The publisher now uses httpx.AsyncClient, so patching the class with a
    MagicMock no longer works -- the calls are awaited. This is the pattern the
    rest of the suite uses for outbound HTTP (see tests/test_email_service.py).
    """
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload, text=text or None)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **k: real_client(*a, **{**k, "transport": httpx.MockTransport(handler)}),
    )


def _platform(access_token: str, username: str) -> MagicMock:
    platform = MagicMock()
    platform.access_token = access_token
    platform.account_name = "Test Account"
    platform.config = {"username": username}
    return platform


def _post(content: str) -> MagicMock:
    post = MagicMock()
    post.content = content
    post.media_urls = None
    return post


async def test_mock_token_returns_simulated_success():
    """A token that is explicitly a mock short-circuits to a fake success, so
    development and seeded data do not call the live API."""
    result = await publish_to_twitter(
        _post("Test tweet content"), _platform("mock_token_123", "testuser")
    )

    assert result["status"] == "success"
    assert result["platform"] == "twitter"
    assert "https://x.com/testuser/status/" in result["post_url"]


async def test_real_token_publishes_and_returns_the_tweet_url(monkeypatch):
    _mock_x_api(monkeypatch, 201, {"data": {"id": "1829304958671"}})

    result = await publish_to_twitter(
        _post("A tweet."), _platform("real_oauth2_token_xyz", "someaccount")
    )

    assert result["status"] == "success"
    assert result["external_post_id"] == "1829304958671"
    assert result["post_url"] == "https://x.com/someaccount/status/1829304958671"


async def test_api_error_raises_with_an_actionable_message(monkeypatch):
    """A 402 from X means the account is out of credits. The error has to say
    so -- a generic failure sends someone hunting through logs for a billing
    problem."""
    _mock_x_api(
        monkeypatch, 402,
        {"detail": "credits depleted", "status": 402, "title": "Payment Required"},
    )

    with pytest.raises(ValueError) as exc:
        await publish_to_twitter(
            _post("Test tweet"), _platform("real_oauth2_token_xyz", "someaccount")
        )

    assert "credits have been depleted" in str(exc.value)
