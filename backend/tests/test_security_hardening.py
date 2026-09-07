"""Assorted security fixes.

* Login used to say "email not found" or "incorrect password", which let anyone
  test an address and learn whether it was registered.
* The Meta webhook stored whatever was POSTed to it, unauthenticated -- anyone
  who knew the URL could write rows.
* CORS trusted every ``*.onrender.com`` origin with credentials, in the
  middleware and again in the error-response echo.
* The Gemini key travelled in the URL query string, where proxies and error
  reporters log it.
* Manual plan changes turned themselves on for any DEBUG run without Stripe
  keys, handing out paid tiers from a combination nobody chose.
"""

import hashlib
import hmac
import json
import uuid

import pytest

from app.core.config import settings

pytestmark = pytest.mark.asyncio

LOGIN_URL = "/api/v1/auth/login"
WEBHOOK_URL = "/api/v1/webhooks/meta"
PASSWORD = "hunter2-correct-horse"


# ---------------------------------------------------------------------------
# Login must not distinguish unknown email from wrong password
# ---------------------------------------------------------------------------

async def test_unknown_email_and_wrong_password_are_indistinguishable(
    client, user_factory
):
    """Same status and same body -- otherwise the form is a membership oracle."""
    user = await user_factory(password=PASSWORD)

    wrong_password = await client.post(
        LOGIN_URL, json={"email": user.email, "password": "definitely-not-it"}
    )
    unknown_email = await client.post(
        LOGIN_URL,
        json={
            "email": f"nobody-{uuid.uuid4().hex[:8]}@example.com",
            "password": "definitely-not-it",
        },
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json(), (
        "the two failures must be byte-identical"
    )


async def test_login_error_does_not_name_the_cause(client, user_factory):
    user = await user_factory(password=PASSWORD)
    response = await client.post(
        LOGIN_URL, json={"email": user.email, "password": "wrong"}
    )

    detail = response.json()["detail"].lower()
    assert detail == "invalid email or password"
    for leak in ("not found", "sign up", "incorrect password", "verify your password"):
        assert leak not in detail, f"error still hints at the cause: {detail!r}"


async def test_unknown_email_still_hashes_a_password(client, monkeypatch):
    """The unknown-address path must do the same work, or timing answers the
    question the error message no longer does."""
    import app.api.v1.endpoints.auth as auth_module

    calls: list[str] = []
    original = auth_module.verify_password_async

    async def _spy(plain, hashed):
        calls.append(hashed)
        return await original(plain, hashed)

    monkeypatch.setattr(auth_module, "verify_password_async", _spy)

    await client.post(
        LOGIN_URL,
        json={"email": f"ghost-{uuid.uuid4().hex[:8]}@example.com", "password": "x"},
    )

    assert calls, "no password verification ran for an unknown address"
    assert calls[0] == auth_module._DUMMY_PASSWORD_HASH


async def test_successful_login_still_works(client, user_factory):
    """The generic error must not have broken the happy path."""
    user = await user_factory(password=PASSWORD)
    response = await client.post(
        LOGIN_URL, json={"email": user.email, "password": PASSWORD}
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


# ---------------------------------------------------------------------------
# Meta webhook signature
# ---------------------------------------------------------------------------

def _signed(body: dict, secret: str) -> tuple[bytes, str]:
    raw = json.dumps(body).encode()
    digest = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return raw, f"sha256={digest}"


@pytest.fixture
def meta_secret(monkeypatch):
    secret = "test-meta-app-secret"
    monkeypatch.setattr(settings, "META_APP_SECRET", secret)
    return secret


async def test_unsigned_webhook_is_rejected(client, meta_secret):
    """The original endpoint stored anything posted to it."""
    response = await client.post(WEBHOOK_URL, json={"object": "page", "entry": []})

    assert response.status_code == 403
    assert "signature" in response.json()["detail"].lower()


async def test_webhook_with_wrong_signature_is_rejected(client, meta_secret):
    raw, _ = _signed({"object": "page", "entry": []}, "the-wrong-secret")

    response = await client.post(
        WEBHOOK_URL,
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=" + "0" * 64,
        },
    )
    assert response.status_code == 403


async def test_webhook_with_valid_signature_is_accepted(client, meta_secret):
    body = {"object": "page", "entry": [{"changes": [{"field": "feed"}]}]}
    raw, signature = _signed(body, meta_secret)

    response = await client.post(
        WEBHOOK_URL,
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "accepted"


async def test_signature_is_over_the_raw_body(client, meta_secret):
    """Re-serialising the parsed JSON changes whitespace and would not match --
    the digest has to be taken over exactly what arrived."""
    raw = b'{"object" :  "page",\n  "entry": []}'
    digest = hmac.new(meta_secret.encode(), raw, hashlib.sha256).hexdigest()

    response = await client.post(
        WEBHOOK_URL,
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": f"sha256={digest}",
        },
    )
    assert response.status_code == 200, response.text


async def test_webhook_rejected_when_no_secret_is_configured(client, monkeypatch):
    """Unverifiable means reject: an unauthenticated endpoint that writes to the
    database must not fall back to trusting the caller."""
    monkeypatch.setattr(settings, "META_APP_SECRET", "")
    body = {"object": "page", "entry": []}
    raw = json.dumps(body).encode()

    response = await client.post(
        WEBHOOK_URL,
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=" + "0" * 64,
        },
    )
    assert response.status_code == 403


