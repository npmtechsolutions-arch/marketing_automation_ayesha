"""The HubSpot integration.

Three things carry most of the weight here, and each is a rule from an earlier
phase applied to a new kind of data:

* **Tokens are encrypted at rest**, proven by reading the raw column — the
  standard the Slack session set, because "we declared the type" is not
  evidence that the value was encrypted.
* **The CRM is organization-scoped**, so one agency's portal is invisible to
  another's. A leak here is a leak of a company's customer list.
* **Sending twice updates one contact.** HubSpot dedupes on email and a social
  inbox has none, so the provider searches on `platform:handle` first.
  Without that, every press of "Send to CRM" would make a new person.

Nothing here is fabricated: a contact carries the handle, the platform and a
link back, because that is the honest extent of what a social conversation
knows about someone.
"""

import json
import uuid

import httpx
import pytest

from app.integrations import hubspot
from app.integrations.base import (
    ContactIdentity,
    CrmAPIError,
    CrmAuthExpired,
    CrmNotConnected,
    NotImplementedInV1,
    SocialContact,
)
from app.models.crm_connection import CrmConnection
from app.services import crm

PASSWORD = "TestPass123!"
TOKEN = "hs-access-token-abc123"


class FakeHubSpot:
    """A HubSpot that records what it was asked and answers as configured."""

    def __init__(self):
        self.contacts: dict[str, dict] = {}
        self.requests: list[httpx.Request] = []
        self.search_status = 200
        self.write_status = None  # None = behave normally
        self.next_id = 1000

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path

        if path.endswith("/oauth/v1/token"):
            return httpx.Response(200, json={
                "access_token": TOKEN,
                "refresh_token": "hs-refresh-xyz",
                "expires_in": 1800,
            })
        if "/oauth/v1/access-tokens/" in path:
            return httpx.Response(200, json={"hub_id": 42, "hub_domain": "acme.example"})
        if path.endswith("/crm/v3/objects/contacts/search"):
            if self.search_status != 200:
                return httpx.Response(self.search_status, json={"message": "search boom"})
            key = json.loads(request.content)["filterGroups"][0]["filters"][0]["value"]
            found = self.contacts.get(key)
            return httpx.Response(200, json={
                "results": [{"id": found["id"]}] if found else []
            })
        if path.endswith("/crm/v3/objects/contacts"):
            if self.write_status:
                return httpx.Response(self.write_status, json={"message": "write boom"})
            body = json.loads(request.content)["properties"]
            self.next_id += 1
            record = {"id": str(self.next_id), "properties": body}
            self.contacts[body[hubspot.HANDLE_PROPERTY]] = record
            return httpx.Response(201, json={"id": record["id"]})
        if "/crm/v3/objects/contacts/" in path:  # PATCH by id
            if self.write_status:
                return httpx.Response(self.write_status, json={"message": "write boom"})
            contact_id = path.rsplit("/", 1)[-1]
            body = json.loads(request.content)["properties"]
            for record in self.contacts.values():
                if record["id"] == contact_id:
                    record["properties"].update(body)
            return httpx.Response(200, json={"id": contact_id})
        if "/oauth/v1/refresh-tokens/" in path:
            return httpx.Response(204)
        return httpx.Response(404, json={"message": f"unhandled {path}"})


@pytest.fixture
def fake_hubspot(monkeypatch):
    fake = FakeHubSpot()
    real_client = httpx.AsyncClient

    def _client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(fake.handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _client)
    monkeypatch.setattr(
        hubspot.settings, "HUBSPOT_CLIENT_ID", "cid", raising=False
    )
    monkeypatch.setattr(
        hubspot.settings, "HUBSPOT_CLIENT_SECRET", "secret", raising=False
    )
    return fake


@pytest.fixture
async def org(db_session, user_factory, organization_factory, account_factory):
    async def _make():
        owner = await user_factory(password=PASSWORD)
        organization = await organization_factory(owner)
        account = await account_factory(owner, organization=organization)
        return {"owner": owner, "organization": organization, "account": account}

    return _make


