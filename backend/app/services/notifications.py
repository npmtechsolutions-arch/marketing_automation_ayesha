"""Which channels an event goes to.

Three channels exist: **in_app**, **email** and **slack**. The first two were
already here, implemented where the events are raised -- `approvals.notify`
writes notification rows and queues its own mail, `account_health` does the
same, `report_jobs` likewise. This module does not move them. Rewiring three
working notification paths to prove a point about layering would risk the
things that already work in order to tidy the shape of the code, and the
routing that actually needed a home is Slack's.

So: this owns **which events reach Slack for a workspace**, and the delivery
itself lives in :mod:`app.services.slack`. `channels_for()` names all three so
the routing is inspectable and testable as a matrix, and says plainly which of
them this module dispatches.

Two inherited rules:

* **A delivery failure never reaches the triggering flow** (0.7's email rule).
  Everything here returns a bool; nothing raises.
* **State-change events fire once per change, not once per poll** (1.9's rule).
  That gate belongs to the caller that knows what changed -- `account_health`
  already notifies only on a transition -- and is deliberately not
  second-guessed here. Where a caller has no such gate, it must not use an
  event named for a state.
"""

import enum
import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.services import slack

logger = logging.getLogger(__name__)


class Channel(str, enum.Enum):
    IN_APP = "in_app"
    EMAIL = "email"
    SLACK = "slack"


class Event(str, enum.Enum):
    """The events a workspace can route to Slack.

    Deliberately a closed set. A free-form event name would mean a typo in a
    toggle silently switches nothing on, which is the accept-and-drop failure
    the settings writer already had once.
    """

    POST_PUBLISHED = "post_published"
    POST_FAILED = "post_failed"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_COMPLETED = "approval_completed"
    ACCOUNT_HEALTH_CHANGED = "account_health_changed"
    REPORT_READY = "report_ready"


# The settings blob key holding the per-event toggles.
SETTINGS_KEY = "slack_events"

# Off unless asked for. A workspace that pastes a webhook to try the test
# button has not thereby consented to a message for every publish.
DEFAULTS: dict[str, bool] = {event.value: False for event in Event}

# Which channels carry an event at all. in_app and email are listed as the
# fact of the matter -- they are dispatched by the callers, not by this module.
_ALWAYS: dict[Event, tuple[Channel, ...]] = {
    Event.POST_PUBLISHED: (Channel.IN_APP,),
    Event.POST_FAILED: (Channel.IN_APP, Channel.EMAIL),
    Event.APPROVAL_REQUESTED: (Channel.IN_APP, Channel.EMAIL),
    Event.APPROVAL_COMPLETED: (Channel.IN_APP,),
    Event.ACCOUNT_HEALTH_CHANGED: (Channel.IN_APP, Channel.EMAIL),
    Event.REPORT_READY: (Channel.IN_APP, Channel.EMAIL),
}


def toggles_for(account: Account) -> dict[str, bool]:
    """This workspace's Slack toggles, defaulted and cleaned.

    An unknown key in the stored blob is ignored rather than trusted: the
    settings endpoint validates on write, but a blob written before an event
    existed should not resurrect as a surprise.
    """
    raw = (account.settings or {}).get(SETTINGS_KEY) or {}
    if not isinstance(raw, dict):
        return dict(DEFAULTS)
    return {
        event.value: bool(raw.get(event.value, DEFAULTS[event.value]))
        for event in Event
    }


def slack_enabled(account: Account, event: Event) -> bool:
    """Whether this event should reach Slack for this workspace.

    Both halves are required: a webhook that looks like Slack's, and the toggle
    for this specific event. A configured webhook is not blanket consent.
    """
    if not slack.is_valid_webhook(getattr(account, "slack_webhook_url", None)):
        return False
    return toggles_for(account).get(event.value, False)


def channels_for(account: Account, event: Event) -> list[Channel]:
    """Every channel this event reaches for this workspace.

    The matrix the tests assert against. in_app and email appear because they
    are true, not because this module sends them.
    """
    channels = list(_ALWAYS.get(event, ()))
    if slack_enabled(account, event):
        channels.append(Channel.SLACK)
    return channels


async def to_slack(
    db: AsyncSession,
    account: Account,
    event: Event,
    *,
    title: str,
    message: str,
    fields: Optional[dict[str, str]] = None,
    action_url: Optional[str] = None,
) -> bool:
    """Send one event to Slack, if this workspace wants it there.

    Returns whether a message was accepted. **Never raises** -- a publish, an
    approval or a report render must not fail because a chat integration did,
    which is the rule the email layer has followed since 0.7.
    """
    try:
        if not slack_enabled(account, event):
            return False
        payload = slack.build_blocks(
            title=title, message=message, fields=fields, action_url=action_url
        )
        return await slack.post(account.slack_webhook_url, payload)
    except Exception:  # noqa: BLE001 - the last line of defence for the caller
        logger.exception(
            "Slack notification for %s on workspace %s failed",
            event.value, getattr(account, "id", "?"),
        )
        return False


def validate_toggles(raw: Any) -> dict[str, bool]:
    """Validate a ``slack_events`` blob on the way in.

    Raises ``ValueError`` for anything that would read back wrong later -- an
    unknown event name, or a string where a bool belongs. ``bool("false")`` is
    True, so a workspace sending the string would have switched an event on
    while believing it had switched it off; that is the exact mistake the
    settings writer's isinstance check exists to catch.
    """
    if not isinstance(raw, dict):
        raise ValueError("settings.slack_events must be an object")

    known = {event.value for event in Event}
    for key, value in raw.items():
        if key not in known:
            raise ValueError(
                f"settings.slack_events.{key} is not an event. "
                f"Known events: {', '.join(sorted(known))}."
            )
        if not isinstance(value, bool):
            raise ValueError(f"settings.slack_events.{key} must be true or false")
    return {key: bool(value) for key, value in raw.items()}
