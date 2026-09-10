"""Slack as a notification channel.

Two inherited rules do most of the work here and both say the same thing from
different directions: **a notification must never break the thing it is
describing.**

* 0.7's email rule — a delivery failure is logged, never raised. A publish that
  reached the platform must not be reported as failed because a webhook 500'd.
* 1.9's de-dup rule — state-change events fire once per change, not once per
  poll. An account that has been broken for a week does not need a seventh
  identical message.

The third thing under test is consent: a workspace that pastes a webhook to try
the test button has not thereby agreed to a message for every publish. Both
halves — a valid webhook *and* the toggle for that specific event — are
required.
"""

import uuid

import pytest

from app.models.post import Post, PostStatus
from app.services import notifications, slack

PASSWORD = "TestPass123!"
HOOK = "https://hooks.slack.com/services/T000/B000/xxxxxxxxxxxxxxxxxxxxxxxx"


@pytest.fixture
async def workspace(db_session, user_factory, account_factory, organization_factory):
    async def _make(*, webhook=None, events=None, tz="UTC"):
        owner = await user_factory(password=PASSWORD)
        organization = await organization_factory(owner)
        account = await account_factory(owner, organization=organization)
        account.settings = {"timezone": tz}
        if events is not None:
            account.settings = {**account.settings, "slack_events": events}
        if webhook is not None:
            account.slack_webhook_url = webhook
        await db_session.flush()
        return {"owner": owner, "organization": organization, "account": account}

    return _make


@pytest.fixture
def captured_posts(monkeypatch):
    """Stand in for Slack, and record what it was sent."""
    sent = []

    def _install(*, ok=True, boom=False):
        async def _post(url, payload):
            if boom:
                raise RuntimeError("slack exploded")
            sent.append({"url": url, "payload": payload})
            return ok
        monkeypatch.setattr(slack, "post", _post)
        return sent

    return _install



@pytest.fixture
async def publishable(db_session, social_account_factory):
    """A post with one target, in a workspace we control the Slack settings of."""
    async def _make(ws):
        social = await social_account_factory(
            ws["owner"], ws["account"], slug="instagram"
        )
        post = Post(
            id=uuid.uuid4(),
            user_id=ws["owner"].id,
            account_id=ws["account"].id,
            content="Announcing something",
            status=PostStatus.DRAFT,
            target_accounts=[{
                "social_account_id": str(social.id),
                "platform_name": "Instagram",
                "account_name": social.account_name,
            }],
        )
        db_session.add(post)
        await db_session.flush()
        return post

    return _make


# ---------------------------------------------------------------------------
# The routing matrix: event x toggle
# ---------------------------------------------------------------------------

ALL_EVENTS = [event for event in notifications.Event]


@pytest.mark.parametrize("event", ALL_EVENTS)
async def test_an_event_reaches_slack_only_when_its_own_toggle_is_on(
    db_session, workspace, event
):
    """Per event, not per integration.

    A workspace that wants to hear about failures does not necessarily want a
    message for every successful publish.
    """
    ws = await workspace(webhook=HOOK, events={event.value: True})

    assert notifications.slack_enabled(ws["account"], event) is True
    for other in ALL_EVENTS:
        if other is event:
            continue
        assert notifications.slack_enabled(ws["account"], other) is False, (
            f"{other.value} fired while only {event.value} was switched on"
        )


async def test_a_webhook_alone_is_not_consent(db_session, workspace):
    """Pasting a URL to try the test button is not agreeing to everything."""
    ws = await workspace(webhook=HOOK)  # no toggles at all

    for event in ALL_EVENTS:
        assert notifications.slack_enabled(ws["account"], event) is False
    assert notifications.toggles_for(ws["account"]) == notifications.DEFAULTS


async def test_a_toggle_without_a_webhook_sends_nothing(db_session, workspace):
    ws = await workspace(events={e.value: True for e in ALL_EVENTS})

    for event in ALL_EVENTS:
        assert notifications.slack_enabled(ws["account"], event) is False


async def test_the_channel_matrix_names_every_channel_an_event_reaches(
    db_session, workspace
):
    """in_app and email are listed because they are true, not because this
    module sends them -- they are dispatched where the events are raised."""
    off = await workspace(webhook=HOOK)
    on = await workspace(
        webhook=HOOK, events={notifications.Event.POST_FAILED.value: True}
    )

    without = notifications.channels_for(off["account"], notifications.Event.POST_FAILED)
    with_slack = notifications.channels_for(on["account"], notifications.Event.POST_FAILED)

    assert notifications.Channel.SLACK not in without
    assert notifications.Channel.IN_APP in without
    assert notifications.Channel.SLACK in with_slack


async def test_a_stored_event_name_that_is_no_longer_known_is_ignored(
    db_session, workspace
):
    """A blob written before an event existed must not resurrect as a surprise."""
    ws = await workspace(webhook=HOOK, events={"some_removed_event": True})

    toggles = notifications.toggles_for(ws["account"])

    assert "some_removed_event" not in toggles
    assert all(value is False for value in toggles.values())


