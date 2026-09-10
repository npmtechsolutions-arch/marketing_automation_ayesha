# Walk B — real platform credentials

Walk A proved the app against mock tokens. Walk B is the half no mock can
reach: **the connectors now refuse rather than invent, and no real platform has
ever tested that refusal.**

Two platforms, chosen so one exercises each half of the fix:

| | Platform | What it proves |
|---|---|---|
| **the nulls** | **X** (free tier) | Publishing works; per-post metrics are gated, so `get_post_metrics` raises `NotSupportedError` against a **real, correctly-credentialed account**. The honest-null path end to end — no row written, "does not expose per-post metrics" in the drawer, blank cells in the report. |
| **the numbers** | **Facebook Page** (Meta app, test Page) | The richest metrics available. Proves the measured path: real numbers arrive, are stored, and reach `analytics_daily` overnight. |

LinkedIn substitutes for Facebook if a company page is easier to obtain than a
Meta app; it needs an approved Marketing Developer Platform application for
metrics, so it is the slower road.

---

## Setup — yours, because it cannot be mine

Creating developer apps needs an account on each platform's developer site,
accepted developer terms and identity verification. I have no access to any of
that. Everything below is the complete list, so it should be paste-and-click.

### 0. X is no longer free — read this before creating the app

**Changed since this plan was written.** The 2026-09-10 tier audit
(`docs/API-TIER-AUDIT.md`) found that X discontinued its free tier for new
developers on 6 February 2026 and moved to **pay-per-use credits**. There is no
free path any more.

For Walk B this is small money but it is a credit card, not just a signup:

| Action | Cost |
|---|---|
| Create a post | $0.015 |
| Create a post **containing a link** | $0.20 |
| Read a post you own | $0.001 |

A walk that publishes two or three test posts costs cents. Load the minimum
credit the console will take.

The `$0.20` for a post containing a link is not a typo and is worth seeing with
your own eyes during the walk — it is a 13× penalty on exactly the kind of post
a marketing tool exists to send, and it is a pricing input for our own plans.

**Facebook is unaffected** and remains free to develop against, so the
"numbers" half of the walk needs no spend.

### 1. Free the callback port

The registered redirect URI must match **exactly**, and the defaults assume
port 8000:

| Platform | Redirect URI to register |
|---|---|
| X | `http://localhost:8000/api/v1/twitter/callback` |
| Facebook | `http://localhost:8000/api/v1/facebook/callback` |
| LinkedIn | `http://localhost:8000/api/v1/linkedin/callback` |

Check nothing else has the port — on this machine another project's server
(TravelHive) has taken 8000 twice, and its `/api/v1/auth/login` even answers,
so the symptom is confusing:

```
lsof -nP -iTCP:8000 -sTCP:LISTEN
```

To use a different port, set the matching `*_REDIRECT_URI` in `.env` **and**
register that exact URI. Both platforms allow plain `http` for `localhost`
during development.

### 2. Create the apps and copy the credentials into `.env`

Do not paste them into the chat.

```dotenv
# X — developer.x.com, a project + app with OAuth 2.0 enabled,
# "Web App" type, and User authentication set up.
TWITTER_CLIENT_ID=
TWITTER_CLIENT_SECRET=
TWITTER_REDIRECT_URI=http://localhost:8000/api/v1/twitter/callback

# Meta — developers.facebook.com, a Business app with the Facebook Login
# product added, and a Page you administer.
META_APP_ID=
META_APP_SECRET=
META_REDIRECT_URI=http://localhost:8000/api/v1/facebook/callback

# LinkedIn — only if used instead of Meta.
LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=
LINKEDIN_REDIRECT_URI=http://localhost:8000/api/v1/linkedin/callback
```

### 3. Scopes the app requests

Grant exactly these; a missing one fails at consent rather than at publish.

- **X** — `tweet.read tweet.write users.read offline.access`
  (`offline.access` is what makes the refresh-token half of step 8 testable.)
- **Facebook** — `pages_manage_posts, pages_read_engagement, pages_show_list,
  read_insights`
