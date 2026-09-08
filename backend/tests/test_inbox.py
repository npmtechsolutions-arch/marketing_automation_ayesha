"""The unified inbox: sync, actions, and what each platform can actually do.

Three things carry the risk.

**Idempotency.** Polling re-fetches the same items every pass by design, so a
sync that is not idempotent on ``external_id`` duplicates the entire inbox
every five minutes — and the duplicates look like new mail.

**Capability honesty.** A platform that cannot do something must say so, not
return an empty list. "No messages" and "this platform has no message API" look
identical to a reader and mean opposite things.

**Permissions.** Replying speaks to the workspace's customers in its name. A
viewer who can read the inbox must not be able to do that.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.connectors.base import NotSupportedError
from app.connectors.registry import get_provider, known_slugs
from app.models.inbox import (
    InboxMessage,
    InboxThread,
    MessageDirection,
    ThreadStatus,
    ThreadType,
)
from app.models.team_member import InvitationStatus, TeamRole
from app.services import inbox_actions, inbox_sync

pytestmark = pytest.mark.asyncio

PASSWORD = "hunter2-correct-horse"


@pytest.fixture
async def workspace(
    db_session, user_factory, account_factory, organization_factory,
    social_account_factory, member_factory,
):
    async def _make(slug="facebook"):
        owner = await user_factory(password=PASSWORD)
        organization = await organization_factory(owner)
        account = await account_factory(owner, organization=organization)
        await db_session.flush()
        connection = await social_account_factory(owner, account, slug=slug)

        editor = await user_factory(password=PASSWORD)
        await member_factory(editor, account, role=TeamRole.EDITOR,
                             invitation_status=InvitationStatus.ACCEPTED)
        viewer = await user_factory(password=PASSWORD)
        await member_factory(viewer, account, role=TeamRole.VIEWER,
                             invitation_status=InvitationStatus.ACCEPTED)
        await db_session.flush()
        return {
            "owner": owner, "editor": editor, "viewer": viewer,
            "account": account, "account_id": account.id,
            "connection": connection, "connection_id": connection.id,
        }

    return _make



@pytest.fixture
def stub_provider(monkeypatch):
    """Silence every inbox source on a provider, then let a test speak.

    Necessary because the fixtures connect with a mock token, and the real
    provider methods answer a mock token with sample data. A test that patches
    only ``get_comments`` would still receive a sample DM from Facebook, and
    its counts would be off by exactly one for a reason nothing on screen
    explains.
    """

    def _install(slug: str, **sources):
        provider = get_provider(slug)

        async def _empty_comments(connection, external_post_id=None):
            return []

        async def _empty(connection):
            return []

        defaults = {
            "get_comments": _empty_comments,
            "get_messages": _empty,
            "get_mentions": _empty,
        }
        for name, default in defaults.items():
            monkeypatch.setattr(
                provider, name, sources.get(name, default), raising=False
            )
        return provider

    return _install


def _item(external_id: str, *, thread="t1", body="Hello", author="Priya",
          minutes_ago=1, outbound=False):
    return {
        "external_id": external_id,
        "thread_external_id": thread,
        "author": author,
        "author_handle": author.lower(),
        "participant": author,
        "participant_handle": author.lower(),
        "body": body,
        "created_at": datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
        "outbound": outbound,
    }


# ---------------------------------------------------------------------------
# Sync idempotency
# ---------------------------------------------------------------------------

async def test_syncing_twice_does_not_duplicate(db_session, workspace, stub_provider):
    """The single most important property. Polling re-fetches the same items
    every pass; without idempotency the inbox doubles every five minutes."""
    ws = await workspace()
    items = [_item("c1"), _item("c2", body="Second")]

    async def comments(connection, external_post_id=None):
        return items

    stub_provider("facebook", get_comments=comments)

    first = await inbox_sync.sync_connection(db_session, ws["connection"])
    second = await inbox_sync.sync_connection(db_session, ws["connection"])

    assert first["new_messages"] == 2
    assert second["new_messages"] == 0, "the second poll re-imported everything"

    total = (await db_session.execute(select(func.count()).select_from(InboxMessage))).scalar_one()
    threads = (await db_session.execute(select(func.count()).select_from(InboxThread))).scalar_one()
    assert (total, threads) == (2, 1)


async def test_a_new_message_in_a_known_thread_is_added(
    db_session, workspace, stub_provider
):
    ws = await workspace()
    items = [_item("c1")]

    async def comments(connection, external_post_id=None):
        return items

    stub_provider("facebook", get_comments=comments)
    await inbox_sync.sync_connection(db_session, ws["connection"])

    items.append(_item("c2", body="A follow-up", minutes_ago=0))
    report = await inbox_sync.sync_connection(db_session, ws["connection"])

    assert report["new_messages"] == 1
    thread = (await db_session.execute(select(InboxThread))).scalars().one()
    assert thread.last_message_preview == "A follow-up"


async def test_an_existing_message_is_not_rewritten(
    db_session, workspace, stub_provider
):
    """A platform can re-serve the same comment with the author's name rendered
    differently. Rewriting it every poll churns the row and makes "has anything
    happened here" unanswerable."""
    ws = await workspace()
    state = {"items": [_item("c1", author="Priya")]}

    async def comments(connection, external_post_id=None):
        return state["items"]

    stub_provider("facebook", get_comments=comments)
    await inbox_sync.sync_connection(db_session, ws["connection"])

    state["items"] = [_item("c1", author="Priya Ramesh")]
    await inbox_sync.sync_connection(db_session, ws["connection"])

    message = (await db_session.execute(select(InboxMessage))).scalars().one()
    assert message.author == "Priya"


