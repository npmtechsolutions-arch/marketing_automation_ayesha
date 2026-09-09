# Walkthrough defect log

Filled in as the walkthrough runs. **Nothing here gets fixed during the walk** —
log it, move on, triage at the end.

Severity:
- **S1** blocks a user completely, or loses/corrupts data
- **S2** a core path works but is wrong, or needs a workaround a user would not find
- **S3** confusing, ugly, or slow, but completable
- **S4** polish

---

## Open

**Nothing.** Every defect Walk A found is fixed; the table below records what
each one was. Walk B -- the same walk against real platform credentials -- is
the remaining unproven layer.

---

## Fixed in this triage pass

| # | Sev | What it was | Fix |
|---|-----|-------------|-----|
| 1 | S2 | The composer's manual schedule built `new Date("...")` in the **browser's** timezone, then sent `.toISOString()`. The read path was wrong the same way. | `/schedule` now takes `scheduled_at_local` (a workspace wall-clock reading) or `scheduled_at` (an instant that must carry an offset); a naive `scheduled_at` is refused rather than assumed UTC. `tests/test_post_contract.py`. |
| 2 | **S1** | `POST /auth/refresh` returned **422** for every browser session, so no access token could ever be renewed and any reload bounced you to `/login`. `Body(None)` makes an *absent* body optional, not a present-but-empty one, so FastAPI validated the frontend's `{}` against the model and 422'd on the required `refresh_token` before the cookie was read. | `refresh_token` made optional, which `_read_refresh_token` already anticipated. Two regression tests in `test_auth.py`. |
| 3 | **S1** | The "I agree to the terms" control was a `<div onClick>` with `tabIndex: -1` and no key handler — **a keyboard-only user could not register at all**. | A real `<input type="checkbox">`, visually hidden with `peer sr-only`, inside a `<label htmlFor>`; focus ring driven by `peer-focus-visible`. Verified live by tabbing to it and pressing Space. |
| 4 | S2 | The same control's `<label>` had no `htmlFor` and no input, so clicking the label text did nothing. | Fell out of #3. Verified live. |
| 5 | S3 | `/auth/refresh` fired for anonymous visitors on the landing page. | A `has_session` marker in `localStorage`; bootstrap early-returns when it is absent. The marker is written by a store **subscription** on `isAuthenticated`, not by hand in `setSession()` — `login` and `register` call `set()` directly and bypassed it, which is a regression I introduced and caught only in the browser. Verified live: landing page is silent. |
| 6 | S3 | The workspace owner was labelled **"Member"** in the sidebar. | `AccountResponse` gained `role`; `list_accounts` resolves it from `TeamMember` in one query. The `owner_id` branch I first wrote was unreachable — owners *do* have `TeamMember` rows and the endpoint filters on membership — so it was removed. Verified live for an owner ("owner") and for an invited editor ("editor"). |
| 7 | S2 | `POST /ai/generate-content` swallowed provider failures, interpolated the raw exception into mock post text, and recorded the row **COMPLETED**. | Now sets `FAILED`, records `error_message`, and raises a 502 saying nothing was generated. Brought into line with the `/ai/rewrite` family. |
| 8 | S3 | The composer's character counter was hardcoded `/ 2,200` for every platform. | Derived from the target platform's real limit. Verified live: `0 / 63,206 · facebook`, and with X also selected it tightened to `44 / 280 · twitter`. |
| 9 | **S1** | **LinkedIn and X reported randomly generated engagement as real data.** Both connectors' `get_post_metrics` returned `mock_metrics_fallback(...)` unconditionally -- not gated on a dev token, not on `DEBUG`. Their own docstrings said "Returns fabricated numbers." | Both now raise `NotSupportedError`, the base class's own default, so no performance row is written and an absent row reads as "not measured". The audit found **two more fabrication sites, both worse**, because they only fire in production when something is already wrong: every connector's `except Exception` in the metrics fetch logged *"falling back to mock"* and returned random integers, so an expired token or a provider outage produced plausible engagement that hid the failure; and `is_mock_token()` matches any token merely *containing* "test" and returns True for an empty one, so the "development placeholder" paths were reachable with live credentials or a token that failed to decrypt. All four are gone, `random` is no longer imported anywhere in `app/connectors/`, and a structural test fails if it returns. Migration `b8d3aa61c94f` deletes the stored fabrications for X and LinkedIn -- unambiguous, since neither ever had a real fetch (7 rows here). The three platforms with a real fetch are left alone: their rows mix measurement and invention with nothing to separate them, and deleting real data to be rid of invented data is its own loss. The calendar no longer coalesces an absent measurement to `0`, which would read as "nobody engaged"; it says the platform does not expose per-post metrics. |
| 10 | **S1** | The workspace switcher was empty for **everyone, always**: `itemsOf` had no branch for `Array.isArray(response.data)`, which is exactly the shape `/organizations/` returns through the raw axios instance, so `organizations` was always `[]`. | Branch added. And the switcher no longer depends on it: it is now driven by `workspaces`, which is the authoritative list, with organizations used only to label the groups. The list a person can act on must not be filtered by a list that is merely decorative. |
| 11 | **S1** | Stacked behind #10: a workspace joined by invitation had no organization row to group under, so it stayed invisible even with `itemsOf` fixed. | The cause was narrower than first logged: `/organizations/` returns orgs you are an accepted *organization* member of, which is correct -- accepting a *workspace* invitation deliberately does not make you one. Widening it would have listed organizations whose every endpoint then 403s. Instead `/accounts/` now sends `organization_name`, so the switcher can group by company without the caller being an org member. A name is not access; `/organizations/{id}` still refuses them. |
| 12 | S2 | **Logged as "there is no Copy Invitation Link button" -- that was wrong, and the severity with it.** The button does exist, in the invite dialog's success state; the walk's selector looked for `input/textarea/code/a` and the link is a `<p>`, so it was missed. What was true: dismiss that dialog and the link is unrecoverable -- the pending row offered only "Cancel" and the token appeared nowhere else. Combined with the broken emailed link (fixed separately), an invitation whose dialog had been closed could not be delivered at all. | A "Copy Invitation Link" button on every pending row. `invitation_token` is now sent only to callers holding `team.manage` -- the permission needed to issue an invitation -- rather than to every role with `team.view`. A narrowing rather than a hole closed: `accept-invite` already checks the invitation email against the caller's own. The panel's note claimed *"No automatic email is sent"*, which was false, and now says email is sent but not guaranteed. |
| 13 | S2 | The team page hardcoded `const planLimit = 10` and the literal `"Growth Plan"`, so a new Free workspace was told **"1 of 10 team members used · Growth Plan"** and refused on the very next click with *"your Free plan's limit for team members (1)"*. | Both read from `GET /accounts/{id}/settings/`, which resolves them from `plan_features` -- the table enforcement itself reads, so the meter and the refusal cannot disagree. A pending invitation counts toward the meter because it counts toward the limit. `null` renders as unlimited with no progress bar rather than as zero seats. Contract test asserts the number the endpoint reports is the number the invite endpoint enforces, *and* that the refusal names it; a structural test fails if a plan literal reappears. |
| 14 | S2 | `mapStatus` narrowed twelve backend statuses to five and fell through to `"draft"`, so `approved`, `in_review` and `changes_requested` all rendered as **Draft**, sat in the Drafts filter, and opened the draft action gate. | Nothing was missing from the type -- `ReviewStatus` already listed all twelve -- so the fix was to stop discarding them. Now in `lib/postStatus.ts`, with buckets for counting and filtering, and an "In review" chip so those posts are countable instead of miscounted. A backend contract test fails if `PostStatus` gains a member the UI does not know. |
| 15 | S2 | `partially_published` mapped to `published`, so a post that **failed on one of two platforms** got a green "Published" pill and a success count while the panel below showed the failure in red. | Its own bucket and its own "Partly published" chip -- it is neither a success nor a failure, and folding it into either hides what happened. `isFullyPublished()` is deliberately false for it. The drawer badge now uses the shared `statusMeta` label, so the header and the review row cannot disagree (it briefly read "Partially_published" while they did). |
| 16 | S2 | The schedule fields were **prefilled from the browser's clock** while the note beneath them said *"Times are on the workspace's clock, not your computer's."* Defect #1 fixed how they are parsed and rendered; nobody looked at what they were seeded with. | `defaultScheduleFields(timeZone, now)` seeds them through the same `wallClockIn` the read path uses, re-seeding once the workspace timezone loads unless the user has already chosen. Verified live with the workspace on Los Angeles and the machine on IST: the field offered 13:49 (workspace) where the bug gave 02:19 -- 12.5 hours apart. |
| 17 | S2 | The calendar read every post's position and time from `new Date(iso)` and `getHours()` -- the *viewer's* clock. A post published at 21:29 UTC in a UTC workspace showed as "Sep 9 at 2:59 AM" in India, and landed in the wrong day cell, because the grid compares the same local fields. | `wallClockDate(iso, tz)` returns a deliberately floating Date carrying the workspace's wall clock in the fields the calendar already reads, so day cells and times both move to the workspace's clock without touching the rest of the grid. The drawer now names the zone. Verified live: "Sep 8, 2026 at 9:29 PM (UTC)". |
| 18 | S2 | **The approval workflow could not be switched on by anyone.** `approvals_required` was read by `approvals.settings_for` and enforced by `assert_publishable`, but the string appeared nowhere in the frontend. Broader than logged: **no screen in the app wrote workspace settings at all** -- not the timezone every scheduled time depends on, not `client_approval_required`. | A Workspace tab in Settings, with the timezone and both approval toggles. Saved one key at a time, since the endpoint merges. Contract tests pin the write/read round trip, that setting one key does not drop the others, and that every key the server reads appears in the tab. |
| 19 | S2 | With approvals on, the composer offered Queue / Post Now / Schedule and nothing else, so every route out of step 4 was refused with a 409 saying *"Submit the post for review first"* -- with nothing on screen able to do that, and no way to leave a post unpublished at all. | Two more outcomes: **Save as draft** and **Submit for review**, the latter defaulting when the workspace gates publishing, plus a line saying why the publish options are unavailable. A contract test walks the exact sequence: publish is refused with a 409 mentioning review, and the action the composer now offers is accepted. |
| 20 | S3 | The preview rendered every post under **"Your Brand · @yourbrand"** rather than the account picked in step 1. | It shows the selected account's name, handle and avatar. Doing so uncovered a second bug: the composer mapped `sa.username`/`sa.handle`, neither of which the API sends -- the field is `account_handle` -- so the handle was empty for every account everywhere, invisible until something displayed it. Verified live: "Dana FB · @danafb". |
| 21 | S3 | The invite dialog's email field was `type="text"`. | `type="email"` with `autoComplete="email"`. |
| 22 | S3 | "Reschedule" reopened the whole four-step composer at **step 1**, with no date control until step 4. | It opens on step 4. The composer takes a `startAt` step, so "Edit" still starts at the beginning and "Reschedule" lands on the field it names. |
| 23 | S2 | `mock_metrics_untokened` was re-randomised on every read, so two reports of the same campaign over the same period gave **6,330** and **550** reach. | Closed by the #9 fabrication removal: a placeholder token now reports nothing at all, so there is no number to re-randomise. |
| 24 | S4 | `mapPlatform` matched substrings, and `n.includes("x")` caught any platform whose *name contains the letter x*. | Exact slugs, including the spellings X goes by. |
| 25 | S4 | The toast read **"Submit for review done."** -- a button label with "done." bolted on. | Each review action carries its own sentence: "Sent for review.", "Approved.", "Changes requested.", "Withdrawn from review." |
| 26 | S4 | `GET /organizations/` was requested **nine times** on one dashboard load: `getAccountId()` calls `loadTenants()` whenever the store is empty, and a dozen components call it in the same tick. | Concurrent callers share one in-flight request. Verified live on a cold load: **nine down to one**. |
| — | **S1** | **No invitation could ever be accepted.** The email built `/accept-invite?token=…`, but `AcceptInvitePage` reads `?account=` **and** `?token=`, and `/accounts/{account_id}/team/invite-info` takes the id in its path. The link gave the page nothing to ask with; every recipient saw *"Missing account or invitation token in link"*. Backend and frontend were each right on their own — nothing exercised the contract between them until someone clicked the link. | `send_invitation_email` takes `account_id` and builds `?account=…&token=…`; `teams.py` passes it. Regression test `test_the_invite_link_carries_the_account_id`, confirmed by reverting the fix and watching it fail. |

