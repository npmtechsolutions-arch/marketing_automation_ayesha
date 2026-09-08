"""PUT /accounts/{id}/settings/ actually writes what it is given.

Every test here is a round trip: write, then re-read through a *separate* GET.
Checking the PUT's own response is not enough -- it renders from the in-memory
object, so a write that never reached the database can still look right in the
reply that reports it.

Every workspace here also starts with a **non-empty** settings blob, and that
is not decoration. On a fresh account ``settings`` is NULL, so the old
``account.settings or {}`` produced a brand new dict and the write landed
correctly; the bug only appeared on the second write, once there was a loaded
dict to mutate in place. A per-field round trip against an empty blob passes
against the broken code.

The bug this file exists for: the writer merged settings by mutating the loaded
dict in place and assigning it back to itself. SQLAlchemy decides whether to
emit an UPDATE by comparing an attribute's before and after values, and here
they were the same object, so ``history.has_changes()`` was False and the flush
wrote nothing. The endpoint returned 200 with the old values.

Nothing caught it because no test had ever called this endpoint, and the
frontend does not use it either. The cost was not hypothetical: the settings
blob is the *only* home of ``approvals_required``, so the entire review and
approval workflow could not be switched on through the API.
"""

import uuid

import pytest

from app.models.team_member import InvitationStatus, TeamRole

pytestmark = pytest.mark.asyncio

PASSWORD = "hunter2-correct-horse"


@pytest.fixture
async def workspace(
    db_session, user_factory, account_factory, organization_factory, member_factory
):
    """An owner and their workspace, with one non-admin for the authz check."""

    async def _make():
        owner = await user_factory(password=PASSWORD, full_name="Olive Owner")
        organization = await organization_factory(owner)
        account = await account_factory(owner, organization=organization)
        # A pre-existing blob, so every write below is a merge into a dict the
        # session has already loaded -- the path that was broken. See the
        # module docstring for why an empty blob would hide it.
        account.settings = {"locale": "en-GB"}
        await db_session.flush()
        viewer = await user_factory(password=PASSWORD, full_name="Vic Viewer")
        await member_factory(
            viewer, account, role=TeamRole.VIEWER,
            invitation_status=InvitationStatus.ACCEPTED,
        )
        return {
            "account": account,
            "account_id": account.id,
            "owner": owner,
            "viewer": viewer,
        }

    return _make


async def _put(client, auth_header, ws, body):
    return await client.put(
        f"/api/v1/accounts/{ws['account_id']}/settings/",
        headers=auth_header(ws["owner"]),
        json=body,
    )


async def _get(client, auth_header, ws):
    return await client.get(
        f"/api/v1/accounts/{ws['account_id']}/settings/",
        headers=auth_header(ws["owner"]),
    )


# ---------------------------------------------------------------------------
# One round trip per persisted field
# ---------------------------------------------------------------------------

async def test_name_round_trips(client, auth_header, workspace):
    ws = await workspace()

    response = await _put(client, auth_header, ws, {"name": "Renamed Workspace"})
    assert response.status_code == 200

    assert (await _get(client, auth_header, ws)).json()["name"] == "Renamed Workspace"


@pytest.mark.parametrize(
    "key, value",
    [
        ("timezone", "Australia/Sydney"),
        ("approvals_required", True),
        ("client_approval_required", True),
        ("approvals_required", False),
        # Not a key the backend reads. The blob is a deliberate extension point
        # for client-side preferences, so an unknown key is stored as given
        # rather than rejected -- but it still has to actually persist.
        ("sidebar_collapsed", True),
    ],
)
async def test_each_settings_key_round_trips(client, auth_header, workspace, key, value):
    """Write one key, read it back from a fresh request."""
    ws = await workspace()

    response = await _put(client, auth_header, ws, {"settings": {key: value}})
    assert response.status_code == 200, response.text
    assert response.json()["settings"][key] == value, "the PUT's own reply is already wrong"

    stored = (await _get(client, auth_header, ws)).json()["settings"]
    assert stored[key] == value, f"{key} did not survive the write"
    assert stored["locale"] == "en-GB", "the merge dropped a pre-existing key"


async def test_approval_workflow_can_be_enabled_through_the_api(
    client, auth_header, workspace, db_session
):
    """The concrete cost of the bug.

    ``approvals_required`` lives only on this blob and is written only by this
    endpoint, so while the writer dropped its input there was no way at all to
    turn the review workflow on through the API. It read as False forever, and
    the approvals tests passed because their fixture writes the blob directly.
    """
    from app.models.account import Account
    from app.services import approvals

    ws = await workspace()

    response = await _put(
        client, auth_header, ws,
        {"settings": {"approvals_required": True, "client_approval_required": True}},
    )
    assert response.status_code == 200

    # Straight from the database, not from the session that did the write.
    db_session.expire_all()
    account = await db_session.get(Account, ws["account_id"])
    config = approvals.settings_for(account)
    assert config.approvals_required is True
    assert config.client_approval_required is True


# ---------------------------------------------------------------------------
# Merge semantics
# ---------------------------------------------------------------------------