- **LinkedIn** — `openid profile email w_member_social` for a personal account;
  add `r_organization_social w_organization_social rw_organization_admin` for a
  company page.

### 4. TikTok — a third platform, with a different kind of gate

Added by Phase 3.6. It is worth walking **because** its gate is unlike the
other two: X's is money and Meta's is app review for *metrics*, but TikTok
gates **who can see what you publish**. An app TikTok has not audited may only
post `SELF_ONLY` — the video really is live, and really is visible to nobody
but its author.

The connector treats that as a state, not an error: the publish succeeds and
carries a notice saying it went out privately. That is the behaviour to watch
for during the walk, and it is what makes the audit submission possible at all
— you cannot film a demo video of a flow that refuses to run.

**Redirect URI** (register this exact string):

```
http://localhost:8000/api/v1/tiktok/callback
```

**Credentials** — developers.tiktok.com → Manage apps → your app. TikTok calls
the id a *client key*, not a client id, and the `.env` name follows TikTok:

```dotenv
# TikTok — developers.tiktok.com, an app with Login Kit and the
# Content Posting API added.
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=
TIKTOK_REDIRECT_URI=http://localhost:8000/api/v1/tiktok/callback
```

**Scopes** — `user.info.basic`, `user.info.stats`, `video.publish`.

* `video.publish` is **Direct Post** — the video lands on the profile.
  `video.upload` alone only drops a draft into the user's TikTok inbox, which
  is a different product and not what this connector implements.
* `user.info.stats` is what makes `get_analytics` return anything. Without it
  the connection can publish and reports **no** follower count — which is the
  null discipline working, not a bug. If the walk shows an empty analytics row
  for TikTok, check the granted scopes before assuming a defect.

**Sandbox and test users.** TikTok's sandbox lets you nominate a small number
of test accounts, and until the app is audited each of them must be able to
accept a private post. Confirm the current caps in the portal rather than
trusting this paragraph — TikTok has changed them before, and a wrong number
here would send someone hunting for a bug that is a quota.

#### The audit, and what the demo video has to show

Direct Post is the part TikTok reviews. The submission is a form plus an
unlisted video walking the whole flow, and the reviewer is checking the
*consent* story, not the code:

1. The user connecting their own TikTok account through the real consent
   screen — not a pre-connected session.
2. The composer, showing what will be posted: caption, hashtags, the video
   itself.
3. The visible statement that posts are private until the app is audited.
   MarketEngine shows this in three places, which is deliberate: on the connect
   panel before authorising, in the toast when the connection lands, and in the
   publishing log line after each publish.
4. The publish, and then the post open **on TikTok**, matching what the
   composer showed.

Nothing in the app has to change to film this. The one thing to remember is
that the demo must show the private-post disclosure — an app whose UI hides it
is the specific failure TikTok rejects for.

#### After approval

Approval does not travel automatically. The connection carries its own audit
state on `social_accounts.config.tiktok_audit_state`, defaulting to
`unaudited`, and publishing reads it to choose the privacy level. Moving it to
`audited` is a deliberate step, not something to infer:

```sql
UPDATE social_accounts
   SET config = jsonb_set(config::jsonb, '{tiktok_audit_state}', '"audited"')
 WHERE id = '<social_account_id>';
```

Inferring it would be the wrong kind of guess: assume audited and the app sends
`PUBLIC_TO_EVERYONE` from a client TikTok rejects; assume it *silently* and a
video someone believed was private goes public. Reconnecting an already-audited
account preserves the state.

#### What to watch during the walk

- A post with no video is refused **in the composer**, before publishing, with
  "tiktok publishes video only". TikTok has no text-only post at all.
- A publish returns success with the private-post notice in the job log, and
  the log records the platform's `publish_id`.
- The poll: a large video sits in `PROCESSING_UPLOAD` for a while. The panel
  should stay on one attempt — the wait is inside the publish, not a retry.