---

## Walk A — what was actually exercised

Driven in a real Chromium via Playwright, two browser contexts side by side.

**Covered end to end:** register (mouse and keyboard-only) → connect two social
accounts → invite a second person → accept the invitation in a second window →
compose through the four-step wizard → submit for review → **approve from the
other window** → schedule two minutes out → **watch the in-process worker
publish it on time** → publish to two targets with one token deliberately
broken → confirm `PARTIALLY_PUBLISHED` carrying X's real 403 → repair the token
→ **click Retry and watch the post roll up to `published`**. Also: session
survives reload, thirteen authenticated routes render clean, settings round-trip
persists.

**The publishing panel is the strongest thing in the app.** Per-target rows with
`attempt 1/3`, the platform's own error text, the live post URL, and expandable
history — that is what made #15 findable at all.

**Frontend tests.** There were none until #13-#16; there is now a vitest suite
(`npm test` in `frontend/`) holding the four rules those defects broke. Each was
confirmed by reverting the fix and watching the right tests fail.

**Not covered:** Walk B (real platform credentials). #9 makes that the priority:
it is the one defect that cannot be seen without either reading the connector
source or having a real X account to compare against.

**Notes on method.** Two of my own checks were weaker than they looked. The
route sweep first reported `/content/create` as "ok" because I only flagged
pages under 40 characters and the 404 page is 82 — it had been a 404 the whole
time (the real route is `/create-post`). And my first revert-to-confirm on the
invite fix "passed" against reverted code because my `sed` did not match a
split f-string, so nothing was actually reverted. A check that can pass while
the thing it checks is broken is not a check.

