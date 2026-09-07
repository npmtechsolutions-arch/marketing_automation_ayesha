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

from unittest.mock import MagicMock, patch

import pytest

from app.connectors.twitter import publish_to_twitter


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


def test_mock_token_returns_simulated_success():
    """A token that is explicitly a mock short-circuits to a fake success, so
    development and seeded data do not call the live API."""
    result = publish_to_twitter(
        _post("Test tweet content"), _platform("mock_token_123", "testuser")
    )

    assert result["status"] == "success"
    assert result["platform"] == "twitter"
    assert "https://x.com/testuser/status/" in result["post_url"]


@patch("httpx.Client")
def test_real_token_publishes_and_returns_the_tweet_url(mock_httpx):
    client = MagicMock()
    mock_httpx.return_value.__enter__.return_value = client
    response = MagicMock()
    response.status_code = 201
    response.json.return_value = {"data": {"id": "1829304958671"}}
    client.post.return_value = response

    result = publish_to_twitter(
        _post("A tweet."), _platform("real_oauth2_token_xyz", "someaccount")
    )

    assert result["status"] == "success"
    assert result["external_post_id"] == "1829304958671"
    assert result["post_url"] == "https://x.com/someaccount/status/1829304958671"


@patch("httpx.Client")
def test_api_error_raises_with_an_actionable_message(mock_httpx):
    """A 402 from X means the account is out of credits. The error has to say
    so -- a generic failure sends someone hunting through logs for a billing
    problem."""
    client = MagicMock()
    mock_httpx.return_value.__enter__.return_value = client
    response = MagicMock()
    response.status_code = 402
    response.text = '{"detail":"credits depleted","status":402}'
    response.json.return_value = {
        "detail": "credits depleted",
        "status": 402,
        "title": "Payment Required",
    }
    client.post.return_value = response

    with pytest.raises(ValueError) as exc:
        publish_to_twitter(
            _post("Test tweet"), _platform("real_oauth2_token_xyz", "someaccount")
        )

    assert "credits have been depleted" in str(exc.value)
