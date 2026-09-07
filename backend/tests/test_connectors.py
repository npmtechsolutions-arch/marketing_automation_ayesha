"""The connector abstraction: registry, publish orchestration, capabilities.

Platform behaviour used to be spread across three layers, with the same
slug-substring if/elif chain written four times and each copy covering a
different set of platforms. These tests pin the seam that replaced it.

Publishing is exercised through a FakeProvider rather than the real ones, so
what is under test is the orchestration -- which targets are attempted, how
partial failure resolves, what lands in ``posting_results`` -- and not five
platforms' HTTP quirks.
"""

import uuid
from unittest.mock import MagicMock

import pytest

from app.connectors.base import (
    Capabilities,
    MediaRef,
    NotSupportedError,
    PostVariant,
    PublishResult,
    SocialProvider,
    classify_retryable,
)
from app.connectors.registry import get_provider, known_slugs

pytestmark = pytest.mark.asyncio

PASSWORD = "hunter2-correct-horse"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "slug,expected",
    [
        ("facebook", "facebook"),
        ("instagram", "instagram"),
        ("linkedin", "linkedin"),
        ("twitter", "twitter"),
        ("youtube", "youtube"),
        # The forms the old substring dispatch accepted, which real
        # SocialPlatform rows still carry.
        ("Facebook", "facebook"),
        ("insta", "instagram"),
        ("X (Twitter)", "twitter"),
        ("x", "twitter"),
        ("  YouTube  ", "youtube"),
    ],
)
async def test_registry_resolves_every_slug_the_old_dispatch_accepted(slug, expected):
    assert get_provider(slug).slug == expected


async def test_every_seeded_platform_has_a_provider():
    assert set(known_slugs()) == {
        "facebook", "instagram", "linkedin", "twitter", "youtube",
    }


async def test_unknown_slug_falls_back_to_instagram_and_says_so(caplog):
    """Pinning behaviour, not endorsing it.

    posts.py:639 sent any unrecognised platform to Instagram through a silent
    ``else``. The fallback is preserved so this stays a refactor; the warning
    is the only difference, because publishing someone's post to the wrong
    platform should not be quiet.
    """
    import logging

    with caplog.at_level(logging.WARNING, logger="app.connectors.registry"):
        provider = get_provider("tiktok")

    assert provider.slug == "instagram"
    assert "tiktok" in caplog.text
    assert "falling back" in caplog.text


async def test_a_known_slug_logs_no_warning(caplog):
    import logging

    with caplog.at_level(logging.WARNING, logger="app.connectors.registry"):
        get_provider("linkedin")
    assert caplog.text == ""


# ---------------------------------------------------------------------------
# Capabilities on the provider
# ---------------------------------------------------------------------------

async def test_capabilities_differ_per_platform():
    """The composer's hardcoded 2,200-character counter is wrong for four of
    the five platforms; this is the data that fixes it."""
    assert get_provider("twitter").capabilities.max_chars == 280
    assert get_provider("instagram").capabilities.max_chars == 2200
    assert get_provider("linkedin").capabilities.max_chars == 3000
    assert get_provider("youtube").capabilities.max_chars == 5000
    assert get_provider("facebook").capabilities.max_chars == 63206


async def test_capabilities_report_what_the_connector_actually_does():
    """Not what the platform's API allows.

    The X publisher drops media silently and the LinkedIn one rejects video
    outright, so reporting the platform's real limits here would promise
    something the connector will not deliver.
    """
    assert get_provider("twitter").capabilities.supports_images is False
    assert get_provider("linkedin").capabilities.supports_video is False
    assert get_provider("instagram").capabilities.supports_video is True


# ---------------------------------------------------------------------------
# NotSupportedError
# ---------------------------------------------------------------------------

async def test_unimplemented_capability_raises_not_supported():
    provider = get_provider("instagram")
    account = object()

    for call in (
        provider.get_messages(account),
        provider.get_posts(account),
        provider.get_comments(account),
    ):
        with pytest.raises(NotSupportedError):
            await call


async def test_not_supported_names_the_platform_and_capability():
    with pytest.raises(NotSupportedError) as exc:
        await get_provider("twitter").get_messages(object())

    assert exc.value.slug == "twitter"
    assert exc.value.capability == "get_messages"
    assert "twitter" in str(exc.value)


