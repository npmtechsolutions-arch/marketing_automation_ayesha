"""TikTok: the first network added through the connector pattern.

Three things here are TikTok-specific and none of them are cosmetic.

**SELF_ONLY is a success.** An app TikTok has not audited may only post
privately. That is the tier every new integration starts on, so a publish
under it must succeed and must *say* it was private -- reporting it as an
error would paint the one path to getting audited red, and saying nothing
would leave someone waiting for views that cannot arrive.

**Publishing is submit-then-poll**, so there are more outcomes than "worked" and
"didn't": still processing, rejected with a reason, rate limited, and still
processing when we ran out of patience. Each maps onto the job runner
differently, and each is pinned below.

**Metrics keep the null discipline.** TikTok's stats scope is separate from its
publishing scope, so a connection that can post may not be able to measure.
Absent stays absent.
"""

import uuid
from datetime import datetime, timezone

import httpx
import pytest

from app.connectors.base import (
    MediaRef,
    NotSupportedError,
    PlatformRateLimited,
    ResolvedContent,
)
from app.connectors import tiktok
from app.connectors.tiktok import AuditState, TikTokProvider

pytestmark = pytest.mark.asyncio

# Captured once, at import, before any test patches it. Reading
# ``httpx.AsyncClient`` inside install() would let a second install in the same
# test wrap the first one's factory -- which it did, and the requests then went
# to the previous fake's handler while the new one sat at zero.
_REAL_ASYNC_CLIENT = httpx.AsyncClient

VIDEO_URL = "https://cdn.test/clip.mp4"
VIDEO_BYTES = b"\x00\x00\x00\x18ftypmp42" + b"x" * 512


# ---------------------------------------------------------------------------
# Fixtures: a post, an account, and a scripted TikTok
# ---------------------------------------------------------------------------

class _Post:
    """The two attributes the caption builder reads."""

    def __init__(self, content: str, hashtags=None):
        self.content = content
        self.hashtags = hashtags or []


class _Account:
    def __init__(self, *, token="real-tiktok-user-token", audited=False):
        self.id = uuid.uuid4()
        self.access_token = token
        self.refresh_token = "refresh-abc"
        self.config = {
            AuditState.KEY: AuditState.AUDITED if audited else AuditState.UNAUDITED
        }


def _content(text="A clip", media_url=VIDEO_URL):
    post = _Post(text)
    return ResolvedContent(
        post=post,
        platform="tiktok",
        content=text,
        media_urls=[media_url] if media_url else [],
    )


def _media(url=VIDEO_URL):
    return [MediaRef(url=url, kind="video")] if url else []


class FakeTikTok:
    """A scripted Content Posting API.

    ``poll_states`` is the sequence ``status/fetch`` returns, one per call; the
    last is repeated if the caller polls past the end. Every request is
    recorded, which is how the privacy level actually sent gets asserted rather
    than assumed.
    """

    def __init__(
        self,
        poll_states=("PUBLISH_COMPLETE",),
        *,
        public_ids=("7311234567890123456",),
        fail_reason=None,
        init_status=200,
        upload_status=201,
        poll_status=200,
        poll_headers=None,
    ):
        self.poll_states = list(poll_states)
        self.public_ids = list(public_ids)
        self.fail_reason = fail_reason
        self.init_status = init_status
        self.upload_status = upload_status
        self.poll_status = poll_status
        self.poll_headers = poll_headers or {}
        self.requests: list[httpx.Request] = []
        self.polls = 0
        self.clients = 0

    def install(self, monkeypatch):
        def factory(*args, **kwargs):
            self.clients += 1
            return _REAL_ASYNC_CLIENT(
                *args,
                **{**kwargs, "transport": httpx.MockTransport(self.handle)},
            )

        monkeypatch.setattr(httpx, "AsyncClient", factory)
        # The real interval would make this suite take minutes.
        monkeypatch.setattr(tiktok, "POLL_INTERVAL_SECONDS", 0)
        return self

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = str(request.url)

        if url == VIDEO_URL:
            return httpx.Response(200, content=VIDEO_BYTES)

        if url.endswith("/post/publish/video/init/"):
            if self.init_status != 200:
                return httpx.Response(
                    self.init_status,
                    json={"error": {"message": "spam_risk_too_many_posts"}},
                )
            return httpx.Response(200, json={"data": {
                "publish_id": "v_pub_id_1234",
                "upload_url": "https://upload.test/tiktok/put",
            }})

        if url.startswith("https://upload.test/"):
            return httpx.Response(self.upload_status)

        if url.endswith("/post/publish/status/fetch/"):
            self.polls += 1
            if self.poll_status != 200:
                return httpx.Response(
                    self.poll_status,
                    json={"error": {"message": "rate limited"}},
                    headers=self.poll_headers,
                )
            index = min(self.polls - 1, len(self.poll_states) - 1)
            state = self.poll_states[index]
            data = {"status": state}
            if state == "PUBLISH_COMPLETE":
                data["publicaly_available_post_id"] = list(self.public_ids)
            if state == "FAILED":
                data["fail_reason"] = self.fail_reason or "picture_size_check_failed"
            return httpx.Response(200, json={"data": data})

        raise AssertionError(f"unexpected request to {url}")

    def body_of(self, suffix: str) -> dict:
        import json

        for request in self.requests:
            if str(request.url).endswith(suffix):
                return json.loads(request.content)
        raise AssertionError(f"no request to {suffix}")


