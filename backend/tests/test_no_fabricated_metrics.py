"""No metric a user sees may be invented.

Walk A found `TwitterConnector.get_post_metrics` and its LinkedIn twin both
returning `mock_metrics_fallback(...)` -- random integers -- unconditionally,
on real accounts with real credentials. Three consecutive reads of one post
returned 755, 72 and 674 likes. Those numbers reached post cards, the analytics
dashboards, and the PDF reports agencies send to their clients, with nothing to
mark them as anything other than measurements.

Two more fabrication sites came out of the same audit and were worse, because
they only fire in production when something is already wrong:

* every connector's `except Exception` in the metrics fetch logged "falling
  back to mock" and returned random integers -- so an expired token, a rate
  limit or a provider outage produced plausible engagement and hid the failure;
* `is_mock_token()` matches any token merely *containing* "test" and returns
  True for an empty one, so the "development placeholder" paths were reachable
  with live credentials or a token that failed to decrypt.

The structural test at the bottom is the one that matters long-term: it fails
if `random` reappears anywhere in the connector package.
"""

import pathlib
import re
from unittest.mock import MagicMock

import pytest

from app.connectors.base import NotSupportedError
from app.connectors.registry import get_provider, known_slugs

pytestmark = pytest.mark.asyncio

CONNECTORS = pathlib.Path("app/connectors")


def _account(token="real-token-abc123", slug="twitter"):
    account = MagicMock()
    account.access_token = token
    account.config = {}
    account.platform = MagicMock()
    account.platform.slug = slug
    return account


# ---------------------------------------------------------------------------
# The platforms with no implemented metrics fetch refuse rather than invent
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("slug", ["twitter", "linkedin"])
async def test_platforms_without_a_metrics_api_raise_not_supported(slug):
    """The honest answer to "how did this post do" is "we cannot tell"."""
    provider = get_provider(slug)

    with pytest.raises(NotSupportedError):
        await provider.get_post_metrics("ext-123", _account(slug=slug))


@pytest.mark.parametrize("slug", ["twitter", "linkedin"])
async def test_they_refuse_for_a_real_looking_token_too(slug):
    """Not gated on the token being a placeholder.

    The bug was unconditional, and a fix that only refused for mock tokens
    would leave real accounts fabricating -- which was the whole defect.
    """
    provider = get_provider(slug)

    with pytest.raises(NotSupportedError):
        await provider.get_post_metrics(
            "ext-123", _account(token="AAAAAAAAAAAAAAAAAAAAA-live-credential")
        )


# ---------------------------------------------------------------------------
# A placeholder token reports nothing rather than something plausible
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("slug", ["facebook", "instagram", "youtube"])
async def test_a_placeholder_token_yields_no_post_metrics(slug):
    provider = get_provider(slug)

    metrics = await provider.get_post_metrics("ext-123", _account("mock_token", slug))

    assert metrics == {}, f"{slug} invented {metrics}"


@pytest.mark.parametrize("slug", known_slugs())
async def test_a_placeholder_token_yields_no_account_metrics(slug):
    """Account-level metrics feed analytics_daily -- followers, reach.

    ``collect_account`` stores absent metrics as NULL, so an empty mapping is
    the way to say "nothing measured" rather than writing a zero.
    """
    from datetime import datetime, timedelta, timezone

    provider = get_provider(slug)
    since = datetime.now(timezone.utc) - timedelta(days=1)

    try:
        metrics = await provider.get_analytics(
            _account("mock_token", slug), since, since + timedelta(days=1)
        )
    except NotSupportedError:
        return  # refusing outright is also honest

    assert metrics == {}, f"{slug} invented account metrics: {metrics}"


async def test_an_empty_token_is_not_treated_as_a_measurable_account():
    """`is_mock_token(None)` is True, so this path is reachable whenever a
    token is missing or failed to decrypt -- not only in development."""
    provider = get_provider("facebook")

    assert await provider.get_post_metrics("ext-123", _account(None, "facebook")) == {}


# ---------------------------------------------------------------------------
# The structural guard
# ---------------------------------------------------------------------------

def test_no_connector_generates_random_numbers():
    """The cheapest possible insurance against this coming back.

    Every fabrication in this package was a `random.randint` call. Three of
    them survived a full connector extraction because each was individually
    plausible in review -- "mock data for development" -- and nothing looked at
    them together.
    """
    offenders = []
    for path in sorted(CONNECTORS.rglob("*.py")):
        for number, line in enumerate(path.read_text().splitlines(), 1):
            code = line.split("#", 1)[0]
            if re.search(r"\brandom\s*\.", code) or re.search(
                r"^\s*(import random|from random import)\b", code
            ):
                offenders.append(f"{path}:{number}: {line.strip()}")

    assert not offenders, (
        "connectors must not generate numbers a user could mistake for "
        "measurements:\n" + "\n".join(offenders)
    )