async def test_an_older_item_does_not_move_the_thread_up(
    db_session, workspace, stub_provider
):
    """Letting a late-arriving old comment rewrite last_message_at would
    shuffle the inbox under whoever is reading it."""
    ws = await workspace()
    state = {"items": [_item("c1", minutes_ago=1, body="Recent")]}

    async def comments(connection, external_post_id=None):
        return state["items"]

    stub_provider("facebook", get_comments=comments)
    await inbox_sync.sync_connection(db_session, ws["connection"])
    thread = (await db_session.execute(select(InboxThread))).scalars().one()
    newest = thread.last_message_at

    state["items"] = [_item("c0", minutes_ago=600, body="Ancient")]
    await inbox_sync.sync_connection(db_session, ws["connection"])
    await db_session.refresh(thread)

    assert thread.last_message_at == newest
    assert thread.last_message_preview == "Recent"


async def test_an_item_without_an_external_id_is_skipped(
    db_session, workspace, stub_provider
):
    """Nothing to be idempotent on, so storing it would duplicate forever."""
    ws = await workspace()

    async def comments(connection, external_post_id=None):
        return [{"body": "no id", "author": "X"}]

    stub_provider("facebook", get_comments=comments)
    report = await inbox_sync.sync_connection(db_session, ws["connection"])

    assert report["new_messages"] == 0


async def test_inbound_mail_reopens_a_resolved_thread(
    db_session, workspace, stub_provider
):
    """A customer replying to a closed conversation has not been dealt with."""
    ws = await workspace()
    state = {"items": [_item("c1")]}

    async def comments(connection, external_post_id=None):
        return state["items"]

    stub_provider("facebook", get_comments=comments)
    await inbox_sync.sync_connection(db_session, ws["connection"])
    thread = (await db_session.execute(select(InboxThread))).scalars().one()
    await inbox_actions.set_status(db_session, thread, ThreadStatus.RESOLVED)

    state["items"].append(_item("c2", body="Actually one more thing", minutes_ago=0))
    await inbox_sync.sync_connection(db_session, ws["connection"])
    await db_session.refresh(thread)

    assert thread.status is ThreadStatus.OPEN


# ---------------------------------------------------------------------------
# Capability fallbacks
# ---------------------------------------------------------------------------

async def test_an_unsupported_source_is_reported_not_called(
    db_session, workspace, stub_provider
):
    """LinkedIn has no generally available messaging API. The sync must not
    call it, and must say so rather than returning an empty inbox."""
    ws = await workspace(slug="linkedin")
    called = {"messages": False}

    async def messages(connection):
        called["messages"] = True
        return []

    async def comments(connection, external_post_id=None):
        return []

    stub_provider("linkedin", get_messages=messages, get_comments=comments)

    report = await inbox_sync.sync_connection(db_session, ws["connection"])

    assert "dm" in report["unsupported"]
    assert called["messages"] is False, "an unsupported source was called anyway"


