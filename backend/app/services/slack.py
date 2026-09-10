"""Slack delivery, over an incoming webhook.

Chosen because it is the one messaging integration that is free, needs no app
review, and can be proven end to end today: a workspace pastes a webhook URL
and the next event arrives in their channel. WhatsApp needs Meta Business
review and belongs with the other tier-gated work.

Two rules from earlier phases apply here and both are about not letting a
notification break the thing it is describing:

* **A delivery failure is logged, never raised.** This is the email rule from
  0.7. A publish that reached the platform must not be reported as failed
  because Slack was down, and a report that rendered must not be marked FAILED
  because a webhook 500'd. Every entry point here swallows and logs.
* **State-change events fire once per change**, not once per sweep. That gate
  lives with the caller that knows what changed -- ``account_health`` already
  only notifies on a transition -- and this module does not try to
  second-guess it.

The message is Block Kit rather than plain text so it renders as a card, but
deliberately compact: a title, a line of context, and at most a handful of
fields. A notification that fills a channel is one people mute.
"""

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

# Slack's own guidance is to answer a webhook quickly; the caller is usually
# inside a request or a worker loop, so a hanging endpoint must not hold it.
TIMEOUT_SECONDS = 8.0

# Slack truncates long text anyway, and a wall of text in a channel is how
# integrations get muted.
MAX_TEXT = 2800

_ALLOWED_HOSTS = ("hooks.slack.com",)


class SlackNotConfigured(Exception):
    """No webhook URL on this workspace."""


def is_valid_webhook(url: Optional[str]) -> bool:
    """Whether this looks like a Slack incoming webhook.

    Checked because the field is user-entered and gets POSTed to on every
    matching event. Restricting the host keeps a typo -- or a paste of some
    other service's URL -- from turning the notification layer into a
    request-forwarder aimed wherever the text happened to point.
    """
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if not url.startswith("https://"):
        return False
    try:
        host = url.split("/", 3)[2].lower()
    except IndexError:
        return False
    return host in _ALLOWED_HOSTS


def build_blocks(
    *,
    title: str,
    message: str,
    fields: Optional[dict[str, str]] = None,
    action_url: Optional[str] = None,
    action_label: str = "Open in MarketEngine",
) -> dict[str, Any]:
    """A compact Block Kit payload.

    ``text`` is set as well as ``blocks`` because that is what Slack shows in a
    notification preview and in clients that do not render blocks; omitting it
    produces "This content can't be displayed".
    """
    trimmed = (message or "")[:MAX_TEXT]
    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": title[:150], "emoji": True},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": trimmed or "_no detail_"},
        },
    ]

    if fields:
        # Slack renders at most 10 fields in a section, two per row.
        pairs = list(fields.items())[:10]
        blocks.append({
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*{key}*\n{value}"}
                for key, value in pairs
            ],
        })

    if action_url:
        blocks.append({
            "type": "actions",
            "elements": [{
                "type": "button",
                "text": {"type": "plain_text", "text": action_label, "emoji": True},
                "url": action_url,
            }],
        })

    return {"text": f"{title} — {trimmed}"[:MAX_TEXT], "blocks": blocks}


async def post(webhook_url: Optional[str], payload: dict[str, Any]) -> bool:
    """Send one message. Returns whether Slack accepted it.

    Never raises. The caller is a publish, an approval or a report render, and
    none of them should fail because a chat integration did.
    """
    if not is_valid_webhook(webhook_url):
        logger.warning("Slack webhook is missing or not a hooks.slack.com URL.")
        return False

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.post(webhook_url, json=payload)
    except Exception as exc:  # noqa: BLE001 - a chat failure is not a publish failure
        logger.warning("Slack delivery failed (%s): %s", type(exc).__name__, exc)
        return False

    if response.status_code == 200:
        return True

    # Slack answers with a short plain-text reason ("no_service", "invalid_payload").
    logger.warning(
        "Slack rejected the message: %s %s",
        response.status_code, (response.text or "")[:200],
    )
    return False


async def send_test(webhook_url: Optional[str]) -> tuple[bool, str]:
    """The settings button. Returns (ok, a sentence for the user).

    Reports the reason rather than a bare failure: "invalid_payload" in a log
    nobody reads is how an integration stays quietly broken.
    """
    if not is_valid_webhook(webhook_url):
        return False, (
            "That does not look like a Slack incoming webhook. It should start "
            "with https://hooks.slack.com/."
        )

    payload = build_blocks(
        title="MarketEngine is connected",
        message=(
            "This is a test message. Real notifications will arrive here when "
            "the events you have switched on happen."
        ),
    )
    if await post(webhook_url, payload):
        return True, "Test message sent — check your Slack channel."
    return False, (
        "Slack did not accept the message. Check the webhook is still active "
        "in your Slack app settings."
    )