async def _connect(db_session, organization, user=None, *, refresh="hs-refresh-xyz"):
    connection = CrmConnection(
        id=uuid.uuid4(),
        organization_id=organization.id,
        provider="hubspot",
        access_token=TOKEN,
        refresh_token=refresh,
        external_account_id="42",
        external_account_name="acme.example",
        connected_by=user.id if user else None,
    )
    db_session.add(connection)
    await db_session.flush()
    return connection


# ---------------------------------------------------------------------------
# The credential
# ---------------------------------------------------------------------------

async def test_tokens_are_encrypted_at_rest(db_session, org):
    """Proven by reading the raw column.

    Anyone holding these can read and write a company's customer records.
    """
    from sqlalchemy import text

    ws = await org()
    connection = await _connect(db_session, ws["organization"], ws["owner"])
    await db_session.flush()

    # No id predicate: the column's storage format differs by dialect and a
    # mismatched bind would return nothing, which would make this test pass by
    # finding no row at all. One row exists; read it.
    rows = (
        await db_session.execute(
            text("SELECT access_token, refresh_token FROM crm_connections")
        )
    ).all()
    assert len(rows) == 1, "expected exactly one connection to inspect"
    row = rows[0]

    assert connection.access_token == TOKEN, "the ORM must see plaintext"
    assert row[0] != TOKEN, "the access token is stored in the clear"
    assert row[1] != "hs-refresh-xyz", "the refresh token is stored in the clear"


async def test_reconnecting_updates_in_place_rather_than_accumulating(
    db_session, org, fake_hubspot
):
    """Two rows for one provider would be two portals competing for the same
    action. 1.9's rule, applied to credentials."""
    from sqlalchemy import func, select

    from app.integrations.base import OAuthTokens

    ws = await org()
    await _connect(db_session, ws["organization"], ws["owner"])

    await crm.save_connection(
        db_session, ws["organization"].id, "hubspot",
        OAuthTokens(access_token="second-token", refresh_token="second-refresh"),
        user_id=ws["owner"].id,
    )

    count = (
        await db_session.execute(
            select(func.count(CrmConnection.id)).where(
                CrmConnection.organization_id == ws["organization"].id
            )
        )
    ).scalar()
    assert count == 1
    connection = await crm.connection_for(db_session, ws["organization"].id, "hubspot")
    assert connection.access_token == "second-token"


async def test_a_reconsent_without_a_new_refresh_token_keeps_the_old_one(
    db_session, org
):
    """Overwriting with None would silently un-connect them."""
    from app.integrations.base import OAuthTokens

    ws = await org()
    await _connect(db_session, ws["organization"], ws["owner"])

    await crm.save_connection(
        db_session, ws["organization"].id, "hubspot",
        OAuthTokens(access_token="new-access", refresh_token=None),
    )

    connection = await crm.connection_for(db_session, ws["organization"].id, "hubspot")
    assert connection.refresh_token == "hs-refresh-xyz"


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------

async def test_one_organizations_connection_is_invisible_to_another(
    db_session, org, fake_hubspot
):
    """A leak here is a leak of a company's customer list."""
    a = await org()
    b = await org()
    await _connect(db_session, a["organization"], a["owner"])

    assert await crm.connection_for(db_session, a["organization"].id, "hubspot")
    assert await crm.connection_for(db_session, b["organization"].id, "hubspot") is None

    with pytest.raises(CrmNotConnected):
        await crm.send_contact(
            db_session, b["organization"].id,
            SocialContact(handle="@someone", platform="twitter"),
        )


# ---------------------------------------------------------------------------
# Idempotency -- the point of the search-then-write design
# ---------------------------------------------------------------------------

