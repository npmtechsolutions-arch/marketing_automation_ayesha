# HubSpot — setup, and what this integration is

The code half of the CRM integration is done and tested. The live half needs a
HubSpot developer portal, which needs a person: an account, accepted developer
terms, and a test portal created from their dashboard. Same shape as Walk B's
dev apps and, before that, the Slack webhook.

Everything below should be paste-and-click.

---

## What v1 does, exactly

**One thing: "Send to CRM" on an inbox conversation creates or updates a HubSpot
contact.** The contact carries the social handle, the platform, and a link back
to the conversation.

Explicitly **not** in v1, each its own future piece of work — stated here and in
`app/integrations/base.py` so nobody has to read the code to find the edges:

| Out of v1 | Why it is its own job |
|---|---|
| Reading contacts back | Needs a sync model, conflict rules, and a decision about which system owns a field. |
| Revenue attribution | Needs the deal pipeline below, plus a durable link from conversation to contact to deal. |
| Creating deals | Writing into someone's revenue pipeline is a different order of trust from adding a contact. |
| Salesforce | Needs a Connected App, a security-token flow, and per-org admin approval that a self-serve signup cannot complete — so it cannot be proven end to end the way HubSpot's free portal can. When it is built it is a second provider behind the same base, not a rewrite. |

The settings screen shows these as `not yet:` badges rather than hiding them,
because a reader should be able to see what an integration does not do without
opening the source.

---

## Setup — the part that needs you

### 1. Create a developer account and a test portal

<https://developers.hubspot.com/> → sign up → **Create a test account** from
the dashboard. Free, no review, no card.

### 2. Create a public app

In the developer account: **Apps → Create app**. Under **Auth**:

- **Redirect URL** — must match exactly:
  ```
  http://localhost:8000/api/v1/integrations/hubspot/callback
  ```
- **Scopes** — exactly these two. Neither needs app review:
  ```
  crm.objects.contacts.read
  crm.objects.contacts.write
  ```

Check nothing else holds port 8000 first — another project on this machine has
taken it twice:

```
lsof -nP -iTCP:8000 -sTCP:LISTEN
```

To use a different port, set `HUBSPOT_REDIRECT_URI` **and** register that exact
URL.

### 3. Create the custom property the dedupe keys on

In the **test portal** (not the developer account): Settings → Properties →
Create property, on the **Contact** object.

- Label: `Social handle`
- **Internal name: `social_handle`** — this exact string
- Type: single-line text

**Why this exists.** HubSpot dedupes contacts on email, server-side. A social
inbox does not have an email address, and inventing one to make the dedupe work
would be fabricating customer data. So the provider searches on
`social_handle` holding `platform:handle` — a value that genuinely is unique for
a person on a platform — before deciding whether to create or update. Without
the property, the search errors and the send is refused rather than quietly
creating a duplicate every time.

### 4. Credentials into `.env`

Do not paste them into the chat.

```dotenv
HUBSPOT_CLIENT_ID=
HUBSPOT_CLIENT_SECRET=
HUBSPOT_REDIRECT_URI=http://localhost:8000/api/v1/integrations/hubspot/callback
```

---

## The live pass, once that exists

1. **Settings → Integrations** shows HubSpot as *available* rather than "not
   configured on this deployment".
2. **Connect** → the real HubSpot consent screen → back to Settings, showing the
   portal name and who connected it.
3. Confirm the token is encrypted at rest:
   ```sql
   SELECT access_token FROM crm_connections;
   ```
   It must not look like a HubSpot token. (The suite proves this on a fixture;
   this proves it on a real one.)
4. **Inbox → a conversation → Send to CRM.** Expect "created".
5. Open the contact in HubSpot. It should carry the handle, the platform, and
   the conversation link — **and no invented email or surname.** A single-word
   display name must not have acquired a last name.
6. **Send the same thread again.** Expect "updated", and **one** contact in
   HubSpot, not two. This is the whole point of the search-then-write design.
7. **Disconnect.** The row goes; confirm HubSpot shows the app as no longer
   authorised.
8. Break it: revoke the app from inside HubSpot, then send again. Expect a
   visible error asking you to **reconnect** — not "try again", which is the
   wrong instruction for a dead credential — and the conversation untouched.

---

## Verified without a portal

- Every HTTP path, against `httpx.MockTransport`: OAuth exchange, refresh,
  search, create, update, revoke.
- Token encryption, by reading the raw column.
- Idempotency: two sends, one contact. Reverting the search-first design fails
  three tests.
- A failed lookup raises rather than reading as "no match" — without that, every
  send during a HubSpot incident would make a duplicate person.
- Organization isolation: one org's connection is invisible to another, and a
  cross-org disconnect is refused.
- Permission: a viewer can read a thread and cannot send it.
- Failure isolation: a HubSpot 500 surfaces as a 502 on that action and leaves
  the thread exactly as it was.

Live, on this deployment with no credentials: the integrations list reports
`configured: false`, `authorize` refuses with a readable reason, and an unknown
provider 404s naming what is available.
