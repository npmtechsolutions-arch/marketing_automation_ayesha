"""Transactional email delivery via the SendGrid Web API.

Sends are made with httpx against SendGrid's v3 REST endpoint rather than the
official SDK, which is a synchronous, heavyweight dependency for what amounts
to one HTTP POST.

Two rules shape everything here:

**A failed email must never break the request that triggered it.** Password
reset and team invitation both respond successfully whether or not the mail
provider is reachable, so every send runs through FastAPI ``BackgroundTasks``
(off the response path) and every exception is caught and logged. The
alternative -- a 500 because SendGrid is slow -- fails the user in a way they
cannot act on.

**Tokens never reach the logs.** The reset link *is* the credential: anyone
holding it can take the account over. Logs are routinely shipped to third-party
aggregators and kept far longer than the token's one-hour life, so nothing here
logs a token, a link containing one, or a rendered body. The previous
implementation logged a 200-character preview of the rendered body; for an
invitation that window reached into the link and wrote the first characters of
the token, and any change to the template wording would have exposed more.
"""

import logging
from pathlib import Path
from typing import Any

import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings

logger = logging.getLogger(__name__)

SENDGRID_ENDPOINT = "https://api.sendgrid.com/v3/mail/send"

# Bounded so a hanging provider cannot pin a background task indefinitely.
REQUEST_TIMEOUT_SECONDS = 10.0

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "email"

# autoescape is on for HTML because template values are user-controlled --
# an account name or an inviter's display name would otherwise be able to
# inject markup into the message. Text templates are escaped-free by design.
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(enabled_extensions=("html",), default=False),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _render(template: str, **context: Any) -> str:
    return _env.get_template(template).render(**context)


class EmailService:
    """Transactional email.

    Every public method is a coroutine intended to be handed to
    ``BackgroundTasks.add_task`` so delivery happens after the response is
    returned.
    """

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    @classmethod
    async def _send(
        cls,
        *,
        to: str,
        subject: str,
        html_body: str,
        text_body: str,
    ) -> bool:
        """POST one message to SendGrid. Returns True if it was accepted.

        Never raises: callers run as background tasks where an exception would
        only produce an unhandled-error traceback long after the response.
        """
        if not settings.SENDGRID_API_KEY:
            # No provider configured. Say so without revealing the body, which
            # contains the reset or invitation link.
            if settings.DEBUG:
                logger.info(
                    "email suppressed (dev): to=%s subject=%r", to, subject
                )
            else:
                logger.error(
                    "SENDGRID_API_KEY is not set; email NOT sent. "
                    "to=%s subject=%r",
                    to,
                    subject,
                )
            return False

        payload = {
            # SendGrid requires content parts in increasing order of
            # preference, so text/plain must come before text/html.
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": settings.FROM_EMAIL},
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": text_body},
                {"type": "text/html", "value": html_body},
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    SENDGRID_ENDPOINT,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {settings.SENDGRID_API_KEY}",
                        "Content-Type": "application/json",
                    },
                )
        except Exception as exc:  # noqa: BLE001 - a send must never propagate
            logger.exception(
                "Email delivery failed (transport error). to=%s subject=%r error=%s",
                to,
                subject,
                type(exc).__name__,
            )
            return False

        if response.status_code == 202:
            logger.info("Email accepted by SendGrid. to=%s subject=%r", to, subject)
            return True

        # SendGrid reports field-level problems in the body; it echoes none of
        # our content back, so this is safe to log. Truncated to keep one bad
        # response from flooding the log.
        logger.error(
            "Email delivery rejected. to=%s subject=%r status=%s detail=%s",
            to,
            subject,
            response.status_code,
            response.text[:500],
        )
        return False

    # ------------------------------------------------------------------
    # Password reset
    # ------------------------------------------------------------------

    @classmethod
    async def send_password_reset_email(cls, email: str, token: str) -> bool:
        """Send a password reset link.

        ``token`` is a credential -- it is only ever interpolated into the
        message, never logged.
        """
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        context = {
            "subject": "Reset your MarketEngine password",
            "reset_url": reset_url,
            "expires_in": "1 hour",
        }
        return await cls._send(
            to=email,
            subject=context["subject"],
            html_body=_render("password_reset.html", **context),
            text_body=_render("password_reset.txt", **context),
        )

    # ------------------------------------------------------------------
    # Team invitation
    # ------------------------------------------------------------------

    @classmethod
    async def send_invitation_email(
        cls,
        email: str,
        inviter_name: str,
        account_name: str,
        token: str,
        role: str = "member",
    ) -> bool:
        """Invite someone to join an account."""
        invite_url = f"{settings.FRONTEND_URL}/accept-invite?token={token}"
        subject = f"{inviter_name} invited you to {account_name} on MarketEngine"
        context = {
            "subject": subject,
            "invite_url": invite_url,
            "inviter_name": inviter_name,
            "account_name": account_name,
            "role": role,
            "role_article": "an" if role[:1].lower() in "aeiou" else "a",
        }
        return await cls._send(
            to=email,
            subject=subject,
            html_body=_render("team_invitation.html", **context),
            text_body=_render("team_invitation.txt", **context),
        )

    # ------------------------------------------------------------------
    # Account health
    # ------------------------------------------------------------------

    @classmethod
    async def send_account_health_email(
        cls,
        email: str,
        *,
        user_name: str,
        account_name: str,
        platform: str,
        health: str,
        detail: str = "",
    ) -> bool:
        """Warn a workspace manager that a connection is failing.

        Sent once per state change, not once per sweep -- see
        app.services.account_health. An hourly reminder about the same broken
        account is how people learn to filter these out.
        """
        expiring = health == "expiring"
        subject = (
            f"Action needed: {platform} connection for {account_name} is expiring"
            if expiring
            else f"{platform} disconnected for {account_name}"
        )
        context = {
            "subject": subject,
            "user_name": user_name,
            "account_name": account_name,
            "platform": platform,
            "health": health,
            "detail": detail,
            "expiring": expiring,
            "reconnect_url": f"{settings.FRONTEND_URL}/social-accounts",
        }
        return await cls._send(
            to=email,
            subject=subject,
            html_body=_render("account_health.html", **context),
            text_body=_render("account_health.txt", **context),
        )

    # ------------------------------------------------------------------
    # Welcome
    # ------------------------------------------------------------------

    @classmethod
    async def send_welcome_email(cls, user: Any) -> bool:
        """Welcome a newly registered user."""
        context = {
            "subject": "Welcome to MarketEngine AI",
            "name": getattr(user, "full_name", None) or "there",
            "onboarding_url": f"{settings.FRONTEND_URL}/onboarding",
        }
        return await cls._send(
            to=getattr(user, "email", ""),
            subject=context["subject"],
            html_body=_render("welcome.html", **context),
            text_body=_render("welcome.txt", **context),
        )
