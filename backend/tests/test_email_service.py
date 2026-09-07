"""Transactional email delivery.

``EmailService._send`` used to only log, so password resets and team invitations
silently never arrived -- and the "body preview" it logged contained the reset
link, which is the credential itself.

These tests pin down three things: the flows actually enqueue a send with the
right recipient and link, a failing provider never breaks the API response, and
no token reaches the logs on any path.
"""

import logging
import uuid

import httpx
import pytest

from app.core.config import settings
from app.services.email_service import SENDGRID_ENDPOINT, EmailService

pytestmark = pytest.mark.asyncio

FORGOT_URL = "/api/v1/auth/forgot-password"
PASSWORD = "hunter2-correct-horse"


class _SendGridSpy:
    """Stands in for the SendGrid API and records what was sent."""

    def __init__(self, status_code: int = 202):
        self.status_code = status_code
        self.calls: list[dict] = []

    async def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(
            {
                "url": str(request.url),
                "headers": dict(request.headers),
                "json": __import__("json").loads(request.content.decode()),
            }
        )
        return httpx.Response(self.status_code, json={})

    # -- convenience accessors -------------------------------------------------
    @property
    def last(self) -> dict:
        assert self.calls, "no email was sent"
        return self.calls[-1]

    @property
    def recipient(self) -> str:
        return self.last["json"]["personalizations"][0]["to"][0]["email"]

    @property
    def subject(self) -> str:
        return self.last["json"]["subject"]

    def body(self, mime: str) -> str:
        for part in self.last["json"]["content"]:
            if part["type"] == mime:
                return part["value"]
        raise AssertionError(f"no {mime} part in the message")


@pytest.fixture
def sendgrid(monkeypatch):
    """Intercept the outbound HTTP call and configure an API key."""
    spy = _SendGridSpy()
    monkeypatch.setattr(settings, "SENDGRID_API_KEY", "SG.test-key")
    monkeypatch.setattr(settings, "FROM_EMAIL", "noreply@example.com")

    real_client = httpx.AsyncClient

    def _client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(spy.handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _client)
    return spy


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------

async def test_password_reset_posts_to_sendgrid(sendgrid):
    sent = await EmailService.send_password_reset_email("user@example.com", "TOK123")

    assert sent is True
    assert sendgrid.last["url"] == SENDGRID_ENDPOINT
    assert sendgrid.last["headers"]["authorization"] == "Bearer SG.test-key"
    assert sendgrid.recipient == "user@example.com"
    assert sendgrid.last["json"]["from"]["email"] == "noreply@example.com"


async def test_message_has_both_text_and_html_parts(sendgrid):
    await EmailService.send_password_reset_email("user@example.com", "TOK123")

    types = [part["type"] for part in sendgrid.last["json"]["content"]]
    # SendGrid requires increasing preference order: plain text first.
    assert types == ["text/plain", "text/html"]
    assert sendgrid.body("text/plain").strip()
    assert "<html" in sendgrid.body("text/html").lower()


async def test_reset_link_is_correct_and_in_both_parts(sendgrid):
    await EmailService.send_password_reset_email("user@example.com", "TOK123")

    expected = f"{settings.FRONTEND_URL}/reset-password?token=TOK123"
    assert expected in sendgrid.body("text/html")
    assert expected in sendgrid.body("text/plain")


async def test_invitation_link_uses_the_frontend_accept_route(sendgrid):
    """Must match the route the SPA actually serves (/accept-invite?token=)."""
    await EmailService.send_invitation_email(
        "invitee@example.com",
        inviter_name="Dana",
        account_name="Acme",
        token="INVITE9",
        role="editor",
    )

    expected = f"{settings.FRONTEND_URL}/accept-invite?token=INVITE9"
    assert sendgrid.recipient == "invitee@example.com"
    assert expected in sendgrid.body("text/html")
    assert expected in sendgrid.body("text/plain")
    assert "Dana" in sendgrid.body("text/plain")
    assert "Acme" in sendgrid.subject