async def test_a_second_write_keeps_the_first_key(client, auth_header, workspace):
    """The endpoint merges rather than replaces, so setting a timezone must not
    silently switch the approval workflow back off."""
    ws = await workspace()

    await _put(client, auth_header, ws, {"settings": {"approvals_required": True}})
    await _put(client, auth_header, ws, {"settings": {"timezone": "Europe/Berlin"}})

    stored = (await _get(client, auth_header, ws)).json()["settings"]
    assert stored == {
        "locale": "en-GB",
        "approvals_required": True,
        "timezone": "Europe/Berlin",
    }


async def test_a_write_can_overwrite_an_existing_key(client, auth_header, workspace):
    """Merging must not mean a value can only ever be set once."""
    ws = await workspace()

    await _put(client, auth_header, ws, {"settings": {"timezone": "Europe/Berlin"}})
    await _put(client, auth_header, ws, {"settings": {"timezone": "Asia/Tokyo"}})

    stored = (await _get(client, auth_header, ws)).json()["settings"]
    assert stored["timezone"] == "Asia/Tokyo"


async def test_name_and_settings_write_together(client, auth_header, workspace):
    ws = await workspace()

    await _put(
        client, auth_header, ws,
        {"name": "Both At Once", "settings": {"timezone": "Asia/Tokyo"}},
    )

    body = (await _get(client, auth_header, ws)).json()
    assert body["name"] == "Both At Once"
    assert body["settings"]["timezone"] == "Asia/Tokyo"


async def test_an_empty_body_changes_nothing(client, auth_header, workspace):
    """A no-op write is fine; it just must not wipe the blob."""
    ws = await workspace()
    await _put(client, auth_header, ws, {"settings": {"timezone": "Asia/Tokyo"}})

    response = await _put(client, auth_header, ws, {})
    assert response.status_code == 200

    stored = (await _get(client, auth_header, ws)).json()["settings"]
    assert stored["timezone"] == "Asia/Tokyo"


# ---------------------------------------------------------------------------
# What must be refused rather than quietly ignored
# ---------------------------------------------------------------------------

async def test_an_unknown_top_level_key_is_refused(client, auth_header, workspace):
    """This is the request that started it.

    ``{"timezone": ...}`` at the top level is a plausible mistake -- the GET
    response is flat-ish, and the key is real one level down. It used to be
    accepted, ignored, and answered with 200, which is indistinguishable from
    having worked. It has to name the offending field instead.
    """
    ws = await workspace()

    response = await _put(client, auth_header, ws, {"timezone": "Australia/Sydney"})

    assert response.status_code == 422
    assert "timezone" in response.text


async def test_an_unusable_timezone_is_refused(client, auth_header, workspace):
    """The same accept-but-drop bug one layer down.

    The dashboard falls back to UTC for an unreadable zone, so storing one
    means telling the workspace the write succeeded and then quietly giving it
    the wrong day's numbers. The fallback stays as defence for existing rows;
    new writes are refused.
    """
    ws = await workspace()

    response = await _put(
        client, auth_header, ws, {"settings": {"timezone": "Mars/Olympus"}}
    )

    assert response.status_code == 422
    assert "timezone" in response.text
    assert (await _get(client, auth_header, ws)).json()["settings"] == {"locale": "en-GB"}


@pytest.mark.parametrize("key", ["approvals_required", "client_approval_required"])
async def test_a_non_boolean_flag_is_refused(client, auth_header, workspace, key):
    """``bool("false")`` is True. A workspace that sent the string would have
    turned the workflow on while believing it had turned it off."""
    ws = await workspace()

    response = await _put(client, auth_header, ws, {"settings": {key: "false"}})

    assert response.status_code == 422
    assert key in response.text


# ---------------------------------------------------------------------------
# Authorization is unchanged by any of this
# ---------------------------------------------------------------------------

async def test_a_viewer_cannot_write_settings(client, auth_header, workspace):
    ws = await workspace()

    response = await client.put(
        f"/api/v1/accounts/{ws['account_id']}/settings/",
        headers=auth_header(ws["viewer"]),
        json={"settings": {"approvals_required": True}},
    )

    assert response.status_code == 403


async def test_another_workspace_cannot_be_written(client, auth_header, workspace):
    ws = await workspace()
    other = await workspace()

    response = await client.put(
        f"/api/v1/accounts/{other['account_id']}/settings/",
        headers=auth_header(ws["owner"]),
        json={"settings": {"approvals_required": True}},
    )

    assert response.status_code in (403, 404)


async def test_an_unknown_workspace_is_404(client, auth_header, workspace):
    ws = await workspace()

    response = await client.put(
        f"/api/v1/accounts/{uuid.uuid4()}/settings/",
        headers=auth_header(ws["owner"]),
        json={"settings": {"approvals_required": True}},
    )

    assert response.status_code in (403, 404)


async def test_a_padded_timezone_is_stored_normalised(client, auth_header, workspace):
    """Whitespace is forgiven on the way in but not carried into storage, so
    the value that reads back is the value the reader will use."""
    ws = await workspace()

    response = await _put(
        client, auth_header, ws, {"settings": {"timezone": "  Asia/Tokyo  "}}
    )
    assert response.status_code == 200

    stored = (await _get(client, auth_header, ws)).json()["settings"]
    assert stored["timezone"] == "Asia/Tokyo"


async def test_an_empty_timezone_is_refused(client, auth_header, workspace):
    """An empty string is not "unset" -- it is a value the reader would have to
    silently interpret."""
    ws = await workspace()

    response = await _put(client, auth_header, ws, {"settings": {"timezone": "   "}})

    assert response.status_code == 422