The login rate limiter (10/hour per email) is real and it caught me twice
mid-walk, presenting as an empty page rather than an obvious 429. That is the
guard working; worth knowing before blaming the UI.

---

## Observations that are not defects

- Reusing a saved browser `storageState` gets the session revoked with "This
  session has been revoked." That is refresh-token rotation working as designed.
- A newly connected account reads `health: unknown` ("Not checked" in the UI)
  until the hourly sweep. Correct by design — UNKNOWN is deliberately distinct
  from CONNECTED — but a user who has just connected an account has no way to
  know that.
- `/accept-invite` renders the marketing hero beside the invitation card. That
  is the deliberate split-panel auth layout, not a stray landing page.
- The public landing page carries an invented testimonial ("Sarah Chen,
  Marketing Director, TechFlow — engagement jumped 300%"). Marketing copy is a
  business decision, but it is the same shape as #9 and as the fabricated admin
  dashboard data already removed, and deserves a deliberate call.
- `TeamMemberResponse` exposes `invitation_token` to anyone who can list the
  team. That is what makes fixing #12 easy, but it also means any member can
  accept another person's invitation. Worth a deliberate decision.
- ~~`POST /posts/` takes `target_account_ids` but the response returns
  `target_accounts`.~~ **Fixed** — post writes refuse unknown fields with a 422
  naming the key, and accept `target_accounts` as an alias.
