# API tier audit — what the platforms will actually let us build

**Run 2026-09-10.** The mandatory tier check before Group C (§15 listening and
competitor monitoring) and Group B (§26 TikTok publishing).

The rule this exists to enforce: **what these features are allowed to be is
determined by the API tier we hold, not by code.** Building first and
discovering the access later is how a product ends up with a "competitor
insights" screen that can only be filled by inventing the numbers — which is
the failure mode this project has spent three sessions removing from the
connectors.

**A caveat on the sources.** Everything below is vendor-published pricing and
policy read on the date above, mostly through secondary write-ups because the
primary docs sit behind developer logins. Platform terms move — X's whole
pricing model changed in February 2026 — so treat the *decisions* as durable
and re-check the *numbers* before committing money. Where a figure decides a
build, it is marked **verify**.

---

## X — the model changed under us

**There is no free tier for new developers.** X replaced flat tiers with
pay-per-use credits on 6 February 2026. Existing free-tier users were migrated
with a $10 voucher; the legacy Basic ($200/mo) and Pro ($5,000/mo) tiers are
closed to new signups and existing subscribers have been auto-migrating since
June 2026. Enterprise starts around $42,000/mo.

Pay-per-use rates (**verify** before spending):

| Action | Cost |
|---|---|
| Read someone else's post | $0.005 |
| Read your own post | $0.001 |
| Create a post | $0.015 |
| Create a post containing a link | $0.20 |
| Read a user | $0.010 |

Hard cap of 2,000,000 reads/month; above that the only option is Enterprise.

### What this permits

- **Publishing: yes**, at $0.015 a post — but **$0.20 if the post contains a
  link**, a 13× penalty that matters enormously for a marketing tool, where
  most posts carry one. A workspace posting 100 linked posts a month costs $20
  in API fees alone. That is a pricing input for our own plans, not a footnote.
- **Listening: yes, within 7 days.** Recent search is included on pay-per-use.
  Full-archive search beyond 7 days needs Pro or Enterprise, neither of which
  is open to us. So an X listening feature is **a rolling 7-day window and
  nothing further back** — and it has to say so, because "no mentions found"
  and "no mentions in the last 7 days" are different statements.
- **Per-post metrics: yes, and this contradicts our own code.** `public_metrics`
  (likes, retweets, replies, quotes, impressions, bookmarks) is available on
  pay-per-use; reading your own post costs $0.001. See the correction below.

### Unit economics of listening

At $0.005 per foreign post read, monitoring a brand with 1,000 mentions a month
costs $5/month in reads for one workspace. A dozen workspaces on a plan that
does not price this in is a real cost centre. **Any listening feature needs a
per-workspace read budget with a visible ceiling**, not an unbounded poll.

---

## Meta — competitor monitoring is nearly impossible, and that is the finding

Instagram's **Business Discovery** API is the only official route to another
account's data, and it returns a deliberately thin set for a Business or
Creator account: username, biography, website, profile image, follower count,
follows count, media count, and recent media. It is capped per account per
week.

Everything else is closed. Meta's permission model restricts data to accounts
that have **explicitly authorised our app**. Not available at all:

- public hashtag streams,
- competitor behaviour or engagement patterns,
- follower lists,
- broad discovery or search.

Tools that appear to offer these rely on scraping or licensed third-party data,
not on Meta APIs.

App review is **mandatory** before serving real users and takes 2–4 weeks.
Shared rate limit of 200 calls/hour/user token.

### What this permits

A "competitor monitoring" feature built on Meta can honestly do exactly one
thing: **track the follower count, media count and recent public posts of named
Instagram Business/Creator accounts, refreshed within a weekly cap.**

That is a follower-count tracker. It is not competitive intelligence, and
calling it that in the UI would be the same category of dishonesty as the
fabricated metrics — a label promising something the data cannot support.

---

## TikTok — the application is blocked on 3.3, not before it

This answers the standing question directly, and the answer is the opposite of
what the sequencing assumed.

The Content Posting API's Direct Post needs the `video.publish` scope. **Until
the app is audited:**

- everything posted is forced to **SELF_ONLY** (private) visibility,
- at most **5 users** may post in any 24-hour window,
- every posting account must itself be set to private at the time of posting.