async def test_sending_the_same_thread_twice_updates_one_contact(
    db_session, org, fake_hubspot
):
    ws = await org()
    await _connect(db_session, ws["organization"], ws["owner"])
    contact = SocialContact(
        handle="@ada", platform="twitter", display_name="Ada Lovelace",
        conversation_url="https://x.com/ada/status/1",
    )

    first = await crm.send_contact(db_session, ws["organization"].id, contact)
    second = await crm.send_contact(db_session, ws["organization"].id, contact)

    assert first.created is True
    assert second.created is False, "the second send made a duplicate"
    assert first.provider_id == second.provider_id
    assert len(fake_hubspot.contacts) == 1


async def test_the_same_handle_on_two_platforms_is_two_people(
    db_session, org, fake_hubspot
):
    """@acme on X and @acme on Instagram are not necessarily the same person,
    which is why the key carries the platform."""
    ws = await org()
    await _connect(db_session, ws["organization"], ws["owner"])

    await crm.send_contact(
        db_session, ws["organization"].id,
        SocialContact(handle="@acme", platform="twitter"),
    )
    await crm.send_contact(
        db_session, ws["organization"].id,
        SocialContact(handle="@acme", platform="instagram"),
    )

    assert len(fake_hubspot.contacts) == 2


async def test_a_failed_lookup_does_not_become_a_new_contact(
    db_session, org, fake_hubspot
):
    """A search that errors must not silently read as "no match".

    That would turn every send during a HubSpot incident into a duplicate
    person, and nobody would notice until the list was full of them.
    """
    ws = await org()
    await _connect(db_session, ws["organization"], ws["owner"])
    fake_hubspot.search_status = 500

    with pytest.raises(CrmAPIError):
        await crm.send_contact(
            db_session, ws["organization"].id,
            SocialContact(handle="@ada", platform="twitter"),
        )
    assert fake_hubspot.contacts == {}


# ---------------------------------------------------------------------------
# Nothing invented
# ---------------------------------------------------------------------------

def test_a_single_word_display_name_does_not_get_a_surname():
    """Guessing a surname puts an invented name into a CRM someone will later
    address them by."""
    properties = hubspot._properties_for(
        SocialContact(handle="@ada", platform="twitter", display_name="Ada"),
        "twitter:@ada",
    )

    assert properties["firstname"] == "Ada"
    assert "lastname" not in properties


def test_no_email_is_invented_when_none_is_known():
    properties = hubspot._properties_for(
        SocialContact(handle="@ada", platform="twitter", display_name="Ada Lovelace"),
        "twitter:@ada",
    )

    assert "email" not in properties
    assert properties[hubspot.HANDLE_PROPERTY] == "twitter:@ada"


# ---------------------------------------------------------------------------
# What v1 refuses, and how
# ---------------------------------------------------------------------------

async def test_out_of_scope_capabilities_refuse_by_name():
    """"HubSpot cannot" and "we have not built it" are different sentences and
    only one is worth waiting for."""
    provider = hubspot.HubSpotProvider()

    with pytest.raises(NotImplementedInV1):
        await provider.list_contacts()
    with pytest.raises(NotImplementedInV1):
        await provider.create_deal()


def test_the_capability_sheet_says_what_v1_does_not_do():
    caps = hubspot.HubSpotProvider.capabilities

    assert caps.supports_contact_upsert is True
    assert caps.supports_contact_read is False
    assert caps.supports_deals is False
    assert caps.supports_attribution is False
    assert caps.identity is ContactIdentity.SEARCH_THEN_WRITE


def test_salesforce_is_not_registered_and_that_is_deliberate():
    from app.integrations.registry import UnknownProvider, get_provider, known_slugs

    assert tuple(known_slugs()) == ("hubspot",)
    with pytest.raises(UnknownProvider):
        get_provider("salesforce")


# ---------------------------------------------------------------------------
# Auth failures say "reconnect", not "retry"
# ---------------------------------------------------------------------------