# ---------------------------------------------------------------------------
# Retry classification
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "error,retryable",
    [
        (429, True), (500, True), (502, True), (503, True), (504, True),
        (400, False), (401, False), (403, False), (404, False),
        ("HTTP 503 from platform", True),
        ("Request timed out", True),
        ("invalid_grant: token revoked", False),
        (None, False),
    ],
)
async def test_retry_classification(error, retryable):
    """A rate limit passes with time; a revoked token never does. Retrying the
    second only burns quota."""
    assert classify_retryable(error) is retryable


# ---------------------------------------------------------------------------
# Publish orchestration, through a FakeProvider
# ---------------------------------------------------------------------------

class FakeProvider(SocialProvider):
    """Records what it was asked to publish and returns scripted results."""

    slug = "instagram"  # registered over a real slug so the dispatch finds it
    name = "Fake"
    capabilities = Capabilities(supports_images=True, max_chars=100, max_images=1)

    def __init__(self, results):
        self.results = dict(results)  # social_account_id str -> PublishResult
        self.calls: list[tuple[PostVariant, list[MediaRef], Any]] = []

    async def publish_post(self, variant, media, social_account):
        self.calls.append((variant, media, social_account))
        return self.results.get(
            str(social_account.id),
            PublishResult(status="published", external_post_id="fake_1"),
        )


from typing import Any  # noqa: E402 - after FakeProvider for readability


@pytest.fixture
def fake_provider(monkeypatch):
    """Swap providers into the registry for the duration of a test."""
    from app.connectors import registry

    def _install(results):
        provider = FakeProvider(results)
        monkeypatch.setitem(registry._PROVIDERS, "instagram", provider)
        return provider

    return _install


@pytest.fixture(autouse=True)
def publish_uses_the_test_session(monkeypatch, db_session):
    """Point the publish worker at the test database.

    ``_do_publish_to_platforms`` takes only a post id and opens its own
    ``AsyncSessionLocal()`` -- it never sees the ``get_db`` override in
    conftest, so without this it would talk to the real Postgres while the test
    wrote to in-memory SQLite. Committing is suppressed for the same reason the
    other fixtures share one session: rolling it back is how the test isolates.
    """
    from contextlib import asynccontextmanager

    from app.api.v1.endpoints import posts as posts_module

    @asynccontextmanager
    async def _session():
        yield db_session

    def _factory():
        return _session()

    monkeypatch.setattr(posts_module, "AsyncSessionLocal", _factory)
    monkeypatch.setattr(db_session, "commit", db_session.flush)


@pytest.fixture
async def publishable(user_factory, account_factory, social_account_factory, db_session):
    """A post with two targets on the same platform, ready to publish."""
    from app.models.post import Post, PostStatus

    async def _make(target_count=2, status=PostStatus.PUBLISHING):
        owner = await user_factory(password=PASSWORD)
        account = await account_factory(owner)
        accounts = [
            await social_account_factory(owner, account, slug="instagram")
            for _ in range(target_count)
        ]
        post = Post(
            id=uuid.uuid4(),
            user_id=owner.id,
            account_id=account.id,
            content="Hello from the connector tests",
            status=status,
            target_accounts=[
                {
                    "social_account_id": str(sa.id),
                    "platform_name": "Instagram",
                    "account_name": sa.account_name,
                }
                for sa in accounts
            ],
        )
        db_session.add(post)
        await db_session.flush()
        return {"owner": owner, "account": account, "accounts": accounts, "post": post}

    return _make


async def _publish(post_id):
    from app.api.v1.endpoints.posts import _do_publish_to_platforms

    await _do_publish_to_platforms(post_id)


async def _reload(db_session, post_id):
    from sqlalchemy import select

    from app.models.post import Post

    db_session.expire_all()
    return (
        await db_session.execute(select(Post).where(Post.id == post_id))
    ).scalar_one()


async def test_all_targets_succeed(db_session, publishable, fake_provider):
    from app.models.post import PostStatus

    ctx = await publishable()
    provider = fake_provider({})

    await _publish(ctx["post"].id)
    post = await _reload(db_session, ctx["post"].id)

    assert post.status is PostStatus.PUBLISHED
    assert post.published_at is not None
    assert post.error_message is None
    assert len(provider.calls) == 2, "each target must be attempted"
    assert len(post.posting_results) == 2
    assert {r["status"] for r in post.posting_results} == {"published"}