async def test_rejected_webhook_stores_nothing(client, db_session, meta_secret):
    from sqlalchemy import func, select

    from app.models.webhook import Webhook

    before = (await db_session.execute(select(func.count(Webhook.id)))).scalar_one()
    await client.post(WEBHOOK_URL, json={"object": "page", "entry": []})
    after = (await db_session.execute(select(func.count(Webhook.id)))).scalar_one()

    assert after == before, "an unsigned webhook was recorded"


async def test_get_handshake_still_works(client, monkeypatch):
    monkeypatch.setattr(settings, "META_WEBHOOK_VERIFY_TOKEN", "the-verify-token")

    ok = await client.get(
        WEBHOOK_URL,
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "the-verify-token",
            "hub.challenge": "12345",
        },
    )
    assert ok.status_code == 200
    assert ok.text == "12345"

    bad = await client.get(
        WEBHOOK_URL,
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong",
            "hub.challenge": "12345",
        },
    )
    assert bad.status_code == 403


async def test_handshake_failure_does_not_log_the_expected_token(
    client, monkeypatch, caplog
):
    import logging

    monkeypatch.setattr(settings, "META_WEBHOOK_VERIFY_TOKEN", "SUPER-SECRET-VERIFY")

    with caplog.at_level(logging.DEBUG):
        await client.get(
            WEBHOOK_URL,
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong",
                "hub.challenge": "1",
            },
        )

    app_logs = "\n".join(
        r.getMessage() for r in caplog.records if r.name.startswith("app")
    )
    assert "SUPER-SECRET-VERIFY" not in app_logs


# ---------------------------------------------------------------------------
# The remaining fixes
# ---------------------------------------------------------------------------

async def test_cors_middleware_has_no_origin_regex():
    """Anyone can deploy to onrender.com; with credentials allowed, trusting the
    whole domain lets an attacker's origin read authenticated responses.

    Asserted against the configured middleware rather than the file's text, so
    the comment explaining the removal cannot satisfy the test.
    """
    from starlette.middleware.cors import CORSMiddleware

    from app.main import app

    cors = next(m for m in app.user_middleware if m.cls is CORSMiddleware)
    options = dict(getattr(cors, "kwargs", None) or getattr(cors, "options", {}))
    assert not options.get("allow_origin_regex"), "CORS still matches origins by pattern"
    assert options.get("allow_credentials") is True


async def test_configured_origins_contain_no_wildcards():
    """Production origins belong in the environment, not baked into config."""
    for origin in settings.CORS_ORIGINS:
        assert "*" not in origin, f"wildcard in CORS_ORIGINS: {origin}"


async def test_error_response_cors_echo_is_exact_match_only():
    """The 500 handler echoes CORS headers itself and had its own copy of the
    wildcard, so fixing only the middleware would have left the hole open.

    Exercised directly: that handler only runs for unhandled exceptions, so a
    normal 4xx request never reaches it -- asserting through one would pass
    whatever the echo does.
    """
    from starlette.datastructures import Headers
    from starlette.requests import Request

    from app.main import _cors_headers_for

    def _request_from(origin: str) -> Request:
        return Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/",
                "headers": Headers({"origin": origin}).raw,
            }
        )

    allowed = settings.CORS_ORIGINS[0]
    assert _cors_headers_for(_request_from(allowed))["Access-Control-Allow-Origin"] == allowed

    for hostile in (
        "https://evil-attacker.onrender.com",
        "https://marketing-automation-ayesha.onrender.com.evil.test",
        "https://attacker.example",
    ):
        assert _cors_headers_for(_request_from(hostile)) == {}, (
            f"error handler echoed CORS to {hostile}"
        )


async def test_gemini_key_is_not_put_in_a_url():
    from pathlib import Path

    import app.api.v1.endpoints.ai as ai_module

    source = Path(ai_module.__file__).read_text()
    assert "generateContent?key=" not in source
    assert 'x-goog-api-key' in source


async def test_manual_plan_change_requires_the_explicit_flag(monkeypatch):
    """It used to switch itself on for DEBUG runs without Stripe keys."""
    from app.api.v1.endpoints.billing import _manual_plan_change_enabled

    monkeypatch.setattr(settings, "DEBUG", True)
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "")
    monkeypatch.setattr(settings, "BILLING_ALLOW_MANUAL_PLAN_CHANGE", False)
    assert _manual_plan_change_enabled() is False, (
        "DEBUG without Stripe keys must not grant free tier changes"
    )

    monkeypatch.setattr(settings, "BILLING_ALLOW_MANUAL_PLAN_CHANGE", True)
    assert _manual_plan_change_enabled() is True


async def test_database_url_default_has_no_invented_password():
    from app.core.config import Settings

    default = Settings.model_fields["DATABASE_URL"].default
    assert "MyNewPassword123" not in default
    assert "postgres:postgres@" in default
