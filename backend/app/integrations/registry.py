"""Which CRM providers exist.

One entry in v1. The registry exists anyway so adding Salesforce is a new file
and a line here rather than a rewrite -- the same reason the platform connector
registry exists.
"""

from typing import Iterable

from app.integrations.base import CrmProvider
from app.integrations.hubspot import HubSpotProvider

_PROVIDERS: dict[str, CrmProvider] = {
    HubSpotProvider.slug: HubSpotProvider(),
}


class UnknownProvider(KeyError):
    """A slug nothing implements.

    Raised rather than returning None so a typo in a URL is a 404 with a
    message, not an AttributeError three frames later.

    ``__str__`` is overridden because ``KeyError`` renders its argument with
    ``repr()``, so the message reached the user wrapped in escaped quotes --
    ``"\"'salesforce' is not a CRM...\""``. A detail string a person reads
    should not carry the punctuation of the exception type that carried it.
    """

    def __str__(self) -> str:
        return self.args[0] if self.args else ""


def get_provider(slug: str | None) -> CrmProvider:
    provider = _PROVIDERS.get((slug or "").lower())
    if provider is None:
        raise UnknownProvider(
            f"'{slug}' is not a CRM this product integrates with. "
            f"Available: {', '.join(sorted(_PROVIDERS)) or 'none'}."
        )
    return provider


def known_slugs() -> Iterable[str]:
    return tuple(sorted(_PROVIDERS))