- A rejected video shows TikTok's own `fail_reason` (`video_pull_failed`,
  `picture_size_check_failed`), not "publishing failed".
- Per-post metrics are **refused**, like X's: `video.list` is not in the
  requested scopes, so no performance row is written and the drawer says so.

### 5. Listening — the half that spends money per poll

Added by Phase 3.7, and the one part of Walk B where the *checking* has a
price. Everything else here costs a few cents once; listening costs a few cents
**every time it runs**, so the walk includes the arithmetic as much as the
behaviour.

No extra app or scope is needed: listening uses the same X connection and the
same `tweet.read` scope as the rest of the walk. What it needs is a **funded**
pay-per-use account, because recent search bills per post read.

#### What a poll costs

From the audit's table (`docs/API-TIER-AUDIT.md`, read 2026-09-10; verify
before spending):

| | |
|---|---|
| Read someone else's post | **$0.005** |
| Posts asked for per poll (`MAX_RESULTS_PER_POLL`) | 25 |
| **Worst case per poll** | 25 × $0.005 = **$0.125** |
| At the 6-hour default | 4 polls/day = **$0.50/day**, about **$15/month**, per query |
| At hourly | 24 polls/day = **$3/day**, about **$90/month**, per query |

Two things stop those being the real numbers. A poll is billed for the posts it
**actually finds**, so a quiet search costs nearly nothing; and every poll after
the first passes `since_id`, so it asks only for what is new rather than
re-reading the window. The figures above are the ceiling, and the UI says so in
those words.

The plan limits are set against this: Free 0 saved searches, Starter 1, Growth
3, Pro 10, Enterprise unlimited. Free gets none deliberately — a free plan that
polls a metered API is a cost centre with no revenue against it.

#### The walk

1. **Before connecting anything**, open **Listening**. It should say the
   feature is idle because no X account is connected — not show an empty
   stream. An empty page here would be the defect.
2. Connect X (step 1 above), then save a search. Use something with real but
   low traffic — your own brand name, not `the` — because you are paying per
   post it finds. `marketengine OR @marketengine` is the shape.
3. **Poll now** (the refresh button on the query). The toast reports posts read
   and the cost of *that* poll. Check it against the arithmetic above.
4. **Poll again immediately.** The second poll must return **0 new** even if it
   read the same posts: the stream is idempotent on X's post id. A duplicated
   stream here would be the 2.5 defect returning.
5. **Check `since_id` is working**: after a successful poll the query's cursor
   is set, and the next poll's `posts_read` should be small or zero on a quiet
   search. A poll that keeps reading 25 posts on every pass is re-paying for
   the same window.
6. **Read the window everywhere.** The header, the empty state and the API
   payloads all say *the last 7 days*. Anything that says just "no mentions" is
   a defect — X cannot see further back, and the UI must not imply it looked.
7. **Break it on purpose.** Either revoke the app's access or let the account's
   credits run out, then poll. The query must turn **Not running** with X's own
   reason on the row, and the banner must say the stream is not evidence of
   quiet. A silent empty stream here is the site-#2 fabrication in another
   shape, and it is the single most important thing this walk proves.
8. **Interval.** Change the polling interval on the Listening page (1/3/6/12/24
   hours). The daily ceiling next to it should change with it, and a value
   outside that set must be refused by the settings endpoint rather than
   quietly clamped.
9. **Next sweep.** The worker looks every 15 minutes but polls a query only
   when the workspace's own interval has come round. Leave it running and
   confirm a poll happens on schedule and not more often — that gap is the
   difference between $15 and $90 a month per query.

**Not in this phase:** sentiment. It would be a metered AI call per mention on
top of the per-post read, which is a pricing decision rather than a feature
decision, and it has not been made yet.

### 6. Competitor tracking — the Meta half, and its own gate

Added by Phase 3.8. It needs nothing new from X, and nothing new from the Meta
app beyond what the "numbers" half of this walk already sets up: an Instagram
**business** account connected through the Meta app, because Business Discovery
must be asked *as* one. Meta's requirement, not ours, and the reason a
workspace without one is shown the requirement rather than an empty screen.

