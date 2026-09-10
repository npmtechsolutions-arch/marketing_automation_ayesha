"""What a CRM provider is, and what it is allowed to not do.

The shape follows :mod:`app.connectors.base` on purpose. That module's rules
were learned the hard way and none of them are cheaper here:

* **Refusal is a first-class answer.** ``NotSupportedError`` means "this CRM has
  no API for that", which a caller should stop asking about rather than retry.
  It is distinct from "we have not built it yet" -- see ``NotImplementedInV1``.
* **Nothing is invented.** A provider that cannot read a contact returns
  nothing; it does not synthesise one. A CRM record that looks real and is not
  is worse than a missing one, because someone will email it.
* **Tokens are encrypted at rest** and never returned by an API.

What v1 is
----------

**Outbound only, to HubSpot.** One capability: push a social conversation to a
contact. That is it.

Explicitly **out of v1**, each its own future piece of work:

``contact_sync_in``
    Reading contacts back from the CRM into this product. Needs a sync model,
    conflict rules, and a decision about which system owns a field.

``attribution``
    Tying a deal to the post that sourced it. Needs the deal pipeline below
    plus a durable link from conversation to contact to deal.

``deals``
    Creating or moving pipeline records. Writing into someone's revenue
    pipeline is a different order of trust from adding a contact, and deserves
    its own review.

``salesforce``
    Out. It requires a Connected App, a security-token flow, and per-org
    admin approval that a self-serve signup cannot complete -- so it cannot be
    proven end to end the way HubSpot's free developer portal can. When it is
    built it will be a second provider behind this same base, not a rewrite.
"""

import enum
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Protocol


class NotSupportedError(NotImplementedError):
    """This CRM has no API for the capability.

    A caller should stop asking. Kept distinct from :class:`NotImplementedInV1`
    because "the vendor cannot" and "we have not yet" lead to different
    decisions, and collapsing them is how a roadmap item becomes a permanent
    excuse.
    """

    def __init__(self, slug: str, capability: str) -> None:
        super().__init__(f"{slug} does not support {capability}")
        self.slug = slug
        self.capability = capability


class NotImplementedInV1(NotImplementedError):
    """The CRM supports it; this product does not yet.

    Named so the message a user sees can say which it is. "HubSpot cannot do
    that" and "we have not built that" are different sentences and only one of
    them is worth waiting for.
    """

    def __init__(self, slug: str, capability: str) -> None:
        super().__init__(
            f"{capability} is not part of this integration yet ({slug})."
        )
        self.slug = slug
        self.capability = capability


class CrmNotConnected(Exception):
    """No CRM connection for this organization."""


class CrmAuthExpired(Exception):
    """The stored credentials no longer work and a reconnect is needed.

    Distinct from a transient failure: retrying will not help, and the honest
    UI response is "reconnect", not "try again".
    """


class CrmAPIError(Exception):
    """The CRM answered with an error.

    Carries the provider's own message where there is one. A generic "sync
    failed" teaches a user nothing and gets logged, ignored, and rediscovered
    a month later.
    """

    def __init__(self, slug: str, detail: str, status_code: Optional[int] = None):
        super().__init__(detail)
        self.slug = slug
        self.detail = detail
        self.status_code = status_code


class ContactIdentity(str, enum.Enum):
    """How a provider decides two records are the same person.

    Recorded per provider rather than assumed, because the answer decides
    whether a second "Send to CRM" updates a contact or creates a duplicate,
    and the two providers this design anticipates answer differently.
    """

    #: The CRM dedupes server-side on a natural key it owns (HubSpot: email).
    PROVIDER_DEDUPES = "provider_dedupes"
    #: We must search first and decide, because the CRM will happily duplicate.
    SEARCH_THEN_WRITE = "search_then_write"


@dataclass(frozen=True)
class CrmCapabilities:
    """What this provider will accept.

    ``None`` for a limit means "no limit", the same convention the platform
    connectors use -- a 0 or -1 sentinel is the ambiguity the entitlement work
    removed.
    """

    #: v1's only capability.
    supports_contact_upsert: bool = False
    #: Everything below is False in v1 and documented in the module docstring.
    supports_contact_read: bool = False
    supports_deals: bool = False
    supports_attribution: bool = False

    identity: ContactIdentity = ContactIdentity.SEARCH_THEN_WRITE
    #: Properties the provider will accept on a contact write.
    writable_properties: tuple[str, ...] = ()
    max_property_length: Optional[int] = None


@dataclass(frozen=True)
class OAuthTokens:
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    #: The CRM's own identifier for the connected account, for display.
    external_account_id: Optional[str] = None
    external_account_name: Optional[str] = None


@dataclass(frozen=True)
class ContactRef:
    """A contact as it exists in the CRM after a write.

    ``created`` distinguishes an insert from an update so the UI can say which
    happened. A user who presses "Send to CRM" twice should be told the second
    press updated the same person, not left wondering whether they made two.
    """

    provider_id: str
    created: bool
    url: Optional[str] = None


@dataclass(frozen=True)
class SocialContact:
    """What this product knows about the person in a conversation.

    Deliberately thin, and every field optional except the handle. This is the
    honest extent of what a social inbox knows: a handle, which platform it is
    on, and a link back. Inferring a name, a company or an email from that
    would be inventing customer data, which is the failure this project has
    spent whole sessions removing.
    """

    handle: str
    platform: str
    display_name: Optional[str] = None
    conversation_url: Optional[str] = None
    email: Optional[str] = None
    note: Optional[str] = None


class CrmProvider(Protocol):
    """The interface a CRM integration implements."""

    slug: str
    name: str
    capabilities: CrmCapabilities

    def is_configured(self) -> bool:
        """Whether this deployment has app credentials for the provider."""
        ...

    def authorize_url(self, state: str) -> str:
        ...

    async def exchange_code(self, code: str) -> OAuthTokens:
        ...

    async def refresh(self, refresh_token: str) -> OAuthTokens:
        ...

    async def revoke(self, tokens: Any) -> bool:
        """Best effort. A provider with no revoke endpoint returns False rather
        than pretending, and the caller still clears its own copy."""
        ...

    async def upsert_contact(
        self, tokens: Any, contact: SocialContact
    ) -> ContactRef:
        ...


__all__ = [
    "ContactIdentity",
    "ContactRef",
    "CrmAPIError",
    "CrmAuthExpired",
    "CrmCapabilities",
    "CrmNotConnected",
    "CrmProvider",
    "NotImplementedInV1",
    "NotSupportedError",
    "OAuthTokens",
    "SocialContact",
]