# ---------------------------------------------------------------------------
# Failure isolation -- 0.7's rule
# ---------------------------------------------------------------------------

async def test_a_slack_failure_is_swallowed_not_raised(
    db_session, workspace, captured_posts
):
    ws = await workspace(
        webhook=HOOK, events={notifications.Event.REPORT_READY.value: True}
    )
    captured_posts(boom=True)

    delivered = await notifications.to_slack(
        db_session, ws["account"], notifications.Event.REPORT_READY,
        title="Report ready", message="x",
    )

    assert delivered is False, "an exception must be reported, not propagated"


async def test_a_slack_500_does_not_fail_the_publish(
    db_session, workspace, publishable, captured_posts
):
    """The whole point of the rule.

    A post that reached the platform is published. If Slack rejects the
    announcement, the post is still published.
    """
    from app.services import publishing
    from app.services.publishing import JobStatus

    ws = await workspace(
        webhook=HOOK, events={notifications.Event.POST_PUBLISHED.value: True}
    )
    captured_posts(ok=False)  # Slack says no

    post = await publishable(ws)
    await publishing.create_jobs_for_post(db_session, post)
    for job in await _jobs_for(db_session, post.id):
        job.status = JobStatus.SUCCEEDED
    await db_session.flush()

    final = await publishing.derive_post_status(db_session, post.id)

    assert final.status is PostStatus.PUBLISHED
    assert final.error_message is None


async def _jobs_for(db_session, post_id):
    from sqlalchemy import select

    from app.models.publishing_job import PublishingJob

    return (
        await db_session.execute(
            select(PublishingJob).where(PublishingJob.post_id == post_id)
        )
    ).scalars().all()


# ---------------------------------------------------------------------------
# De-dup -- 1.9's rule
# ---------------------------------------------------------------------------

async def test_a_post_announces_once_per_transition_not_once_per_pass(
    db_session, workspace, publishable, captured_posts
):
    """Deriving the same finished post twice sends one message.

    The worker re-derives a post whenever any of its jobs moves. Announcing on
    every pass would mean a published post being re-announced each time another
    target finished.
    """
    from app.services import publishing
    from app.services.publishing import JobStatus

    ws = await workspace(
        webhook=HOOK, events={notifications.Event.POST_PUBLISHED.value: True}
    )
    sent = captured_posts()

    post = await publishable(ws)
    await publishing.create_jobs_for_post(db_session, post)
    for job in await _jobs_for(db_session, post.id):
        job.status = JobStatus.SUCCEEDED
    await db_session.flush()

    await publishing.derive_post_status(db_session, post.id)
    await publishing.derive_post_status(db_session, post.id)
    await publishing.derive_post_status(db_session, post.id)

    assert len(sent) == 1, f"announced {len(sent)} times for one transition"


# ---------------------------------------------------------------------------
# Payload shape
# ---------------------------------------------------------------------------

def test_the_payload_carries_text_as_well_as_blocks():
    """Slack shows `text` in notification previews and in clients that do not
    render blocks; without it they show "This content can't be displayed"."""
    payload = slack.build_blocks(title="Post published", message="Hello world")

    assert payload["text"], "a blocks-only payload previews as unreadable"
    assert "Post published" in payload["text"]
    assert payload["blocks"][0]["type"] == "header"
    assert payload["blocks"][1]["type"] == "section"


def test_fields_and_an_action_button_render_when_given():
    payload = slack.build_blocks(
        title="Report ready", message="Ready to download.",
        fields={"Period": "Sep", "Formats": "pdf, csv"},
        action_url="https://app.example.test/reports",
    )

    kinds = [block["type"] for block in payload["blocks"]]
    assert "actions" in kinds
    field_block = next(b for b in payload["blocks"] if b.get("fields"))
    assert len(field_block["fields"]) == 2
    button = next(b for b in payload["blocks"] if b["type"] == "actions")
    assert button["elements"][0]["url"] == "https://app.example.test/reports"


def test_a_long_message_is_trimmed_rather_than_sent_whole():
    payload = slack.build_blocks(title="t", message="x" * 9000)

    assert len(payload["text"]) <= slack.MAX_TEXT
    assert len(payload["blocks"][1]["text"]["text"]) <= slack.MAX_TEXT


# ---------------------------------------------------------------------------
# The webhook itself
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("url,valid", [
    (HOOK, True),
    ("http://hooks.slack.com/services/x", False),        # not https
    ("https://hooks.slack.example.com/services/x", False),  # lookalike host
    ("https://evil.test/collect", False),
    ("", False),
    (None, False),
])
def test_only_a_real_slack_webhook_is_accepted(url, valid):
    """The field is user-entered and gets POSTed to on every matching event.

    Without a host check, a typo -- or a paste of some other service's URL --
    turns the notification layer into a request-forwarder aimed wherever the
    text happened to point.
    """
    assert slack.is_valid_webhook(url) is valid