async def test_a_provider_raising_not_supported_is_a_fact_not_an_error(
    db_session, workspace, stub_provider
):
    """LinkedIn comments work on organization pages and not personal ones.
    That is a fact about the connection, not a fault to investigate."""
    ws = await workspace(slug="linkedin")

    async def comments(connection, external_post_id=None):
        raise NotSupportedError("linkedin", "get_comments on a personal profile")

    stub_provider("linkedin", get_comments=comments)

    report = await inbox_sync.sync_connection(db_session, ws["connection"])

    assert "comment" in report["unsupported"]
    assert report["errors"] == []


async def test_a_provider_error_is_recorded_as_an_error(
    db_session, workspace, stub_provider
):
    """Distinct from unsupported: this one someone should look at."""
    ws = await workspace()

    async def comments(connection, external_post_id=None):
        raise RuntimeError("graph exploded")

    stub_provider("facebook", get_comments=comments)

    report = await inbox_sync.sync_connection(db_session, ws["connection"])

    assert report["errors"]
    assert "comment" not in report["unsupported"]


async def test_one_failing_source_does_not_stop_the_others(
    db_session, workspace, stub_provider
):
    ws = await workspace()

    async def comments(connection, external_post_id=None):
        raise RuntimeError("nope")

    async def messages(connection):
        return [_item("m1", thread="conv1", body="A DM")]

    stub_provider("facebook", get_comments=comments, get_messages=messages)

    report = await inbox_sync.sync_connection(db_session, ws["connection"])

    assert report["new_messages"] == 1
    assert report["errors"]


@pytest.mark.parametrize("slug", sorted(known_slugs()))
async def test_a_claimed_capability_is_actually_implemented(slug):
    """A capability flag that says True with a NotSupportedError behind it is
    the lying-matrix pattern: the UI offers a feature the server refuses."""
    provider = get_provider(slug)
    capabilities = provider.capabilities
    checks = [
        (capabilities.supports_comments_api, "get_comments"),
        (capabilities.supports_dm_api, "get_messages"),
        (capabilities.supports_mentions_api, "get_mentions"),
    ]
    base = type(provider).__mro__[-2]  # SocialProvider
    for claimed, method in checks:
        if not claimed:
            continue
        assert getattr(type(provider), method, None) is not getattr(base, method), (
            f"{slug} claims {method} but inherits the unsupported stub"
        )


async def test_supported_sources_describes_each_platform():
    assert inbox_sync.supported_sources("twitter") == {
        "comment": False, "dm": False, "mention": True
    }
    assert inbox_sync.supported_sources("linkedin")["dm"] is False
    assert inbox_sync.supported_sources("facebook")["comment"] is True


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

@pytest.fixture
async def thread(db_session, workspace, stub_provider):
    async def _make(slug="facebook", kind=ThreadType.COMMENT):
        ws = await workspace(slug=slug)
        row = InboxThread(
            id=uuid.uuid4(), account_id=ws["account_id"],
            social_account_id=ws["connection_id"], type=kind,
            external_id="t1", participant="Priya", participant_handle="priya",
            status=ThreadStatus.OPEN, unread_count=1,
        )
        db_session.add(row)
        db_session.add(InboxMessage(
            id=uuid.uuid4(), thread_id=row.id, direction=MessageDirection.INBOUND,
            external_id="c1", author="Priya", body="Does this ship to the EU?",
            created_at=datetime.now(timezone.utc),
        ))
        await db_session.flush()
        return ws, row

    return _make


