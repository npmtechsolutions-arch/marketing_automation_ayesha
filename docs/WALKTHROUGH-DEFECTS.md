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

| # | Step | Sev | What happened | Expected |
|---|------|-----|---------------|----------|
| 9 | analytics, everywhere | **S1** | **LinkedIn and X report randomly generated engagement as real data.** `TwitterConnector.get_post_metrics` and `LinkedInConnector.get_post_metrics` both `return mock_metrics_fallback(self.slug)` unconditionally — not gated on a dev token, not gated on `DEBUG`. Their own docstrings say *"Returns fabricated numbers."* So a user who connects a real X account with real credentials sees invented likes/comments/shares on their posts, in the analytics dashboards, and in exported PDF/CSV/Excel reports they may send to a client. Verified live: three consecutive reads of one post returned 755/135/28/684, then 72/35/63/4437, then 674/75/16/934 — the same post, seconds apart. | Report nothing, and say the platform does not expose it, per the null-vs-zero doctrine already applied to `engagement_rate`. |
| 10 | 4 (invite) | **S1** | **A workspace you were invited to is unreachable.** `TopBar`'s switcher renders `organizations.map(org => workspaces.filter(w => w.organization_id === org.id))`, and `organizations` is **always empty**: `authStore` imports the raw axios instance, so `api.get("/organizations/")` resolves to an axios *response*, and `itemsOf` has branches for a bare array and for `response.items`/`response.data.items` — but none for `Array.isArray(response.data)`, which is the shape `/organizations/` actually returns. The dropdown therefore lists nothing for anyone, ever; only "Manage workspaces" shows. Verified live: the server returned the org correctly and the menu was empty. | The switcher lists every workspace, grouped by org. |
| 11 | 4 (invite) | **S1** | Stacked behind #10: `GET /organizations/` returns only orgs the user **owns**. `GET /accounts/` correctly returns every workspace they can reach (verified: Bob got Olive's workspace with `role: editor`). So even with `itemsOf` fixed, a workspace joined by invitation still has no org row to group under and stays invisible. Both bugs must be fixed for an invitee to reach their workspace. | Return orgs reachable via membership, or group by workspace and drop the org dependency. |
| 12 | 4 (invite) | **S1** | **The invitation link cannot be obtained by any route.** The team page's own instructions say *"After sending, an invitation link will appear on screen. Click 'Copy Invitation Link'"* — **there is no such button**; the pending row offers only "Cancel". The same panel says *"No automatic email is sent"*, which is false — the backend does send one. And in dev the email is suppressed with a log line carrying only `to=` and `subject=`, not the link. So: no email, no log, no button. `TeamMemberResponse` already includes `invitation_token`, so the UI has everything it needs and simply never renders it. | Render the copy button the page already promises. |
| 13 | 4 (invite) | **S2** | The team page hardcodes `const planLimit = 10` and the literal string `"Growth Plan"`. A brand-new Free workspace is told **"1 of 10 team members used · Growth Plan"** and then refused with *"You have reached your Free plan's limit for team members (1)"* on the very next click. Two contradicting numbers on one screen; 10 happens to be the real Growth limit, so someone pasted a mid-tier plan's values in as a placeholder. | Read the limit and plan name from the entitlement API. |
| 14 | 6 (calendar) | **S2** | `mapStatus` in `CalendarPage.tsx` handles `published`, `partially_published`, `scheduled`, `failed`, `publishing` — and falls through to `"draft"` for everything else. So `approved`, `in_review` and `changes_requested` all render as **"Draft"**, the "Drafts" filter lumps them together, and the `selectedPost.status === "draft"` action gate fires for approved posts. Verified live: API said `status: approved`, drawer badge said "Draft" on a fresh load while the REVIEW row beside it said "Approved". | Map every status the API can return. |
| 15 | 6 (calendar) | **S2** | `partially_published` maps to `published`, so a post that **failed on one of its two platforms is counted and badged as "Published"** — the drawer header showed a green "Published" pill while the REVIEW row said "Partly published" and the panel below showed X in red with a 403. The top-of-calendar counter read "2 Published · 1 Failed" with the partial one inside "Published". | A partial publish is not a publish. |
| 16 | 6 (composer) | **S2** | The schedule step's date/time fields are **prefilled in the browser's clock** while the note directly beneath them says *"Times are on the workspace's clock (UTC), not your computer's."* Verified live: with the machine on IST and the workspace on UTC, the fields defaulted to `03:54` when UTC was `21:24` — the default was local-now + 1h, which read as workspace time is 6.5 hours off. Defect #1 fixed the parse and the read path; the default value was missed. | Default in workspace time, as the label promises. |
| 17 | 6 (calendar) | **S2** | The drawer renders post timestamps in the browser's timezone — a post published at `21:29 UTC` in a UTC workspace displayed as *"Sep 9, 2026 at 2:59 AM"* on an IST machine. Same family as #1 and #16; the composer was fixed, the calendar drawer was not. | Render on the workspace clock, consistently with the composer. |
| 18 | 5 (approvals) | **S2** | **`approvals_required` cannot be switched on by a user.** It is read by `approvals.settings_for` and enforced by `assert_publishable`, but the string `approvals_required` appears **nowhere in the frontend** — no toggle, no settings row. The only way to enable the entire approval workflow is a hand-written `PUT /accounts/{id}/settings/` with the right nested blob. | A toggle in workspace settings. |
| 19 | 5 (approvals) | **S2** | With approvals on, the composer's four-step wizard offers Queue / Post Now / Schedule and **no "submit for review"** and no "save as draft". Every path commits to publishing. Confirming returns a 409 — *"This workspace requires approval before publishing. Submit the post for review first."* — with nothing on screen to do that. The post **is** created as a draft, and "Submit for review" exists in the calendar's post drawer, so the flow is completable; nothing tells you to go there. | Offer "Submit for review" in the composer, or link the 409 to the drawer. |
| 20 | 6 (composer) | **S3** | Step 3's preview renders the post under **"Your Brand · @yourbrand"** rather than the account selected in step 1 ("Dana FB / @danafb"). The preview's whole job is showing what it will look like on that account. | Use the selected account's name, handle and avatar. |
| 21 | 4 (invite) | **S3** | The invite dialog's email field is `type="text"` — no email keyboard on mobile, no browser-level validation. | `type="email"`. |
| 22 | 6 (calendar) | **S3** | "Reschedule" in the post drawer does not open a date picker; it reopens the whole four-step composer at **step 1**, with no date control visible until step 4. It does edit in place (verified: no duplicate post created) and the content is carried over, so it works — it just is not what the label says. | A date/time picker, or rename the action. |
| 23 | analytics | **S2** | `mock_metrics_untokened` (Facebook, YouTube dev tokens) is re-randomised on **every read**, so the same post's engagement changes on each page refresh. Raised from S3 while building 2.7: two campaign reports generated minutes apart, for the same campaign over the same period, reported **6,330** and **550** reach. A report is a statement of fact that gets sent to a client, and two of them contradicting each other is worse than either being wrong. | Seed on the post id so a given post is stable, or store the first fetch. |
| 24 | 6 (calendar) | **S4** | `mapPlatform` matches on `n.includes("x")`, so any platform whose *name contains the letter x* maps to Twitter; anything unrecognised maps to Instagram. Harmless with today's five platforms, a trap for the sixth. | Match on the platform slug. |
| 25 | 5 (approvals) | **S4** | The toast after submitting reads **"Submit for review done."** | "Sent for review." |
| 26 | perf | **S4** | `GET /organizations/` is requested **nine times** on a single dashboard load. | Once. |
| 5 | 2 (landing) | S3 | `POST /auth/refresh` fires on the public landing page for anonymous visitors, producing a console error on every first visit. | No auth call before there is a session. **FIXED — see below.** |
| 7 | `POST /ai/generate-content` | S2 | A provider failure is caught, mock text is substituted with the raw exception interpolated into it, and the `AIGeneration` row is recorded **COMPLETED**. **FIXED — see below.** |

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