@pytest.fixture
def api(monkeypatch):
    def _install(**kwargs):
        return FakeTikTok(**kwargs).install(monkeypatch)

    return _install


# ---------------------------------------------------------------------------
# SELF_ONLY is a state, not an error
# ---------------------------------------------------------------------------

async def test_an_unaudited_app_posts_privately_and_says_so(api):
    """The publish succeeds, and the privacy is reported as a notice.

    Both halves matter. If this came back failed, the only route to being
    audited -- posting a video and filming it -- would look broken. If it came
    back with nothing said, the author would wait for views that cannot arrive.
    """
    fake = api()
    result = await TikTokProvider().publish_post(
        _content(), _media(), _Account(audited=False)
    )

    assert result.succeeded
    assert result.error is None
    assert result.notice and "visible only to your own account" in result.notice
    assert fake.body_of("/video/init/")["post_info"]["privacy_level"] == "SELF_ONLY"


async def test_an_audited_connection_posts_publicly_with_no_notice(api):
    fake = api()
    result = await TikTokProvider().publish_post(
        _content(), _media(), _Account(audited=True)
    )

    assert result.succeeded
    assert result.notice is None
    assert result.post_url == "https://www.tiktok.com/video/7311234567890123456"
    assert (
        fake.body_of("/video/init/")["post_info"]["privacy_level"]
        == "PUBLIC_TO_EVERYONE"
    )


async def test_an_unknown_audit_state_is_treated_as_unaudited(api):
    """A config written by an older version, or by hand, must not go public.

    Guessing the generous case would mean sending PUBLIC_TO_EVERYONE from a
    client TikTok will reject -- and, if it ever were accepted, publishing
    someone's video more widely than they were told.
    """
    fake = api()
    account = _Account()
    account.config = {AuditState.KEY: "probably-fine"}

    result = await TikTokProvider().publish_post(_content(), _media(), account)

    assert result.succeeded
    assert fake.body_of("/video/init/")["post_info"]["privacy_level"] == "SELF_ONLY"


async def test_a_private_post_with_no_public_id_still_records_a_handle(api):
    """SELF_ONLY returns no public video id, which is correct, not missing.

    The publish id is still a real handle on the upload, so the job records
    that rather than a NULL and the post stops looking half-published.
    """
    api(public_ids=[])
    result = await TikTokProvider().publish_post(
        _content(), _media(), _Account(audited=False)
    )

    assert result.succeeded
    assert result.external_post_id == "v_pub_id_1234"
    assert result.post_url is None


# ---------------------------------------------------------------------------
# Every poll outcome
# ---------------------------------------------------------------------------

async def test_processing_states_are_waited_out(api):
    fake = api(poll_states=[
        "PROCESSING_UPLOAD", "PROCESSING_DOWNLOAD", "PUBLISH_COMPLETE",
    ])
    result = await TikTokProvider().publish_post(
        _content(), _media(), _Account(audited=True)
    )

    assert result.succeeded
    assert fake.polls == 3