async def test_a_reply_is_sent_before_it_is_recorded(
    db_session, thread, monkeypatch
):
    """The other order leaves a reply in our inbox that the customer never
    received, which is worse than an error the sender can see."""
    ws, row = await thread()
    sent = {}

    async def reply_to_comment(connection, comment_id, body):
        sent["comment_id"] = comment_id
        sent["body"] = body
        return {"external_id": "reply_1"}

    monkeypatch.setattr(
        get_provider("facebook"), "reply_to_comment", reply_to_comment, raising=False
    )

    message = await inbox_actions.reply(
        db_session, row, ws["connection"], body="Yes, we do.", user_id=ws["owner"].id
    )

    assert sent["body"] == "Yes, we do."
    # Replied to the latest inbound comment, keeping the platform's threading.
    assert sent["comment_id"] == "c1"
    assert message.direction is MessageDirection.OUTBOUND
    assert message.external_id == "reply_1"


async def test_a_failed_reply_records_nothing(db_session, thread, monkeypatch):
    ws, row = await thread()

    async def reply_to_comment(connection, comment_id, body):
        raise RuntimeError("graph refused")

    monkeypatch.setattr(
        get_provider("facebook"), "reply_to_comment", reply_to_comment, raising=False
    )

    with pytest.raises(inbox_actions.ReplyFailed):
        await inbox_actions.reply(
            db_session, row, ws["connection"], body="Hi", user_id=ws["owner"].id
        )

    outbound = (
        await db_session.execute(
            select(func.count()).select_from(InboxMessage).where(
                InboxMessage.direction == MessageDirection.OUTBOUND
            )
        )
    ).scalar_one()
    assert outbound == 0


async def test_a_mention_cannot_be_replied_to_from_the_inbox(db_session, thread):
    """A mention lives on someone else's post; replying means posting
    publicly, which is the composer's job."""
    ws, row = await thread(slug="twitter", kind=ThreadType.MENTION)

    with pytest.raises(inbox_actions.ReplyNotSupported):
        await inbox_actions.reply(
            db_session, row, ws["connection"], body="Thanks!", user_id=ws["owner"].id
        )


async def test_an_internal_note_is_never_outbound(db_session, thread):
    ws, row = await thread()

    note = await inbox_actions.add_note(
        db_session, row, body="Refund already issued", user_id=ws["owner"].id
    )

    assert note.direction is MessageDirection.INTERNAL
    assert note.author_user_id == ws["owner"].id


async def test_a_note_does_not_move_the_thread_up_the_inbox(db_session, thread):
    """The inbox sorts by customer activity. A team member writing to
    themselves is not that."""
    ws, row = await thread()
    row.last_message_at = datetime.now(timezone.utc) - timedelta(hours=3)
    await db_session.flush()
    before = row.last_message_at

    await inbox_actions.add_note(db_session, row, body="Note", user_id=ws["owner"].id)

    assert row.last_message_at == before


@pytest.mark.parametrize(
    "raw, expected",
    [
        (["Refund", "refund", " REFUND "], ["refund"]),
        (["  ", "billing"], ["billing"]),
        ([f"tag{n}" for n in range(30)], [f"tag{n}" for n in range(20)]),
    ],
)
async def test_tags_are_normalised(raw, expected):
    """"Refund" and "refund" filtering as two tags is how a tag list becomes
    useless within a week."""
    assert inbox_actions.normalise_tags(raw) == expected


# ---------------------------------------------------------------------------
# Endpoints and permissions
# ---------------------------------------------------------------------------

async def test_a_viewer_can_read_but_not_reply(
    client, auth_header, thread, monkeypatch
):
    """Replying speaks to the workspace's customers in its name."""
    ws, row = await thread()

    async def reply_to_comment(connection, comment_id, body):
        return {"external_id": "r1"}

    monkeypatch.setattr(
        get_provider("facebook"), "reply_to_comment", reply_to_comment, raising=False
    )
    base = f"/api/v1/accounts/{ws['account_id']}/inbox"

    listed = await client.get(f"{base}/", headers=auth_header(ws["viewer"]))
    assert listed.status_code == 200

    blocked = await client.post(
        f"{base}/{row.id}/reply", headers=auth_header(ws["viewer"]),
        json={"body": "Hi"},
    )
    assert blocked.status_code == 403

    allowed = await client.post(
        f"{base}/{row.id}/reply", headers=auth_header(ws["editor"]),
        json={"body": "Hi"},
    )
    assert allowed.status_code == 200, allowed.text


