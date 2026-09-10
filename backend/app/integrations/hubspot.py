"""HubSpot.

The only concrete provider in v1, chosen for the same reason Slack was chosen
over WhatsApp: it can be proven end to end today. HubSpot gives out free
developer accounts with a test portal, its OAuth is public, and the scopes v1
needs carry no review gate.

Contact identity
----------------

**HubSpot dedupes on email, server-side, and we do not have one.** A social
inbox knows a handle and a platform; it does not know an email address, and
inventing one to make the dedupe work would be fabricating customer data.

So this provider searches before it writes, on a property it owns:
``social_handle`` holding ``platform:handle`` -- a value that *is* unique for a
person on a platform, unlike a display name. That makes "Send to CRM" twice on
one thread an update rather than a duplicate, which is the idempotency the
prompt asks for and the behaviour a user assumes.

The alternative -- letting HubSpot dedupe -- would need an email, and asking a
user to type one to file a Twitter conversation is asking them to guess.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.integrations.base import (
    ContactIdentity,
    ContactRef,
    CrmAPIError,
    CrmAuthExpired,
    CrmCapabilities,
    NotImplementedInV1,
    OAuthTokens,
    SocialContact,
)

logger = logging.getLogger(__name__)

AUTH_URL = "https://app.hubspot.com/oauth/authorize"
TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"
API = "https://api.hubapi.com"

# The least that lets v1 work. Neither needs HubSpot app review.
SCOPES = "crm.objects.contacts.read crm.objects.contacts.write"

TIMEOUT = 20.0

# The custom property this integration owns, holding "platform:handle".
HANDLE_PROPERTY = "social_handle"


class HubSpotProvider:
    slug = "hubspot"
    name = "HubSpot"

    capabilities = CrmCapabilities(
        supports_contact_upsert=True,
        # Everything below is out of v1 and each is its own future prompt.
        supports_contact_read=False,
        supports_deals=False,
        supports_attribution=False,
        identity=ContactIdentity.SEARCH_THEN_WRITE,
        writable_properties=(
            "firstname", "lastname", HANDLE_PROPERTY,
            "hs_lead_status", "website",
        ),
        max_property_length=65536,
    )

    # -- configuration ----------------------------------------------------

    def is_configured(self) -> bool:
        return bool(
            getattr(settings, "HUBSPOT_CLIENT_ID", "")
            and getattr(settings, "HUBSPOT_CLIENT_SECRET", "")
        )

    @property
    def redirect_uri(self) -> str:
        return getattr(settings, "HUBSPOT_REDIRECT_URI", "")

    def authorize_url(self, state: str) -> str:
        return f"{AUTH_URL}?" + urlencode({
            "client_id": settings.HUBSPOT_CLIENT_ID,
            "redirect_uri": self.redirect_uri,
            "scope": SCOPES,
            "state": state,
        })

    # -- OAuth ------------------------------------------------------------

    async def _token_request(self, form: dict[str, str]) -> OAuthTokens:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(TOKEN_URL, data=form)

        if response.status_code >= 400:
            detail = _error_detail(response)
            # A bad refresh token is not a transient failure; retrying it
            # forever is how an integration stays broken silently.
            if response.status_code in (400, 401):
                raise CrmAuthExpired(
                    f"HubSpot rejected the credentials: {detail}"
                )
            raise CrmAPIError(self.slug, detail, response.status_code)

        payload = response.json()
        expires_in = payload.get("expires_in")
        return OAuthTokens(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token"),
            expires_at=(
                datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
                if expires_in
                else None
            ),
        )

    async def exchange_code(self, code: str) -> OAuthTokens:
        tokens = await self._token_request({
            "grant_type": "authorization_code",
            "client_id": settings.HUBSPOT_CLIENT_ID,
            "client_secret": settings.HUBSPOT_CLIENT_SECRET,
            "redirect_uri": self.redirect_uri,
            "code": code,
        })
        # Which portal this is, so settings can name it rather than showing a
        # bare "connected" that a user with three portals cannot act on.
        return await self._label(tokens)

    async def refresh(self, refresh_token: str) -> OAuthTokens:
        return await self._token_request({
            "grant_type": "refresh_token",
            "client_id": settings.HUBSPOT_CLIENT_ID,
            "client_secret": settings.HUBSPOT_CLIENT_SECRET,
            "refresh_token": refresh_token,
        })

    async def _label(self, tokens: OAuthTokens) -> OAuthTokens:
        """Attach the portal id and name, best effort.

        A failure here loses a label, not a connection, so it must not fail the
        exchange -- the tokens are already valid at this point.
        """
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.get(
                    f"{API}/oauth/v1/access-tokens/{tokens.access_token}"
                )
            if response.status_code == 200:
                info = response.json()
                return OAuthTokens(
                    access_token=tokens.access_token,
                    refresh_token=tokens.refresh_token,
                    expires_at=tokens.expires_at,
                    external_account_id=str(info.get("hub_id") or "") or None,
                    external_account_name=(
                        info.get("hub_domain") or info.get("user") or None
                    ),
                )
        except Exception:  # noqa: BLE001 - a label is not worth a failed connect
            logger.warning("Could not read HubSpot token metadata", exc_info=True)
        return tokens

    async def revoke(self, tokens: Any) -> bool:
        """HubSpot revokes a *refresh* token; access tokens simply expire.

        Returns whether the provider confirmed it. The caller clears its own
        copy either way -- a disconnect that leaves the row behind because the
        vendor was unreachable is a disconnect that did not happen.
        """
        refresh_token = getattr(tokens, "refresh_token", None)
        if not refresh_token:
            return False
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.delete(
                    f"{API}/oauth/v1/refresh-tokens/{refresh_token}"
                )
            return response.status_code in (200, 204)
        except Exception:  # noqa: BLE001
            logger.warning("HubSpot revoke failed", exc_info=True)
            return False

    # -- the one v1 capability -------------------------------------------

    async def upsert_contact(
        self, tokens: Any, contact: SocialContact
    ) -> ContactRef:
        """Create or update the contact for this social identity.

        Search-then-write on ``social_handle``. See the module docstring for
        why this rather than HubSpot's own email dedupe.
        """
        access_token = getattr(tokens, "access_token", None) or str(tokens)
        headers = {"Authorization": f"Bearer {access_token}"}
        key = f"{contact.platform}:{contact.handle}".lower()

        properties = _properties_for(contact, key)

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            existing_id = await self._find(client, headers, key)
            if existing_id:
                response = await client.patch(
                    f"{API}/crm/v3/objects/contacts/{existing_id}",
                    headers=headers, json={"properties": properties},
                )
                created = False
            else:
                response = await client.post(
                    f"{API}/crm/v3/objects/contacts",
                    headers=headers, json={"properties": properties},
                )
                created = True

        if response.status_code == 401:
            raise CrmAuthExpired("HubSpot rejected the access token.")
        if response.status_code >= 400:
            raise CrmAPIError(
                self.slug, _error_detail(response), response.status_code
            )

        body = response.json()
        contact_id = str(body.get("id") or existing_id or "")
        return ContactRef(
            provider_id=contact_id,
            created=created,
            url=(
                f"https://app.hubspot.com/contacts/{_portal(tokens)}/contact/{contact_id}"
                if contact_id and _portal(tokens)
                else None
            ),
        )

    async def _find(self, client, headers, key: str) -> Optional[str]:
        """The id of the contact carrying this social handle, if any."""
        response = await client.post(
            f"{API}/crm/v3/objects/contacts/search",
            headers=headers,
            json={
                "filterGroups": [{
                    "filters": [{
                        "propertyName": HANDLE_PROPERTY,
                        "operator": "EQ",
                        "value": key,
                    }]
                }],
                "properties": [HANDLE_PROPERTY],
                "limit": 1,
            },
        )
        if response.status_code == 401:
            raise CrmAuthExpired("HubSpot rejected the access token.")
        if response.status_code >= 400:
            # A search that errors must not silently become "no match", which
            # would turn every send into a new duplicate contact.
            raise CrmAPIError(
                self.slug,
                f"Contact lookup failed: {_error_detail(response)}",
                response.status_code,
            )
        results = (response.json() or {}).get("results") or []
        return str(results[0]["id"]) if results else None

    # -- refusals ---------------------------------------------------------

    async def list_contacts(self, *args, **kwargs):
        raise NotImplementedInV1(self.slug, "Reading contacts back")

    async def create_deal(self, *args, **kwargs):
        raise NotImplementedInV1(self.slug, "Creating deals")


def _properties_for(contact: SocialContact, key: str) -> dict[str, str]:
    """Only what we actually know.

    A display name is split into first/last **only when it clearly has two
    parts**; guessing a surname from a single word is inventing a person's
    name into a CRM someone will later address them by.
    """
    properties: dict[str, str] = {HANDLE_PROPERTY: key}

    name = (contact.display_name or "").strip()
    if name:
        parts = name.split()
        if len(parts) >= 2:
            properties["firstname"] = parts[0]
            properties["lastname"] = " ".join(parts[1:])
        else:
            properties["firstname"] = parts[0]

    if contact.email:
        properties["email"] = contact.email
    if contact.conversation_url:
        properties["website"] = contact.conversation_url
    return properties


def _portal(tokens: Any) -> Optional[str]:
    return getattr(tokens, "external_account_id", None)


def _error_detail(response: httpx.Response) -> str:
    """HubSpot's own message where it gives one.

    A generic "sync failed" teaches a user nothing; "property social_handle
    does not exist" tells them exactly what to do.
    """
    try:
        body = response.json()
    except Exception:  # noqa: BLE001
        return (response.text or "")[:300] or f"HTTP {response.status_code}"
    return str(
        body.get("message") or body.get("error_description") or body
    )[:300]
