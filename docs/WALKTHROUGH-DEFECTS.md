# Walkthrough defect log

Filled in as the walkthrough runs. **Nothing here gets fixed during the walk** —
log it, move on, triage at the end.

Severity:
- **S1** blocks a user completely, or loses/corrupts data
- **S2** a core path works but is wrong, or needs a workaround a user would not find
- **S3** confusing, ugly, or slow, but completable
- **S4** polish

| # | Step | Severity | What happened | Expected | Notes |
|---|------|----------|---------------|----------|-------|
| 2 | 1 (registration) | **S1** | `POST /auth/refresh` returned **422** for every browser session, so the access token could never be renewed. Navigating away from the page you registered on, or reloading any page, bounced you to `/login`. The app was unusable past the first SPA route. | A session survives a reload. | **FIXED.** The seam: the endpoint takes `TokenRefresh \| None = Body(None)` and reads the httpOnly cookie — correct. The frontend posts `{}` — also reasonable. But `Body(None)` makes an *absent* body optional, not a present-but-empty one, so FastAPI validated `{}` against the model and 422'd on the required `refresh_token` before the cookie was ever read. `refresh_token` is now optional, which `_read_refresh_token` already anticipated. Two regression tests in `test_auth.py`. Found by clicking; no per-step review could see it, because each half is right on its own. |
| 3 | 1 (registration) | **S1** | The "I agree to the terms" control is a `<div onClick>` with `tabIndex: -1`, no `role`, and no keyboard handler. **A keyboard-only user cannot register at all** — they can fill every field, cannot reach the checkbox, and the form refuses to submit with "You must agree to the terms". | The control is focusable and toggles on Space/Enter. | Not fixed. Should be a real `<input type="checkbox">`, or at minimum `role="checkbox"` + `tabIndex={0}` + key handler. |
| 4 | 1 (registration) | S2 | The same control sits inside a `<label>` with no `htmlFor` and no input, so **clicking the label text does nothing**. Only the 16×16px box works. | Clicking anywhere on "I agree to the…" toggles it. | Not fixed. Falls out of the same fix as #3. |
| 5 | 2 (email) | S3 | `POST /auth/refresh` fires on the **public landing page** for anonymous visitors, producing a failed request and a console error on every first visit. | No auth call before there is a session to refresh. | Not fixed. Harmless but noisy, and it trained me to ignore a console error that later turned out to be #2. |
| 6 | 3 (workspace) | S3 | The person who registered and owns the workspace is labelled **"Member"** in the sidebar. `GET /accounts/` returns `role: null` for an owner (they have no `TeamMember` row — they are `owner_id`), and the UI falls back to "Member". | "Owner". | Not fixed. Either return a synthetic `owner` role or have the UI check `owner_id`. |
| ~~1~~ **FIXED** | 6 (schedule) | S2 | The composer's manual schedule builds `new Date("2026-03-09T10:00")`, which parses in the **browser's** timezone, then sends `.toISOString()`. An agency in London scheduling for a Sydney workspace sets a time eleven hours out, and the error changes by an hour when either side's clocks move. | The time entered should mean that time on the *workspace's* clock, as it does for queue slots and recurring schedules. | Found while building scope §9's remainder, not by the walkthrough. "Add to queue" and "Repeat" avoid it — the server resolves those. Fixed: `/schedule` now takes `scheduled_at_local` (a workspace wall-clock reading) or `scheduled_at` (an instant that must carry an offset); a naive `scheduled_at` is refused rather than assumed UTC. The read path was wrong the same way — a post set for 10:00 Sydney rendered as 23:00 to a London viewer, and saving that form wrote 23:00 Sydney — so both directions were fixed. `tests/test_post_contract.py`. |

## Walk A — coverage note

Driven in a real Chromium via Playwright (browsers were already cached on this
machine; `playwright-core` is installed in the scratchpad, not the repo).

**Covered:** registration, session persistence across reload, and a sweep of all
thirteen authenticated routes — every one renders with no console error, no
failed request and no unexpected redirect. Account connection and health state.
The composer through step 2.

**Not covered, and still open:** the invite link from the suppressed-email log,
the approval chain across two windows, schedule-and-watch-it-publish, and the
break-a-target retry path. Automating the four-step composer wizard turned into
selector archaeology, which is the rabbit hole this document's own rules say to
step out of. Those steps are better done by hand — and are now *possible* by
hand, which they were not before #2 was fixed.

**A caution about my own method:** the route sweep initially reported
`/content/create` as "ok" because I only flagged pages under 40 characters, and
the 404 page is 82. It was a 404 the whole time. A check that can pass while the
thing it checks is broken is not a check.

## Found while building, not by the walk

| # | Area | Severity | What happens |
|---|------|----------|--------------|
| 7 | `POST /ai/generate-content` | S2 | A provider failure is caught, mock text is substituted with the raw exception interpolated into it (`⚠️ … Error: {exc}`), and the `AIGeneration` row is recorded **COMPLETED**. So an internal error string can land in the user's post, and the usage log cannot answer "how often does this break". The newer `/ai/rewrite` family does the opposite — FAILED row, 502, text untouched — and `generate-content` should be brought into line. Not changed here because its response contract is what the composer's generate flow depends on. |
| 8 | Composer character counter | S3 | The counter is hardcoded `/ 2,200` for every platform, so someone targeting X is told 2,200 is fine and finds out at publish time. Already noted in the `Capabilities` docstring; the AI assists route around it by asking the connector for the real limit. |

## Observations that are not defects

Things worth remembering that are not bugs — friction, missing features, ideas
for Phase 2 ordering.

- Reusing a saved browser `storageState` across runs got the session revoked
  with "This session has been revoked. Please sign in again." That is the
  refresh-token rotation guard working exactly as designed — a superseded token
  presented twice means two parties hold it — not a defect. Each script logs in
  fresh.
- A newly connected account shows `health: unknown` until the hourly sweep runs.
  Correct by design (UNKNOWN is deliberately distinct from CONNECTED so an
  unswept account does not read as a clean bill of health), but a user who has
  just connected an account and sees "unknown" has no way to know that.
- The public landing page carries an invented testimonial ("Sarah Chen,
  Marketing Director, TechFlow — engagement jumped 300%"). Marketing copy is a
  business decision rather than a bug, but it is the same shape as the
  fabricated data removed from the admin dashboard, and worth a deliberate
  decision rather than an inherited default.
- ~~`POST /posts/` takes `target_account_ids`, but the response returns
  `target_accounts`.~~ **Fixed.** Post writes now refuse unknown fields with a
  422 naming the key, and accept `target_accounts` as an alias so
  read-modify-write works against the API's own response.