async def test_another_workspace_cannot_see_a_thread(client, auth_header, thread, workspace):
    ws, row = await thread()
    other = await workspace()

    response = await client.get(
        f"/api/v1/accounts/{ws['account_id']}/inbox/{row.id}",
        headers=auth_header(other["owner"]),
    )
    assert response.status_code in (403, 404)


async def test_a_thread_id_from_another_workspace_is_404(
    client, auth_header, thread, workspace
):
    """Scoped by account, so a valid id from elsewhere must not resolve."""
    ws, row = await thread()
    other = await workspace()

    response = await client.get(
        f"/api/v1/accounts/{other['account_id']}/inbox/{row.id}",
        headers=auth_header(other["owner"]),
    )
    assert response.status_code == 404


async def test_assigning_to_a_non_member_is_refused(
    client, auth_header, thread, user_factory
):
    """Otherwise the thread lands in a queue nobody can see."""
    ws, row = await thread()
    outsider = await user_factory()

    response = await client.put(
        f"/api/v1/accounts/{ws['account_id']}/inbox/{row.id}/assign",
        headers=auth_header(ws["owner"]),
        json={"assigned_to": str(outsider.id)},
    )
    assert response.status_code == 400


async def test_assign_and_unassign(client, auth_header, thread):
    ws, row = await thread()
    url = f"/api/v1/accounts/{ws['account_id']}/inbox/{row.id}/assign"

    assigned = await client.put(url, headers=auth_header(ws["owner"]),
                                json={"assigned_to": str(ws["editor"].id)})
    assert assigned.json()["assigned_to"] == str(ws["editor"].id)

    cleared = await client.put(url, headers=auth_header(ws["owner"]),
                               json={"assigned_to": None})
    assert cleared.json()["assigned_to"] is None


async def test_opening_a_thread_marks_it_read(client, auth_header, thread):
    ws, row = await thread()

    body = (
        await client.get(
            f"/api/v1/accounts/{ws['account_id']}/inbox/{row.id}",
            headers=auth_header(ws["owner"]),
        )
    ).json()

    assert body["unread_count"] == 0
    assert len(body["messages"]) == 1


async def test_filters_narrow_the_list(client, auth_header, thread, db_session):
    ws, row = await thread()
    row.tags = ["refund"]
    row.status = ThreadStatus.RESOLVED
    await db_session.flush()
    base = f"/api/v1/accounts/{ws['account_id']}/inbox/"
    headers = auth_header(ws["owner"])

    assert len((await client.get(f"{base}?status=open", headers=headers)).json()["threads"]) == 0
    assert len((await client.get(f"{base}?status=resolved", headers=headers)).json()["threads"]) == 1
    assert len((await client.get(f"{base}?tag=refund", headers=headers)).json()["threads"]) == 1
    assert len((await client.get(f"{base}?tag=billing", headers=headers)).json()["threads"]) == 0
    assert len((await client.get(f"{base}?platform=twitter", headers=headers)).json()["threads"]) == 0
    assert len((await client.get(f"{base}?unassigned=true", headers=headers)).json()["threads"]) == 1


async def test_the_capabilities_endpoint_says_what_each_connection_supports(
    client, auth_header, thread
):
    """So the UI can say "X has no direct messages" instead of showing an
    empty list that looks like a quiet inbox."""
    ws, _ = await thread(slug="twitter")

    body = (
        await client.get(
            f"/api/v1/accounts/{ws['account_id']}/inbox/capabilities",
            headers=auth_header(ws["owner"]),
        )
    ).json()

    twitter = next(c for c in body["connections"] if c["platform"] == "twitter")
    assert twitter["supports"] == {"comment": False, "dm": False, "mention": True}


async def test_replying_to_a_mention_is_422_not_500(
    client, auth_header, thread
):
    ws, row = await thread(slug="twitter", kind=ThreadType.MENTION)

    response = await client.post(
        f"/api/v1/accounts/{ws['account_id']}/inbox/{row.id}/reply",
        headers=auth_header(ws["owner"]), json={"body": "Thanks!"},
    )

    assert response.status_code == 422
    assert "publicly" in response.json()["detail"]
