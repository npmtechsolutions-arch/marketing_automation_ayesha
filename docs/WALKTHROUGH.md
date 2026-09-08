# End-to-end walkthrough

The first time anyone drives this product as a user rather than as a reviewer.

Every prior verification went through the API directly, one endpoint at a time,
within the session that built it. That leaves two blind spots this is meant to
close: the **seams between sessions** (each step proved its own edge and assumed
its neighbours'), and the **frontend**, which has never been driven end to end by
anything but `npm run build` — while three of Phase 1's bugs were frontend-shaped.

## Rules

1. **Walk first, fix after.** Log every defect and keep going. One rabbit hole
   eats the session, and the point is coverage.
2. **Browser, not curl.** If you find yourself reaching for a terminal to make a
   step work, that is itself a defect — a user cannot do that.
3. **Two windows.** A normal window as the owner, a private/incognito window as
   the second role. Sessions are in-memory, so two windows really are two users.
4. Note anything that is merely *confusing* as well as broken. "I could not tell
   whether that saved" is a real finding.

## Environment

| | |
|---|---|
| Backend | http://127.0.0.1:8000 — logs at `/tmp/walkthrough-backend.log` |
| Frontend | http://localhost:5175 — logs at `/tmp/walkthrough-frontend.log` |
| Database | Postgres at `127.0.0.1:5433/marketing_automation` |
| Config | `.env` at the repo **root** (not `backend/`), gitignored |

Port 8000 is deliberate: `META_REDIRECT_URI` and `LINKEDIN_REDIRECT_URI` default
to `localhost:8000`, and an OAuth redirect URI must match the registered one
character for character.

### Before starting: real social credentials

Fill these into the root `.env` yourself. Do not paste them into the chat.

**Facebook Page** (via a test or personal Meta app):
```
META_APP_ID=
META_APP_SECRET=
META_CONFIG_ID=          # optional, only for Facebook Login for Business
META_REDIRECT_URI=http://localhost:8000/api/v1/facebook/callback
```

**LinkedIn** (needs a company page you administer):
```
LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=
LINKEDIN_REDIRECT_URI=http://localhost:8000/api/v1/linkedin/callback
```

In the provider's app settings, register the redirect URI **exactly** as above.
Then restart the backend so the new values load.

Both key names already exist in `.env` with empty values, so this is filling in
blanks rather than adding lines.

---

## The script

Tick as you go. Anything that fails gets a row in `docs/WALKTHROUGH-DEFECTS.md`
and you move on.

### 1. Registration and first run
- [ ] Register a brand-new organization at `/register`
- [ ] Landed somewhere sensible afterwards, not a blank page
- [ ] Onboarding (if any) can be completed *or* skipped without a dead end
- [ ] Workspace exists and is selected
- [ ] `subscription_events` got a `signup` row — the trend's baseline for this org

### 2. Email flows
Emails are suppressed in dev and logged instead. Watch for
`email suppressed (dev): to=… subject=…` in the backend log.
- [ ] Verification email logged on registration
- [ ] Trigger a password reset — email logged, link is well-formed
- [ ] The link's host matches `FRONTEND_URL` (`localhost:5175`), not a stale port

### 3. Connect a real social account  ← the part never tested before
- [ ] Start the connect flow from the UI
- [ ] Real provider consent screen appears
- [ ] Approve, and the callback returns to the app rather than an error page
- [ ] The account appears connected, with the right name and avatar
- [ ] Health reads **CONNECTED**, not UNKNOWN
- [ ] The stored token is encrypted at rest (spot-check the row)

This single connection exercises the OAuth handshake, the token exchange, and
`TOKEN_ENCRYPTION_KEY` — none of which mock tokens have ever touched.

### 4. Compose with variants
- [ ] Create a post with content and an image from the media library
- [ ] Upload a new image; it lands in S3 and previews
- [ ] Add a per-platform variant and change its text
- [ ] Exceed a platform's character limit deliberately — validation should refuse
      it *before* publish, not at publish time
- [ ] Save as draft, navigate away, come back — everything persisted

### 5. Approval chain (two windows)
- [ ] Enable approvals in workspace settings (this is the setting whose writer
      was silently dropping every change until `9c3b204`)
- [ ] Invite a second user to the workspace; accept in the private window
- [ ] Submit the post for review as the owner
- [ ] Second window sees it in the queue and can act
- [ ] Request changes → back to draft, with the comment visible
- [ ] Resubmit → approve → status lands correctly
- [ ] A CLIENT role sees only what it should

### 6. Schedule and publish for real
- [ ] Schedule the approved post ~5 minutes out
- [ ] It appears on the calendar at the right local time
- [ ] Wait. The worker picks it up without a nudge
- [ ] Job status moves queued → running → succeeded, visible in the UI
- [ ] **Open the real platform and confirm the post is actually there**
- [ ] The stored permalink opens the real post

### 7. Failure and retry
- [ ] Add a second target with a deliberately broken token
- [ ] Publish → `PARTIALLY_PUBLISHED`, with the platform's real error text
- [ ] `retryable` is set sensibly for that error
- [ ] Retry from the UI, and watch it re-run only the failed target
- [ ] Job logs are readable and say something useful

### 8. Health degradation
- [ ] Break the connection (revoke access from the provider's side)
- [ ] Next health sweep marks it FAILED with a real reason
- [ ] The dashboard health strip warns
- [ ] Admin → Connection Health lists it with org and workspace context
- [ ] Reconnect, and it returns to CONNECTED

### 9. Next morning — real analytics
- [ ] `analytics_daily` has a row for the real account, from the real API
- [ ] Only the metrics that platform actually reports are non-null
- [ ] Analytics → Overview / Platforms / Content / Audience all render
- [ ] CSV export downloads and opens in a spreadsheet
- [ ] Unreported metrics are blank cells, not `0` and not `None`

### 10. The agency screenshot
- [ ] Produce the dashboard view an agency would actually send a client
- [ ] Judge it as a customer: is it worth the subscription price?
- [ ] Note what is missing — this is the input to Phase 2 ordering

---

## After the walk

Triage `WALKTHROUGH-DEFECTS.md` by severity, fix in priority order, and let what
actually broke — not the scope document's numbering — decide which Phase 2
prompt runs first.