async def test_an_unrecognised_state_waits_rather_than_guessing(api):
    """TikTok adding a state must not turn into a false success or failure."""
    fake = api(poll_states=["SOMETHING_NEW_IN_2027", "PUBLISH_COMPLETE"])
    result = await TikTokProvider().publish_post(
        _content(), _media(), _Account(audited=True)
    )

    assert result.succeeded
    assert fake.polls == 2


async def test_a_failed_state_keeps_the_platform_reason(api):
    """The platform's own words, not "publishing failed".

    ``PublishingLog`` stores this verbatim, and "picture_size_check_failed" is
    something an author can act on where a generic failure is not.
    """
    api(poll_states=["FAILED"], fail_reason="video_pull_failed: duration too long")
    result = await TikTokProvider().publish_post(
        _content(), _media(), _Account(audited=True)
    )

    assert result.status == "failed"
    assert "video_pull_failed: duration too long" in result.error
    # A rejected video is rejected. Re-uploading the same bytes would fail the
    # same way and spend another slot from the daily quota.
    assert result.retryable is False


async def test_still_processing_at_the_ceiling_is_retryable(api, monkeypatch):
    monkeypatch.setattr(tiktok, "POLL_ATTEMPTS", 3)
    fake = api(poll_states=["PROCESSING_UPLOAD"])
    result = await TikTokProvider().publish_post(
        _content(), _media(), _Account(audited=True)
    )

    assert result.status == "failed"
    assert result.retryable is True
    assert "still processing" in result.error.lower()
    assert fake.polls == 3


async def test_a_rate_limit_carries_the_platforms_own_retry_after(api):
    """Raised, not returned: the job runner honours Retry-After over backoff."""
    api(poll_status=429, poll_headers={"retry-after": "45"})

    with pytest.raises(PlatformRateLimited) as caught:
        await TikTokProvider().publish_post(
            _content(), _media(), _Account(audited=True)
        )

    assert caught.value.retry_after == 45


async def test_a_rejected_upload_init_fails_with_tiktoks_message(api):
    api(init_status=400)
    result = await TikTokProvider().publish_post(
        _content(), _media(), _Account(audited=True)
    )

    assert result.status == "failed"
    assert "spam_risk_too_many_posts" in result.error
    assert result.retryable is False


async def test_a_5xx_on_init_is_retryable(api):
    api(init_status=503)
    result = await TikTokProvider().publish_post(
        _content(), _media(), _Account(audited=True)
    )

    assert result.status == "failed"
    assert result.retryable is True


# ---------------------------------------------------------------------------
# The Instagram lesson: one client for the whole loop
# ---------------------------------------------------------------------------

async def test_one_client_serves_the_whole_poll_loop(api):
    """Client count must not grow with the number of poll attempts.

    Instagram's container poll opened a fresh AsyncClient per iteration, so
    twenty-four attempts meant twenty-four TCP+TLS handshakes, each then held
    idle across the sleep. Asserting the count is flat is the only way to
    catch that reappearing: a per-attempt client passes every other test here.
    """
    one = api(poll_states=["PUBLISH_COMPLETE"])
    await TikTokProvider().publish_post(
        _content(), _media(), _Account(audited=True)
    )

    many = api(poll_states=[
        "PROCESSING_UPLOAD", "PROCESSING_UPLOAD", "PROCESSING_DOWNLOAD",
        "PROCESSING_DOWNLOAD", "PUBLISH_COMPLETE",
    ])
    await TikTokProvider().publish_post(
        _content(), _media(), _Account(audited=True)
    )

    assert many.polls == 5
    assert many.clients == one.clients


# ---------------------------------------------------------------------------
# Video is required, and that is decided before any request
# ---------------------------------------------------------------------------

async def test_a_post_with_no_video_never_reaches_the_platform(api):
    fake = api()
    result = await TikTokProvider().publish_post(
        _content(media_url=None), [], _Account(audited=True)
    )

    assert result.status == "failed"
    assert result.retryable is False
    assert "video" in result.error.lower()
    assert fake.requests == []


async def test_an_image_is_not_quietly_turned_into_a_video(api):
    """YouTube's publisher renders an image into a clip. That must not spread.

    A video the author never made, published under their name, is a fabrication
    of a different kind from an invented metric but the same kind of dishonesty.
    """
    fake = api()
    result = await TikTokProvider().publish_post(
        _content(media_url="https://cdn.test/photo.jpg"),
        [MediaRef(url="https://cdn.test/photo.jpg", kind="image")],
        _Account(audited=True),
    )

    assert result.status == "failed"
    assert fake.requests == []