Lifting those requires an audit, and the audit requires **app review including
at least one demo video showing the complete end-to-end flow**, plus URL
verification for the Content Posting endpoints.

### The consequence

**We cannot submit a meaningful TikTok application before building 3.3.** The
audit wants a video of the working integration. The correct order is:

1. build 3.3 against the documented API shape,
2. register the app and post privately as an unaudited client — which is
   exactly what the unaudited tier is *for*,
3. record the end-to-end demo from that,
4. submit for audit,
5. ship publicly only once audited.

So "TikTok application submitted?" has been a question with no good answer
available: submitting early would have meant submitting without the demo the
reviewers require. Worth knowing before another cycle of asking.

**Design consequence for 3.3:** the integration must treat SELF_ONLY as a
first-class state, not an error. An unaudited deployment publishing privately
is working correctly, and the UI has to say "posted privately — your app is not
yet audited by TikTok" rather than reporting success that looks public.

---

## Decisions

| # | Question | Decision |
|---|---|---|
| 1 | Build §15 social listening? | **Yes, X only, 7-day window, with a read budget.** Meta cannot feed it — no hashtag streams, no public search. A listening feature that silently covers one platform of four must say which. |
| 2 | Build §15 competitor monitoring? | **Narrowly, and rename it.** Instagram Business Discovery supports tracking named competitor accounts' follower/media counts and recent posts, capped weekly. Ship it as "competitor tracking", not "competitive intelligence", and state the refresh cap in the UI. |
| 3 | Cross-platform listening? | **No.** There is no honest way to offer it. Anything presenting X mentions beside empty Meta results needs per-platform "not supported here" the way the inbox already does. |
| 4 | TikTok application now? | **No — after 3.3.** The audit needs a demo video of the working flow. |
| 5 | Pay for X access before Walk B? | **Needed sooner than planned.** See below. |

---

## Two things this audit changes retroactively

### Walk B's X assumption is out of date

`docs/WALKTHROUGH-B.md` says "X (free tier: can publish, per-post metrics
gated)". **There is no free tier any more.** Walk B's X half now needs a
funded pay-per-use account — small money (a handful of test posts is cents),
but it is a credit card, not a signup. The plan should say so before you sit
down to it. Facebook remains free to develop against, so the "numbers"
half of Walk B is unaffected.

### Our X connector's stated reason for refusing is wrong

`TwitterConnector.get_post_metrics` raises `NotSupportedError` — correct
behaviour, and the honest-null path built on it stands. But its docstring says
this "requires an elevated access tier", and that is no longer true:
`public_metrics` is readable on pay-per-use at $0.001 for an owned post.

The refusal is still right **for a deployment with no funded X credential**,
which is every deployment we have. But the reason is now "we have not
implemented it and it costs money per read", not "the tier forbids it". That
distinction decides whether it is ever implemented, so the docstring should say
the true thing.

**Recommended shape when it is implemented:** capability-gated, exactly as the
doctrine requires — a real fetch when a funded credential is configured,
`NotSupportedError` when it is not. Never a fabricated number in either branch,
and never a silent zero.

---

## Sources

Read 2026-09-10. Secondary write-ups, because the primary references sit behind
developer logins.

- X pricing and tiers — https://postproxy.dev/blog/x-api-pricing-2026/
- X credit pricing — https://www.socialcrawl.dev/blog/x-twitter-api-2026
- X `public_metrics` availability — https://api.sorsa.io/blog/twitter-analytics-api
- X API overview (primary) — https://docs.x.com/x-api/getting-started/about-x-api
- Instagram API changes 2026 — https://storrito.com/resources/instagram-api-2026/
- Instagram integration and review — https://www.getphyllo.com/post/instagram-api-integration-101-for-developers-of-the-creator-economy
- TikTok Direct Post (primary) — https://developers.tiktok.com/docs/en/content-posting-api-reference-direct-post
- TikTok unaudited-client limits — https://vorplabs.com/agent-tools/tiktok-content-posting-api
- TikTok posting guide 2026 — https://timetopost.co/blog/how-to-post-to-tiktok-api/