Permissions: the same `instagram_basic` + `pages_show_list` the Instagram
connection already carries. Business Discovery adds no scope of its own, which
is the one piece of good news in the audit's Meta section.

#### What it can and cannot see

| | |
|---|---|
| Returned | username, name, follower count, media count |
| Not returned, on any tier | engagement, posting frequency, top content, audience, follower lists |
| Works for | public Instagram **business and creator** accounts |
| Invisible to it | personal accounts, private accounts |
| Cap | roughly one lookup per account per week |

The absences are the feature's most important product decision, so they are
stated in the add dialog before anyone commits to using it — not discovered
later as a thin card.

#### The walk

1. **Before connecting Instagram**, open **Competitors**. It should state the
   requirement (an Instagram business account) rather than showing an empty
   list.
2. Connect the Instagram business account from step 1 of this walk, then add a
   competitor by handle. Use a real public business account — a brand you
   actually compete with, or any public business account for the test.
3. **Type a handle wrong on purpose.** It must be refused *at add time*, with
   Instagram's own reason, and nothing stored. A typo tracked silently would
   sit there empty forever and read as a competitor with no followers.
4. **Try a personal account.** Same refusal, different sentence: Discovery
   cannot see personal or private accounts at all.
5. **Check the first card.** One snapshot means no chart — it should say the
   trend appears after next week's check rather than drawing a line through a
   single point.
6. **Press "check now" twice.** The second must be refused: Instagram allows
   about one lookup per account per week and counts attempts, not successes.
7. **A week later**, confirm a second snapshot appears and the chart draws,
   with the axis scaled to the tracked range and the exact numbers printed
   above it.
