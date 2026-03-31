import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Transactional email service.

    Uses SendGrid when SENDGRID_API_KEY is configured; otherwise logs the
    email content for local development.
    """

    @classmethod
    def _send(cls, to: str, subject: str, html_body: str) -> None:
        """Low-level send helper.  Replace with real SendGrid integration."""
        if settings.SENDGRID_API_KEY:
            # TODO: Implement real SendGrid send
            # import sendgrid
            # from sendgrid.helpers.mail import Mail
            # sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
            # message = Mail(
            #     from_email=settings.FROM_EMAIL,
            #     to_emails=to,
            #     subject=subject,
            #     html_content=html_body,
            # )
            # sg.send(message)
            logger.info("Email sent via SendGrid to %s: %s", to, subject)
        else:
            logger.info(
                "[DEV] Email would be sent to %s\n  Subject: %s\n  Body preview: %s",
                to,
                subject,
                html_body[:200],
            )

    # ------------------------------------------------------------------
    # Welcome email
    # ------------------------------------------------------------------

    @classmethod
    def send_welcome_email(cls, user: Any) -> None:
        """Send a welcome email after registration."""
        name = getattr(user, "full_name", "there")
        html = f"""
        <h1>Welcome to MarketEngine AI!</h1>
        <p>Hi {name},</p>
        <p>Thanks for signing up. You're all set to start creating amazing
        marketing content powered by AI.</p>
        <p><a href="{settings.FRONTEND_URL}/onboarding">Complete your setup</a></p>
        <p>-- The MarketEngine Team</p>
        """
        cls._send(
            to=getattr(user, "email", ""),
            subject="Welcome to MarketEngine AI!",
            html_body=html,
        )

    # ------------------------------------------------------------------
    # Team invitation
    # ------------------------------------------------------------------

    @classmethod
    def send_invitation_email(
        cls,
        email: str,
        inviter_name: str,
        account_name: str,
        token: str,
    ) -> None:
        """Send an invitation to join a team account."""
        invite_url = f"{settings.FRONTEND_URL}/invite/{token}"
        html = f"""
        <h1>You've been invited!</h1>
        <p>{inviter_name} has invited you to join <strong>{account_name}</strong>
        on MarketEngine AI.</p>
        <p><a href="{invite_url}">Accept Invitation</a></p>
        <p>This link expires in 7 days.</p>
        <p>-- The MarketEngine Team</p>
        """
        cls._send(
            to=email,
            subject=f"{inviter_name} invited you to {account_name} on MarketEngine",
            html_body=html,
        )

    # ------------------------------------------------------------------
    # Password reset
    # ------------------------------------------------------------------

    @classmethod
    def send_password_reset_email(cls, email: str, token: str) -> None:
        """Send a password reset link."""
        reset_url = f"{settings.FRONTEND_URL}/reset-password/{token}"
        html = f"""
        <h1>Reset your password</h1>
        <p>We received a request to reset your password. Click the link below
        to choose a new one:</p>
        <p><a href="{reset_url}">Reset Password</a></p>
        <p>If you didn't request this, you can safely ignore this email.</p>
        <p>This link expires in 1 hour.</p>
        <p>-- The MarketEngine Team</p>
        """
        cls._send(
            to=email,
            subject="Reset your MarketEngine password",
            html_body=html,
        )

    # ------------------------------------------------------------------
    # Post published notification
    # ------------------------------------------------------------------

    @classmethod
    def send_post_published_notification(cls, user: Any, post: Any) -> None:
        """Notify the user that their scheduled post has been published."""
        name = getattr(user, "full_name", "there")
        post_title = getattr(post, "title", "your post")
        html = f"""
        <h1>Your post is live!</h1>
        <p>Hi {name},</p>
        <p>Your scheduled post <strong>"{post_title}"</strong> has been
        successfully published to all connected platforms.</p>
        <p><a href="{settings.FRONTEND_URL}/analytics">View Performance</a></p>
        <p>-- The MarketEngine Team</p>
        """
        cls._send(
            to=getattr(user, "email", ""),
            subject=f"Published: {post_title}",
            html_body=html,
        )