async def test_partial_failure_across_targets(db_session, publishable, fake_provider):
    """The behaviour that matters most: one bad account must not lose the good
    one, and the post must not read as fully published."""
    from app.models.post import PostStatus

    ctx = await publishable()
    good_id, bad_id = (str(sa.id) for sa in ctx["accounts"])
    post_id = ctx["post"].id
    fake_provider({
        bad_id: PublishResult(
            status="failed", error="Token expired", retryable=False
        ),
    })

    await _publish(post_id)
    post = await _reload(db_session, post_id)

    assert post.status is PostStatus.PARTIALLY_PUBLISHED
    assert post.published_at is not None
    assert post.error_message == "Token expired"

    by_account = {r["social_account_id"]: r for r in post.posting_results}
    assert by_account[good_id]["status"] == "published"
    assert by_account[bad_id]["status"] == "failed"
    assert by_account[bad_id]["error"] == "Token expired"


async def test_all_targets_fail(db_session, publishable, fake_provider):
    from app.models.post import PostStatus

    ctx = await publishable()
    fake_provider({
        str(sa.id): PublishResult(status="failed", error=f"boom {i}")
        for i, sa in enumerate(ctx["accounts"])
    })

    await _publish(ctx["post"].id)
    post = await _reload(db_session, ctx["post"].id)

    assert post.status is PostStatus.FAILED
    assert post.error_message == "boom 0"
    assert {r["status"] for r in post.posting_results} == {"failed"}


async def test_manual_required_keeps_its_own_status(
    db_session, publishable, fake_provider
):
    """YouTube Community posts have no API. They count as a failure for the
    post's status but stay distinguishable, so the UI can offer a "publish by
    hand" helper instead of a red error."""
    from app.models.post import PostStatus

    ctx = await publishable()
    _, manual_id = (str(sa.id) for sa in ctx["accounts"])
    post_id = ctx["post"].id
    fake_provider({
        manual_id: PublishResult(
            status="manual_required", error="Post this one by hand"
        ),
    })

    await _publish(post_id)
    post = await _reload(db_session, post_id)

    assert post.status is PostStatus.PARTIALLY_PUBLISHED
    by_account = {r["social_account_id"]: r for r in post.posting_results}
    assert by_account[manual_id]["status"] == "manual_required"
    assert by_account[manual_id]["error"] == "Post this one by hand"


async def test_retryable_failures_are_marked(db_session, publishable, fake_provider):
    ctx = await publishable()
    limited_id, revoked_id = (str(sa.id) for sa in ctx["accounts"])
    post_id = ctx["post"].id
    fake_provider({
        limited_id: PublishResult(
            status="failed", error="429 Too Many Requests", retryable=True
        ),
        revoked_id: PublishResult(
            status="failed", error="401 token revoked", retryable=False
        ),
    })

    await _publish(post_id)
    post = await _reload(db_session, post_id)

    by_account = {r["social_account_id"]: r for r in post.posting_results}
    assert by_account[limited_id]["retryable"] is True
    # Absent rather than False, so consumers of posting_results see the shape
    # they always have.
    assert "retryable" not in by_account[revoked_id]


async def test_the_provider_receives_the_resolved_variant(
    db_session, publishable, fake_provider
):
    ctx = await publishable(target_count=1)
    expected_id = ctx["accounts"][0].id
    provider = fake_provider({})

    await _publish(ctx["post"].id)

    variant, media, social_account = provider.calls[0]
    assert variant.platform == "instagram"
    assert variant.content == "Hello from the connector tests"
    assert variant.post is not None
    assert social_account.id == expected_id
    assert media == []


async def test_performance_rows_are_seeded_for_successes_only(
    db_session, publishable, fake_provider
):
    from sqlalchemy import select

    from app.models.post_performance import PostPerformance

    ctx = await publishable()
    _, bad_id = (str(sa.id) for sa in ctx["accounts"])
    post_id = ctx["post"].id
    fake_provider({bad_id: PublishResult(status="failed", error="nope")})

    await _publish(post_id)

    rows = (
        await db_session.execute(
            select(PostPerformance).where(PostPerformance.post_id == post_id)
        )
    ).scalars().all()
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# Capabilities endpoint
# ---------------------------------------------------------------------------

