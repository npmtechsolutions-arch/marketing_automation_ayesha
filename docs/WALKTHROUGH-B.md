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

### 5. Start on a clean workspace

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

## Findings

Nothing yet — the walk has not been run.

| # | Step | Sev | What happened | Expected |
|---|------|-----|---------------|----------|