async def test_a_video_over_the_size_ceiling_is_refused(api, monkeypatch):
    monkeypatch.setattr(tiktok, "MAX_VIDEO_BYTES", 128)
    fake = api()
    result = await TikTokProvider().publish_post(
        _content(), _media(), _Account(audited=True)
    )

    assert result.status == "failed"
    assert result.retryable is False
    # The video was fetched, but nothing was sent to TikTok.
    assert not any("tiktokapis" in str(r.url) for r in fake.requests)


async def test_a_placeholder_token_never_touches_the_network(api):
    fake = api()
    result = await TikTokProvider().publish_post(
        _content(), _media(), _Account(token="mock_token_for_tests")
    )

    assert result.succeeded
    assert fake.requests == []
    # Still honest about privacy: a seeded account is unaudited too.
    assert result.notice


async def test_the_caption_carries_the_posts_hashtags(api):
    fake = api()
    content = _content("New drop")
    content.post.hashtags = ["launch", "#behindthescenes"]

    await TikTokProvider().publish_post(content, _media(), _Account(audited=True))

    title = fake.body_of("/video/init/")["post_info"]["title"]
    assert "New drop" in title
    assert "#launch" in title and "#behindthescenes" in title


# ---------------------------------------------------------------------------
# Analytics: absent is not zero
# ---------------------------------------------------------------------------

async def _analytics(monkeypatch, status, payload):
    def handler(request):
        return httpx.Response(status, json=payload)

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **k: _REAL_ASYNC_CLIENT(
            *a, **{**k, "transport": httpx.MockTransport(handler)}
        ),
    )
    since = datetime(2026, 9, 1, tzinfo=timezone.utc)
    until = datetime(2026, 9, 10, tzinfo=timezone.utc)
    return await TikTokProvider().get_analytics(_Account(), since, until)


async def test_metrics_the_scope_did_not_return_are_absent(monkeypatch):
    """Not zero. TikTok's stats scope is separate from its publishing scope, so
    a connection that can post may report no follower count at all -- and a
    stored 0 would draw a real, flat, wrong line."""
    metrics = await _analytics(
        monkeypatch, 200, {"data": {"user": {"follower_count": 4210}}}
    )

    assert metrics == {"followers": 4210}
    assert "likes" not in metrics
    assert "posts_count" not in metrics


async def test_a_failed_analytics_fetch_reports_nothing(monkeypatch):
    metrics = await _analytics(monkeypatch, 403, {"error": {"message": "scope_not_authorized"}})

    assert metrics == {}


async def test_a_zero_from_tiktok_is_kept_as_a_zero(monkeypatch):
    """The other half of the doctrine: a real measured zero is real.

    Dropping it would be the mirror-image error -- a brand new account with no
    likes has genuinely been measured at none.
    """
    metrics = await _analytics(
        monkeypatch, 200,
        {"data": {"user": {"follower_count": 0, "likes_count": 0, "video_count": 0}}},
    )

    assert metrics == {"followers": 0, "likes": 0, "posts_count": 0}


async def test_analytics_on_a_placeholder_token_is_empty(monkeypatch):
    account = _Account(token="mock_token_for_tests")
    metrics = await TikTokProvider().get_analytics(
        account,
        datetime(2026, 9, 1, tzinfo=timezone.utc),
        datetime(2026, 9, 10, tzinfo=timezone.utc),
    )

    assert metrics == {}


async def test_per_video_metrics_are_refused_not_estimated():
    """Handing back the account's lifetime totals as one video's numbers is
    exactly the fabrication removed from X and LinkedIn."""
    with pytest.raises(NotSupportedError):
        await TikTokProvider().get_post_metrics("v_123", _Account())


# ---------------------------------------------------------------------------
# Capabilities: what the flags claim is what the code does
# ---------------------------------------------------------------------------

async def test_capabilities_match_the_publish_path(api):
    """The flags are read by the composer, so a wrong one is a lie to an author.

    ``requires_video`` is the new one: TikTok does not merely accept video, it
    publishes nothing else, and the composer needs to say so while the post can
    still be fixed.
    """
    caps = TikTokProvider().capabilities

    assert caps.supports_video is True
    assert caps.requires_video is True
    assert caps.supports_images is False and caps.max_images == 0
    assert caps.supports_comments_api is False
    assert caps.max_chars == 2200

    # And the refusals behind the false flags are real refusals.
    for method, args in (
        ("get_comments", ()),
        ("get_messages", ()),
        ("get_mentions", ()),
    ):
        with pytest.raises(NotSupportedError):
            await getattr(TikTokProvider(), method)(_Account(), *args)