async def test_a_rejected_token_asks_for_a_reconnect(db_session, org, fake_hubspot):
    ws = await org()
    await _connect(db_session, ws["organization"], ws["owner"])
    fake_hubspot.search_status = 401

    with pytest.raises(CrmAuthExpired):
        await crm.send_contact(
            db_session, ws["organization"].id,
            SocialContact(handle="@ada", platform="twitter"),
        )


async def test_an_expired_token_with_no_refresh_token_asks_for_a_reconnect(
    db_session, org, fake_hubspot
):
    from datetime import datetime, timedelta, timezone

    ws = await org()
    connection = await _connect(db_session, ws["organization"], ws["owner"], refresh=None)
    connection.token_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await db_session.flush()

    with pytest.raises(CrmAuthExpired):
        await crm.ensure_fresh(db_session, connection)


# ---------------------------------------------------------------------------
# The inbox action
# ---------------------------------------------------------------------------

@pytest.fixture
async def thread_in_org(db_session, org, social_account_factory):
    """A conversation to send, in an organization we control."""
    from datetime import datetime, timezone

    from app.models.inbox import (
        InboxMessage,
        InboxThread,
        MessageDirection,
        ThreadStatus,
        ThreadType,
    )

    async def _make(*, handle="priya"):
        ws = await org()
        connection = await social_account_factory(
            ws["owner"], ws["account"], slug="facebook"
        )
        row = InboxThread(
            id=uuid.uuid4(), account_id=ws["account"].id,
            social_account_id=connection.id, type=ThreadType.COMMENT,
            external_id="t1", participant="Priya Patel",
            participant_handle=handle, permalink="https://fb.example/c/1",
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


def _send_url(account_id, thread_id):
    return f"/api/v1/accounts/{account_id}/inbox/{thread_id}/send-to-crm"


async def test_sending_a_thread_creates_a_contact(
    client, auth_header, db_session, thread_in_org, fake_hubspot
):
    ws, row = await thread_in_org()
    await _connect(db_session, ws["organization"], ws["owner"])

    response = await client.post(
        _send_url(ws["account"].id, row.id), headers=auth_header(ws["owner"])
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["created"] is True
    assert body["contact_id"]
    # The handle carries the platform, so the key is unambiguous.
    assert "facebook:priya" in fake_hubspot.contacts


async def test_a_viewer_can_read_the_thread_but_not_send_it(
    client, auth_header, db_session, thread_in_org, fake_hubspot,
    user_factory, member_factory,
):
    """content.create, not content.view.

    Reading a conversation and filing the person into the company's CRM are
    different kinds of act.
    """
    from app.models.team_member import InvitationStatus, TeamRole

    ws, row = await thread_in_org()
    await _connect(db_session, ws["organization"], ws["owner"])
    viewer = await user_factory(password=PASSWORD)
    await member_factory(
        viewer, ws["account"], role=TeamRole.VIEWER,
        invitation_status=InvitationStatus.ACCEPTED,
    )

    readable = await client.get(
        f"/api/v1/accounts/{ws['account'].id}/inbox/{row.id}",
        headers=auth_header(viewer),
    )
    sendable = await client.post(
        _send_url(ws["account"].id, row.id), headers=auth_header(viewer)
    )

    assert readable.status_code == 200
    assert sendable.status_code == 403
    assert fake_hubspot.contacts == {}


async def test_a_hubspot_failure_is_visible_and_leaves_the_thread_alone(
    client, auth_header, db_session, thread_in_org, fake_hubspot
):
    """A CRM write *is* the point of this action, so unlike Slack it surfaces.

    But it surfaces on this action only: the thread is not touched on the way
    in, so there is no half-written state to recover from.
    """
    from sqlalchemy import select

    from app.models.inbox import InboxThread

    ws, row = await thread_in_org()
    await _connect(db_session, ws["organization"], ws["owner"])
    fake_hubspot.write_status = 500
    before = row.status

    response = await client.post(
        _send_url(ws["account"].id, row.id), headers=auth_header(ws["owner"])
    )

    assert response.status_code == 502
    assert "boom" in response.json()["detail"]

    reread = (
        await db_session.execute(select(InboxThread).where(InboxThread.id == row.id))
    ).scalar_one()
    await db_session.refresh(reread)
    assert reread.status == before
    assert reread.participant_handle == "priya"


async def test_sending_without_a_connection_says_so(
    client, auth_header, thread_in_org, fake_hubspot
):
    ws, row = await thread_in_org()

    response = await client.post(
        _send_url(ws["account"].id, row.id), headers=auth_header(ws["owner"])
    )

    assert response.status_code == 409
    assert "Connect one in Settings" in response.json()["detail"]


async def test_a_thread_with_no_handle_is_refused_rather_than_duplicated(
    client, auth_header, db_session, thread_in_org, fake_hubspot
):
    """Without an identity to key on, every send would make a new person."""
    ws, row = await thread_in_org(handle="")
    await _connect(db_session, ws["organization"], ws["owner"])

    response = await client.post(
        _send_url(ws["account"].id, row.id), headers=auth_header(ws["owner"])
    )

    assert response.status_code == 409
    assert "duplicates" in response.json()["detail"]
    assert fake_hubspot.contacts == {}


async def test_the_integrations_list_never_returns_a_token(
    client, auth_header, db_session, org, fake_hubspot
):
    ws = await org()
    await _connect(db_session, ws["organization"], ws["owner"])

    response = await client.get(
        f"/api/v1/organizations/{ws['organization'].id}/integrations/",
        headers=auth_header(ws["owner"]),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    hub = next(i for i in body["items"] if i["provider"] == "hubspot")
    assert hub["connected"] is True
    assert hub["account_name"] == "acme.example"
    assert hub["connected_by"]
    assert TOKEN not in response.text
    assert "hs-refresh-xyz" not in response.text
    # What it does not do, stated rather than omitted.
    assert hub["capabilities"]["deals"] is False
    assert hub["capabilities"]["contact_read"] is False


async def test_another_organization_cannot_see_or_disconnect_the_connection(
    client, auth_header, db_session, org, fake_hubspot
):
    a = await org()
    b = await org()
    await _connect(db_session, a["organization"], a["owner"])

    listed = await client.get(
        f"/api/v1/organizations/{a['organization'].id}/integrations/",
        headers=auth_header(b["owner"]),
    )
    removed = await client.delete(
        f"/api/v1/organizations/{a['organization'].id}/integrations/hubspot",
        headers=auth_header(b["owner"]),
    )

    assert listed.status_code == 403
    assert removed.status_code == 403
    assert await crm.connection_for(db_session, a["organization"].id, "hubspot")


def test_every_crm_provider_has_a_home_in_settings():
    """The #18-style contract, applied to integrations.

    A provider the server knows about and no screen can connect is a feature
    that exists only in the code — the exact shape of the approvals workflow
    that shipped with no way to switch it on.
    """
    import pathlib

    from app.integrations.registry import known_slugs

    page = (
        pathlib.Path(__file__).resolve().parents[2]
        / "frontend" / "src" / "pages" / "settings" / "SettingsPage.tsx"
    ).read_text()

    assert "IntegrationsTab" in page, "there is no Integrations settings section"
    assert "/integrations/" in page, "the section never calls the integrations API"
    for slug in known_slugs():
        # The section renders whatever the API lists, so the contract is that
        # it lists them rather than hardcoding one.
        assert "items" in page, f"{slug} has no home in settings"


def test_an_unknown_provider_message_reads_as_a_sentence():
    """KeyError renders its argument with repr(), so the detail reached the
    user as \"'salesforce' is not a CRM...\" — quotes and all. A message a
    person reads should not carry the punctuation of the exception type that
    carried it. Found by calling the endpoint."""
    from app.integrations.registry import UnknownProvider, get_provider

    try:
        get_provider("salesforce")
    except UnknownProvider as exc:
        detail = str(exc)

    assert not detail.startswith('"')
    assert detail.startswith("'salesforce' is not a CRM")