def _caps_url(account_id, social_account_id):
    return (
        f"/api/v1/accounts/{account_id}/social-accounts/"
        f"{social_account_id}/capabilities"
    )


@pytest.mark.parametrize(
    "slug,max_chars,images",
    [
        ("twitter", 280, False),
        ("instagram", 2200, True),
        ("linkedin", 3000, True),
        ("youtube", 5000, False),
        ("facebook", 63206, True),
    ],
)
async def test_capabilities_endpoint_reports_the_platform(
    client, auth_header, user_factory, account_factory, social_account_factory,
    slug, max_chars, images,
):
    owner = await user_factory(password=PASSWORD)
    account = await account_factory(owner)
    social_account = await social_account_factory(owner, account, slug=slug)

    response = await client.get(
        _caps_url(account.id, social_account.id), headers=auth_header(owner)
    )
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["platform_slug"] == slug
    assert body["max_chars"] == max_chars
    assert body["supports_images"] is images
    assert body["social_account_id"] == str(social_account.id)


async def test_capabilities_denied_to_a_non_member(
    client, auth_header, user_factory, account_factory, social_account_factory
):
    owner = await user_factory(password=PASSWORD)
    account = await account_factory(owner)
    social_account = await social_account_factory(owner, account)
    stranger = await user_factory()

    response = await client.get(
        _caps_url(account.id, social_account.id), headers=auth_header(stranger)
    )
    assert response.status_code == 403


async def test_capabilities_of_another_workspaces_account_is_404(
    client, auth_header, user_factory, account_factory, social_account_factory
):
    """The tenancy boundary: the account exists, but not in this workspace."""
    owner = await user_factory(password=PASSWORD)
    mine = await account_factory(owner, name="Mine")
    theirs_owner = await user_factory()
    theirs = await account_factory(theirs_owner, name="Theirs")
    other_account = await social_account_factory(theirs_owner, theirs)

    response = await client.get(
        _caps_url(mine.id, other_account.id), headers=auth_header(owner)
    )
    assert response.status_code == 404


async def test_capabilities_requires_authentication(
    client, user_factory, account_factory, social_account_factory
):
    owner = await user_factory(password=PASSWORD)
    account = await account_factory(owner)
    social_account = await social_account_factory(owner, account)

    response = await client.get(_caps_url(account.id, social_account.id))
    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Refresh error mapping
# ---------------------------------------------------------------------------

async def test_missing_refresh_token_is_a_400_not_a_bad_gateway(
    client, auth_header, user_factory, account_factory, social_account_factory
):
    """An account with no stored refresh token is the caller's state, not the
    platform being unreachable.

    Live testing caught this returning 502 after the refactor: the endpoint
    mapped every ProviderAPIError without a status code to bad gateway, and a
    missing credential never has one. The code this replaced returned 400.
    """
    owner = await user_factory(password=PASSWORD)
    account = await account_factory(owner)
    social_account = await social_account_factory(
        owner, account, slug="twitter",
        # Not a mock token, so the request reaches the provider.
        access_token="AAAAreal-looking-token",
    )

    response = await client.post(
        f"/api/v1/accounts/{account.id}/social-accounts/"
        f"{social_account.id}/refresh-token",
        headers=auth_header(owner),
    )
    assert response.status_code == 400, response.text
    assert "refresh token" in response.json()["detail"].lower()


async def test_mock_tokens_never_reach_the_platform(
    client, auth_header, user_factory, account_factory, social_account_factory
):
    """Seeded and development accounts short-circuit, as before."""
    owner = await user_factory(password=PASSWORD)
    account = await account_factory(owner)
    social_account = await social_account_factory(
        owner, account, slug="linkedin", access_token="mock_token_123"
    )

    response = await client.post(
        f"/api/v1/accounts/{account.id}/social-accounts/"
        f"{social_account.id}/refresh-token",
        headers=auth_header(owner),
    )
    assert response.status_code == 200
    assert "mocked" in response.json()["message"]