async def test_html_escapes_user_controlled_values(sendgrid):
    """An account or inviter name must not be able to inject markup."""
    await EmailService.send_invitation_email(
        "invitee@example.com",
        inviter_name="<script>alert(1)</script>",
        account_name="Tom & Jerry",
        token="T",
    )

    html = sendgrid.body("text/html")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "Tom &amp; Jerry" in html


async def test_welcome_email_renders(sendgrid):
    class _User:
        email = "new@example.com"
        full_name = "New Person"

    assert await EmailService.send_welcome_email(_User()) is True
    assert sendgrid.recipient == "new@example.com"
    assert "New Person" in sendgrid.body("text/plain")


# ---------------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------------

async def test_provider_rejection_is_reported_not_raised(monkeypatch):
    monkeypatch.setattr(settings, "SENDGRID_API_KEY", "SG.test-key")
    spy = _SendGridSpy(status_code=400)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **k: real_client(*a, **{**k, "transport": httpx.MockTransport(spy.handler)}),
    )

    assert await EmailService.send_password_reset_email("u@example.com", "TOK") is False


async def test_transport_error_is_swallowed(monkeypatch):
    """A background task must not raise when the provider is unreachable."""
    monkeypatch.setattr(settings, "SENDGRID_API_KEY", "SG.test-key")

    async def _explode(request):
        raise httpx.ConnectError("network down")

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **k: real_client(*a, **{**k, "transport": httpx.MockTransport(_explode)}),
    )

    assert await EmailService.send_password_reset_email("u@example.com", "TOK") is False


# ---------------------------------------------------------------------------
# Suppression when unconfigured
# ---------------------------------------------------------------------------

async def test_no_api_key_in_debug_logs_suppressed_without_the_token(
    monkeypatch, caplog
):
    monkeypatch.setattr(settings, "SENDGRID_API_KEY", "")
    monkeypatch.setattr(settings, "DEBUG", True)

    with caplog.at_level(logging.INFO):
        sent = await EmailService.send_password_reset_email(
            "user@example.com", "SUPERSECRETTOKEN"
        )

    assert sent is False
    assert "email suppressed (dev)" in caplog.text
    assert "SUPERSECRETTOKEN" not in caplog.text


async def test_no_api_key_outside_debug_logs_an_error(monkeypatch, caplog):
    monkeypatch.setattr(settings, "SENDGRID_API_KEY", "")
    monkeypatch.setattr(settings, "DEBUG", False)

    with caplog.at_level(logging.DEBUG):
        sent = await EmailService.send_password_reset_email(
            "user@example.com", "SUPERSECRETTOKEN"
        )

    assert sent is False
    assert any(r.levelno >= logging.ERROR for r in caplog.records), (
        "an unconfigured provider outside DEBUG must log at ERROR"
    )
    assert "SUPERSECRETTOKEN" not in caplog.text


# ---------------------------------------------------------------------------
# Tokens must never reach the logs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status_code", [202, 400, 500])
async def test_token_never_appears_in_logs(monkeypatch, caplog, status_code):
    """The reset link is the credential; logs outlive it and get shipped
    elsewhere, so it must not be written on any path."""
    token = "TOKEN-THAT-MUST-NOT-LEAK"
    monkeypatch.setattr(settings, "SENDGRID_API_KEY", "SG.test-key")
    spy = _SendGridSpy(status_code=status_code)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **k: real_client(*a, **{**k, "transport": httpx.MockTransport(spy.handler)}),
    )

    with caplog.at_level(logging.DEBUG):
        await EmailService.send_password_reset_email("user@example.com", token)

    assert token not in caplog.text
    assert "reset-password?token=" not in caplog.text


async def test_transport_failure_does_not_log_the_token(monkeypatch, caplog):
    token = "ANOTHER-SECRET-TOKEN"
    monkeypatch.setattr(settings, "SENDGRID_API_KEY", "SG.test-key")

    async def _explode(request):
        raise httpx.ConnectError("network down")

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **k: real_client(*a, **{**k, "transport": httpx.MockTransport(_explode)}),
    )

    with caplog.at_level(logging.DEBUG):
        await EmailService.send_password_reset_email("user@example.com", token)

    assert token not in caplog.text