async def test_the_composer_refuses_a_tiktok_post_with_no_video():
    """Verified rather than reimplemented: validation reads Capabilities, so
    this rule arrived with the connector."""
    from app.services import post_validation

    result = post_validation._validate_one(
        "tiktok", TikTokProvider().capabilities, _content(media_url=None), {}
    )

    assert not result.ok
    messages = " ".join(e.message for e in result.errors)
    assert "video" in messages.lower()


async def test_the_registry_resolves_tiktok_rather_than_falling_back():
    """The fallback publishes to Instagram, silently. A workspace whose row is
    slugged "tiktok-business" must not have its videos land there."""
    from app.connectors.registry import get_provider, resolve_slug

    assert resolve_slug("tiktok") == "tiktok"
    assert resolve_slug("tiktok-business") == "tiktok"
    assert isinstance(get_provider("TikTok"), TikTokProvider)


# ---------------------------------------------------------------------------
# Through the 1.5 job runner
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def publish_uses_the_test_session(monkeypatch, db_session):
    """Point the publish worker at the test database.

    ``execute_job`` takes only a job id and opens its own ``AsyncSessionLocal``,
    so without this it would talk to the developer's real Postgres while the
    test wrote to in-memory SQLite. Same fixture as test_connectors.py.
    """
    from contextlib import asynccontextmanager

    from app.services import publishing as publishing_module

    @asynccontextmanager
    async def _session():
        yield db_session

    monkeypatch.setattr(publishing_module, "AsyncSessionLocal", lambda: _session())
    monkeypatch.setattr(db_session, "commit", db_session.flush)


async def test_a_private_publish_reaches_the_job_log_as_a_note_not_an_error(
    db_session, user_factory, account_factory, social_account_factory
):
    """The whole point of ``notice``, end to end.

    The job must succeed -- a SELF_ONLY post is published -- and the reason
    nobody can see it must be in the log the user reads. Recording it as an
    error would fail a post that worked; dropping it would leave the log
    saying the video went out with no hint that it went out privately.
    """
    from sqlalchemy import select

    from app.models.post import Post, PostStatus
    from app.models.publishing_job import JobStatus, PublishingJob, PublishingLog
    from app.services import publishing

    owner = await user_factory(password="hunter2-correct-horse")
    account = await account_factory(owner)
    social = await social_account_factory(
        owner, account, slug="tiktok",
        config={AuditState.KEY: AuditState.UNAUDITED},
    )
    post = Post(
        id=uuid.uuid4(),
        user_id=owner.id,
        account_id=account.id,
        content="A clip for TikTok",
        status=PostStatus.PUBLISHING,
        target_accounts=[{
            "social_account_id": str(social.id),
            "platform_name": "TikTok",
            "account_name": social.account_name,
        }],
    )
    db_session.add(post)
    await db_session.flush()

    jobs = await publishing.create_jobs_for_post(db_session, post)
    await db_session.flush()
    # Ids captured before anything expires: reading post.id back after
    # expire_all() is a lazy load, and a lazy load inside an async call's
    # arguments is the MissingGreenlet this suite keeps meeting.
    post_id = post.id
    job_ids = [job.id for job in jobs]
    for job_id in job_ids:
        await publishing.execute_job(job_id)

    db_session.expire_all()
    job = (
        await db_session.execute(
            select(PublishingJob).where(PublishingJob.post_id == post_id)
        )
    ).scalar_one()
    assert job.status is JobStatus.SUCCEEDED
    assert job.last_error is None

    logs = (
        await db_session.execute(
            select(PublishingLog).where(PublishingLog.job_id == job.id)
        )
    ).scalars().all()
    notices = [log for log in logs if "visible only to your own account" in log.message]
    assert notices, [log.message for log in logs]
    # Recorded as information, beside the success -- not as an error.
    assert notices[0].level.value.lower() == "info"
    assert any(
        (log.platform_response or {}).get("notice") for log in logs
    )