8. **Read the staleness.** Every number is shown with how old it is ("as of 6
   days ago"). A card that shows a follower count with no age is a defect —
   the freshest possible figure here is one weekly lookup old.
9. **Break it on purpose.** Revoke the Instagram connection, then wait for the
   weekly sweep (or force one). The competitor row must say why it could not be
   checked. A chart that simply stops gaining points looks like an account that
   stopped changing.

**Live status:** the whole of this waits on the Meta developer app and a
connected Instagram business account, exactly like the "numbers" half of the
walk. Everything short of Meta itself has been verified locally: the capability
gate, the plan limit, the refusal of a placeholder credential (400, naming the
credential rather than blaming Instagram), the weekly cap on manual refresh,
snapshot upsert on a repeat check, tenant isolation, and both themes of the UI.

### 7. Start on a clean workspace

Register a **fresh workspace** for the walk. An existing one carries Walk A's
mock accounts, and the point is to watch real numbers arrive against nothing.

---

## The walk

In order. Log anything surprising in the table below — the rule from Walk A
still holds: **log it, move on, triage at the end.**

1. **Connect** — Accounts → Add Account → the real OAuth consent screen →
   back to the app with the account listed.
2. **Health CONNECTED** — the account's health should leave `unknown` once the
   sweep runs. It is hourly; `POST /social-accounts/{id}/verify` forces it.
3. **Publish for real** — compose, target the real account, Post Now.
4. **See it on the platform** — open the post on X / the Page itself. The
   per-target panel's URL should take you there.
5. **The per-target panel shows the platform's own response** — real external
   id, real post URL, `attempt 1/3`.
6. **Metrics: measured or null, never invented.**
   - X: no performance row at all, and the drawer says *"X does not expose
     per-post metrics, so there is nothing to report."*
   - Facebook: real numbers, and they should not change between two reads.
     (Two reads giving different numbers is the old fabrication; it is gone,
     but this is the check that proves it against a live API.)
7. **Report** — generate one and open the PDF. Anything unmeasured must render
   as an em-dash. **Pre-flight below already proves this for a workspace with
   nothing measured; step 7 proves it for a mixed one**, where X contributes
   blanks and the Page contributes numbers in the same table.
8. **Break it on purpose** — revoke the app's access from the platform's own
   settings, or wait for the token to expire. Then confirm:
   - health goes **FAILED**, not silently stale;
   - a publish attempt shows the platform's real error in the panel;
   - **nothing invents a number to cover the gap.** This is the fix from site
     #2 — the `except Exception` that used to log "falling back to mock" and
     return random integers — and it is only provable here.
9. **Next morning** — `analytics_daily` holds real rows for the Page, and none
   for X. The daily sync runs on the hour.

---

## Pre-flight — done without credentials

Three of the mission's checks did not need a real platform, and one of them
found something.

| # | What | Result |
|---|---|---|
| — | Report renders em-dashes where nothing was measured | **Passes.** All four headline cards render `—`, no literal `0`. Pinned by `test_a_report_with_nothing_measured_renders_dashes_not_zeroes`. |
| **B1** | 112 fabricated rows still in `analytics_daily` | **Fixed.** See below. |
| **B2** | A report for a workspace with no connected accounts crashed | **Fixed.** See below. |

### Step 8, most of the way, without credentials

Step 8's point is the failure path: a revoked or expired token must produce an
honest error and **no invented number**. A revoked token and an invalid one look
the same to the connector — both are a 401 from the real API — so most of it can
be proven now. Outbound calls to `api.twitter.com` and `graph.facebook.com` both
work from here, and a real-shaped invalid token reaches the network path
(`is_mock_token` does not match it, so nothing short-circuits):

```
twitter    post=NotSupportedError      account=refused (empty)
facebook   post=refused (empty)        account=refused (empty)
instagram  post=refused (empty)        account=refused (empty)
youtube    post=refused (empty)        account=refused (empty)
linkedin   post=NotSupportedError      account=refused (empty)
```

Every connector made a real HTTP call, got a 401/400, and returned nothing.
Before the fix, every one of those cells held random integers behind a log line
reading *"falling back to mock"*.

What still needs the real walk: that **health flips to FAILED** rather than
going quietly stale, and that the per-target panel shows the platform's own
error text to a user. Both need a connected account to fail, not a synthetic
one.

### B1 — the #9 cleanup missed `analytics_daily` (S2)

Migration `b8d3aa61c94f` deleted fabricated **post** metrics and left the
account-level table alone. `mock_account_metrics()` had been writing invented
follower counts, reach and impressions there for any placeholder token, and 112
such rows were still feeding reports: a report generated to check the em-dash
path rendered **"62,233 followers"** for a workspace with no real connection.

Fixed by `c5f18ba2d703`, which deletes rows belonging to accounts whose token is
still a development placeholder — the same unambiguous argument as X and
LinkedIn post metrics. Accounts with a real token, and their history, are
untouched, so this does not touch anything Walk B is about to create.

**Why it matters for Walk B:** without it, the first real numbers would have
been blended with invented history in the same report.

### B2 — a report for a brand-new workspace failed (S2)

`analytics_query.audience()` returned **two different shapes**: the
no-social-accounts early return used the keys `growth`/`growth_percent`, while
the populated path used `change`/`change_percent`. `_executive_summary` reads
`change`, so a workspace with nothing connected raised `KeyError: 'change'` and
the report came back FAILED with *"Could not gather the numbers"*.

That is the exact state of the fresh workspace step 4 of the setup asks for, so
Walk B would have hit it before connecting anything. One shape now.

---

## The zero-connection walk — run 2026-09-11

The credential half of Walk B is still blocked (nothing is in `.env`), but one
whole half of it never needed credentials: **what a new customer sees before
they connect anything**. That is the Walk A defect class — a page that shows an
empty void where it should explain itself, or says something the server does
not support — and it turned out to be where the product was least honest.

Method: a fresh workspace created through the real registration bootstrap, then
every page in the sidebar visited in a browser with console errors and failed
requests recorded per page. Eighteen pages; five defects, four of them on the
first screen anybody sees.

| # | Where | Sev | What happened | Status |
|---|-------|-----|---------------|--------|
| **B3** | Dashboard | **S1** | A hardcoded sentence: *"Your social channels are performing 14% above baseline"* — shown to every workspace, including one with no connected accounts and no posts. | **Fixed** |
| **B4** | Dashboard | **S1** | A hardcoded *"Optimal posting window for LinkedIn & Instagram today is 4:30 PM – 6:00 PM"*, on a workspace with neither platform connected. | **Fixed** |
| **B5** | Dashboard | S2 | Stat cards rendered a green upward badge reading **"+%"** with no number, for a workspace with nothing to compare. | **Fixed** |
| **B6** | Dashboard / `/analytics/overview` | S2 | "Total Reach **0**", "Avg Engagement Rate **0.00%**", "0 followers gained" where nothing had been measured. | **Fixed** |
| **B7** | Inbox | S2 | `GET /accounts/{id}/teams/members` 404'd on every load, so the assignee dropdown was always empty. | **Fixed** |

Every other page passed: analytics, calendar, composer, accounts, listening,
competitors, reports, campaigns, strategy, monthly plan, media, team, settings,
billing, activity and notifications all explained themselves with no console or
network errors.

### B3 / B4 — the dashboard was making things up (S1)

Two hardcoded strings in `DashboardPage.tsx`, both in the most prominent
position in the product, both shown unconditionally:

```
{today} • Your social channels are performing 14% above baseline
Optimal posting window for LinkedIn & Instagram today is 4:30 PM – 6:00 PM.
```

This is the fabrication class the project has now removed four times — a
`Math.random()` heatmap, a hardcoded price table, an admin dashboard of invented
signups, and these. It is the worst variant of it, because a performance claim
about *the customer's own account* is exactly what a marketing tool exists to
report, and because it greets every new user before they have done anything.

The header line is now the date, which is the only thing that sentence knew.
The advisor card now calls the **real** best-times endpoint built in 2.6 —
which already distinguishes this account's observed data from the platform's
usual times — and says which it is showing:

> Best time to post next: **Tuesday 10:00** — from the platform's usual times,
> not this account's yet.

With nothing to say, the card renders the service's own explanation rather than
a sentence of its own.

### B5 — a missing comparison rendered as a rise (S2)

`StatCard` guarded on `change !== undefined`, and the dashboard passes `null`.
`null !== undefined` is true and `null >= 0` is true, so "we have nothing to
compare against" rendered as a green, upward, positive-looking badge containing
no number at all: **"+%"**.

The rule moved to `src/lib/stats.ts` (`changeBadge`) and is pinned by tests,
because the next card would have got it wrong the same way. Null and undefined
are both absences; neither is a rise.

### B6 — the dashboard endpoint coalesced every measurement to zero (S2)

`/analytics/overview` wrapped each aggregate in `coalesce(..., 0)` and typed
the schema as non-optional, so a workspace that had measured nothing was told
"0 reach, 0 engagement, 0.00% engagement rate". The reports and the analytics
page were fixed for precisely this in an earlier phase; **this endpoint was
missed because nothing tested it**, and it is the one the dashboard uses.

`total_followers_gained` was worse: a literal `0` with a comment saying follower
tracking did not exist. It does — `analytics_daily` records it and
`analytics_query.audience()` computes the change with the right null handling —
so the endpoint now calls it.

Fixed by removing the coalesces, making the schema optional, and refusing to
draw a comparison from an unmeasured previous period. `total_posts` stays an
`int`: a count of zero published posts is a real answer, not a gap. Pinned by
`test_the_overview_endpoint_reports_nulls_where_nothing_was_measured`.

### B7 — the inbox asked for a route that does not exist (S2)

`InboxPage` fetched `/accounts/{id}/teams/members`; the teams router is mounted
at `/accounts/{id}/team` and lists members at its root. Two 404s on every inbox
load, and an assignee dropdown that has never contained a single person — so
"assign this conversation to a teammate" looked available and did nothing.

---

## Findings — the credentialled walk

Nothing yet — this half has not been run.

| # | Step | Sev | What happened | Expected |
|---|------|-----|---------------|----------|