async def test_the_test_button_explains_a_bad_url_rather_than_just_failing():
    ok, detail = await slack.send_test("https://evil.test/collect")

    assert ok is False
    assert "hooks.slack.com" in detail


# ---------------------------------------------------------------------------
# The credential
# ---------------------------------------------------------------------------

async def test_the_webhook_round_trips_and_is_not_stored_in_the_clear(
    db_session, workspace
):
    """It is a credential -- anyone holding it can post as this app.

    Stored through EncryptedText like the social tokens, so the ORM sees
    plaintext and the row does not. Checked by reading the raw column, because
    "we set the type" is not evidence that the value was encrypted.
    """
    from sqlalchemy import text

    ws = await workspace(webhook=HOOK)
    await db_session.flush()

    account_id = ws["account"].id
    stored = (
        await db_session.execute(
            text("SELECT slack_webhook_url FROM accounts WHERE id = :id"),
            {"id": str(account_id)},
        )
    ).scalar()

    assert ws["account"].slack_webhook_url == HOOK, "the ORM must see plaintext"
    assert stored != HOOK, "the row holds the URL in the clear"
    assert "hooks.slack.com" not in (stored or ""), "the host leaked"


async def test_the_settings_response_says_whether_a_webhook_exists_not_what_it_is(
    client, auth_header, workspace
):
    """Returning the URL would put a credential in every settings response,
    and in whatever logs or error reports carry one."""
    ws = await workspace(webhook=HOOK)

    body = (await client.get(
        f"/api/v1/accounts/{ws['account'].id}/settings/",
        headers=auth_header(ws["owner"]),
    )).json()

    assert body["slack_webhook_configured"] is True
    assert HOOK not in str(body)


async def test_a_webhook_that_is_not_slacks_is_refused_on_write(
    client, auth_header, workspace
):
    ws = await workspace()

    response = await client.put(
        f"/api/v1/accounts/{ws['account'].id}/settings/",
        headers=auth_header(ws["owner"]),
        json={"slack_webhook_url": "https://evil.test/collect"},
    )

    assert response.status_code == 422
    assert "hooks.slack.com" in response.json()["detail"]


async def test_an_unknown_slack_event_is_refused_rather_than_stored(
    client, auth_header, workspace
):
    """A toggle for an event that does not exist switches nothing on.

    Accepting it silently is the accept-and-drop failure the settings writer
    already had once.
    """
    ws = await workspace()

    response = await client.put(
        f"/api/v1/accounts/{ws['account'].id}/settings/",
        headers=auth_header(ws["owner"]),
        json={"settings": {"slack_events": {"post_exploded": True}}},
    )

    assert response.status_code == 422
    assert "post_exploded" in response.text


async def test_a_string_toggle_is_refused(client, auth_header, workspace):
    """bool("false") is True, so a workspace sending the string would have
    switched an event on while believing it had switched it off."""
    ws = await workspace()

    response = await client.put(
        f"/api/v1/accounts/{ws['account'].id}/settings/",
        headers=auth_header(ws["owner"]),
        json={"settings": {"slack_events": {"post_failed": "false"}}},
    )

    assert response.status_code == 422
    assert "true or false" in response.text


async def test_an_empty_webhook_clears_it(client, auth_header, workspace):
    ws = await workspace(webhook=HOOK)
    url = f"/api/v1/accounts/{ws['account'].id}/settings/"

    await client.put(url, headers=auth_header(ws["owner"]),
                     json={"slack_webhook_url": ""})

    body = (await client.get(url, headers=auth_header(ws["owner"]))).json()
    assert body["slack_webhook_configured"] is False


async def test_the_test_button_endpoint_exists_where_the_ui_calls_it(
    client, auth_header, workspace, monkeypatch
):
    """A 404 here is a button that never worked.

    The route lives under the settings router, so its real path is
    /accounts/{id}/settings/slack/test. The page called
    /accounts/{id}/slack/test and got a 404 that looked, in the UI, like a
    Slack problem rather than a wiring one. Found by calling it against the
    running server.
    """
    ws = await workspace(webhook=HOOK)

    async def _send_test(url):
        return True, "Test message sent — check your Slack channel."

    monkeypatch.setattr(slack, "send_test", _send_test)

    response = await client.post(
        f"/api/v1/accounts/{ws['account'].id}/settings/slack/test",
        headers=auth_header(ws["owner"]),
    )

    assert response.status_code == 200, response.text
    assert response.json()["ok"] is True


def test_the_ui_calls_the_path_the_router_actually_serves():
    """The contract the 404 broke, pinned so it cannot drift again."""
    import pathlib

    page = (
        pathlib.Path(__file__).resolve().parents[2]
        / "frontend" / "src" / "pages" / "settings" / "SettingsPage.tsx"
    ).read_text()

    assert "/settings/slack/test" in page, (
        "the settings page calls a Slack test path the router does not serve"
    )