# ---------------------------------------------------------------------------
# The flows enqueue sends
# ---------------------------------------------------------------------------

async def test_forgot_password_enqueues_a_send(client, user_factory, sendgrid):
    """The endpoint responds 200 and the email goes out for a known address."""
    user = await user_factory(password=PASSWORD)

    response = await client.post(FORGOT_URL, json={"email": user.email})

    assert response.status_code == 200
    assert sendgrid.calls, "forgot-password did not send anything"
    assert sendgrid.recipient == user.email
    assert f"{settings.FRONTEND_URL}/reset-password?token=" in sendgrid.body("text/plain")


async def test_forgot_password_sends_nothing_for_unknown_address(client, sendgrid):
    """Still 200 -- the generic response is what prevents enumeration -- but no
    mail is sent to an address that has no account."""
    response = await client.post(
        FORGOT_URL, json={"email": f"nobody-{uuid.uuid4().hex[:8]}@example.com"}
    )

    assert response.status_code == 200
    assert sendgrid.calls == []


async def test_forgot_password_succeeds_when_the_provider_fails(
    client, user_factory, monkeypatch
):
    """A dead mail provider must not turn into a 500 for the user."""
    monkeypatch.setattr(settings, "SENDGRID_API_KEY", "SG.test-key")

    async def _explode(request):
        raise httpx.ConnectError("network down")

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **k: real_client(*a, **{**k, "transport": httpx.MockTransport(_explode)}),
    )
    user = await user_factory(password=PASSWORD)

    response = await client.post(FORGOT_URL, json={"email": user.email})
    assert response.status_code == 200


async def test_invite_enqueues_a_send_with_the_accept_link(
    client, auth_header, user_factory, account_factory, organization_factory, sendgrid
):
    """The teams.py TODO: inviting someone now actually emails them."""
    owner = await user_factory(full_name="Dana Owner")
    organization = await organization_factory(owner, max_team_members=10)
    account = await account_factory(
        owner, name="Acme Marketing", organization=organization
    )
    invitee_email = f"invitee-{uuid.uuid4().hex[:8]}@example.com"

    response = await client.post(
        f"/api/v1/accounts/{account.id}/team/invite",
        headers=auth_header(owner),
        json={"email": invitee_email, "role": "editor"},
    )

    assert response.status_code == 201, response.text
    assert sendgrid.calls, "invite did not send an email"
    assert sendgrid.recipient == invitee_email

    text = sendgrid.body("text/plain")
    assert f"{settings.FRONTEND_URL}/accept-invite?token=" in text
    assert "Dana Owner" in text
    assert "Acme Marketing" in text


async def test_invite_does_not_log_the_invitation_token(
    client, auth_header, user_factory, account_factory, organization_factory, sendgrid, caplog
):
    owner = await user_factory(full_name="Dana Owner")
    organization = await organization_factory(owner, max_team_members=10)
    account = await account_factory(
        owner, name="Acme Marketing", organization=organization
    )

    with caplog.at_level(logging.DEBUG):
        response = await client.post(
            f"/api/v1/accounts/{account.id}/team/invite",
            headers=auth_header(owner),
            json={"email": f"x-{uuid.uuid4().hex[:8]}@example.com", "role": "viewer"},
        )
    assert response.status_code == 201

    # Pull the real token out of the sent message and confirm the application's
    # own logging never writes it.
    text = sendgrid.body("text/plain")
    token = text.split("accept-invite?token=")[1].split()[0]
    assert token, "could not extract the invitation token"

    # Scoped to the application's own loggers ("app.*"). The database layer is
    # excluded deliberately: SQLAlchemy's statement echo (enabled by
    # `echo=settings.DEBUG` in app/core/database.py) and the driver's debug
    # logging both dump statements with their bound parameters, so the INSERT
    # that stores the invitation row necessarily contains the token. That is
    # database debugging behaviour rather than this feature's logging, and it
    # is off whenever DEBUG is false -- which config.py effectively requires in
    # production. What this asserts is that *our* code never writes a token.
    app_logs = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name.startswith("app")
    )
    assert token not in app_logs, "application logging leaked the invitation token"