# ---------------------------------------------------------------------------
# The point of native async: waiting must not occupy anything
# ---------------------------------------------------------------------------

async def test_instagram_poll_yields_to_the_event_loop(monkeypatch):
    """Instagram's container poll waits without holding a thread.

    It polls up to 24 times with a 5s gap while Instagram encodes the video.
    That wait used to be ``time.sleep`` inside ``asyncio.to_thread``, so a
    single Reel publish parked one of the 16 pool threads -- shared with bcrypt
    password hashing -- for up to two minutes. The wait is now awaited, so
    other work runs during it.

    Real sleeps would make this test take minutes, so asyncio.sleep is replaced
    with one that yields but returns immediately. What is under test is that
    control reaches the loop at all, which a blocking sleep would never do.
    """
    import asyncio

    import httpx

    from app.connectors import instagram

    slept: list[float] = []
    # instagram.asyncio is the global module, so hold the real sleep before
    # patching -- otherwise the replacement calls itself.
    real_sleep = asyncio.sleep

    async def _fast_sleep(delay, *args, **kwargs):
        slept.append(delay)
        await real_sleep(0)  # yield, but do not actually wait

    monkeypatch.setattr(instagram.asyncio, "sleep", _fast_sleep)

    # IN_PROGRESS twice, then FINISHED -- so the loop sleeps before succeeding.
    statuses = iter(["IN_PROGRESS", "IN_PROGRESS", "FINISHED"])

    async def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/media"):
            return httpx.Response(200, json={"id": "container_1"})
        if path.endswith("/media_publish"):
            return httpx.Response(200, json={"id": "published_1"})
        if "fields=status_code" in str(request.url):
            return httpx.Response(200, json={"status_code": next(statuses)})
        if "permalink" in str(request.url):
            return httpx.Response(200, json={"permalink": "https://instagram.com/p/x/"})
        return httpx.Response(200, json={"id": "17841400000000000"})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient",
        lambda *a, **k: real_client(*a, **{**k, "transport": httpx.MockTransport(handler)}),
    )

    post = MagicMock()
    post.content = "A reel"
    post.media_urls = ["https://cdn.example.com/photo.jpg"]
    post.hashtags = None
    post.instagram_post_type = "feed"
    post.instagram_video_url = None
    post.instagram_music_url = None

    account = MagicMock()
    account.access_token = "IGreal_token_value"
    account.config = {"instagram_business_account_id": "17841400000000000"}

    ticks = 0

    async def ticker():
        nonlocal ticks
        while True:
            ticks += 1
            await real_sleep(0)

    tick_task = asyncio.create_task(ticker())
    try:
        await instagram.publish_to_instagram(post, account)
    finally:
        tick_task.cancel()

    assert slept == [5, 5], f"expected two 5s waits between polls, got {slept}"
    assert ticks > 0, (
        "nothing else ran while the poll waited -- the wait is still blocking"
    )


# ---------------------------------------------------------------------------
# Structural: nothing in the package may block the loop
# ---------------------------------------------------------------------------

async def test_no_synchronous_httpx_client_remains():
    """A single `httpx.Client` here stalls the event loop for every request in
    the process, and nothing in a test would catch it."""
    from pathlib import Path

    package = Path(__file__).resolve().parent.parent / "app" / "connectors"
    offenders = [
        f"{path.name}:{n}"
        for path in sorted(package.glob("*.py"))
        for n, line in enumerate(path.read_text().splitlines(), 1)
        if "httpx.Client(" in line
    ]
    assert offenders == [], f"synchronous httpx client(s) at {offenders}"


async def test_only_disk_work_runs_in_a_thread():
    """asyncio.to_thread should survive only where the work is genuinely
    blocking -- file reads and writes, and the temp-directory handling around
    the ffmpeg render. HTTP must never be among them."""
    from pathlib import Path

    package = Path(__file__).resolve().parent.parent / "app" / "connectors"
    hops = {
        f"{path.name}"
        for path in sorted(package.glob("*.py"))
        for line in path.read_text().splitlines()
        if "asyncio.to_thread(" in line and not line.strip().startswith(("#", '"'))
    }
    assert hops <= {"media.py"}, (
        f"to_thread outside the disk helpers in media.py: {sorted(hops)}"
    )
