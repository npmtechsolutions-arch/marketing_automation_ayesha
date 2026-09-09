# MarketEngine AI

An AI-powered marketing automation platform for small and mid-sized businesses. Rather than being only a scheduling tool, it aims to act as a decision engine: it turns a business profile and a set of goals into a content strategy, generates the posts, schedules and publishes them across social platforms, then reports on how they performed.

**Core capabilities**

- **Strategy generation** — AI-generated marketing strategies and topic suggestions derived from a stored business profile.
- **Content generation** — post copy and images via OpenAI, Anthropic, or Gemini, with per-platform variants.
- **Scheduling and publishing** — a calendar plus a background worker that publishes scheduled posts to Facebook, Instagram, LinkedIn, X/Twitter, and YouTube.
- **Approval workflow** — draft → review → approve/reject before anything is published.
- **Analytics** — engagement metrics synced back from each platform, aggregated per account and per post.
- **Teams and RBAC** — multiple accounts per user with five roles (`viewer` → `editor` → `manager` → `admin` → `owner`) and an invitation flow. See [documents/RBAC-Permissions.md](documents/RBAC-Permissions.md).
- **Billing** — Stripe-backed subscription tiers with per-tier usage limits.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, SQLAlchemy 2.x (async), Pydantic v2 |
| Database | PostgreSQL 15 (asyncpg driver) |
| Background jobs | Celery + Redis; plus an in-process scheduler for due posts |
| Auth | JWT access/refresh tokens, TOTP 2FA, Firebase for Google sign-in |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4, Radix UI |
| Frontend state | TanStack Query (server state), Zustand (client state) |
| Payments | Stripe |
| Media storage | Local disk by default; S3-compatible when configured |

---

## Repository layout

```
backend/
  alembic/
    versions/           database migrations
    env.py              alembic config: reads DATABASE_URL from app settings
  app/
    api/v1/endpoints/   HTTP endpoints, one module per resource
    core/               config, database, security, auth/authz, scheduler
    models/             SQLAlchemy ORM models
    schemas/            Pydantic request/response schemas
    services/           business logic (platform clients, entitlements, ...)
    workers/            Celery app and periodic tasks
  scripts/              one-off operational scripts (seeding, maintenance)
  tests/                pytest suite
frontend/
  src/                  React application
  public/               static assets served at the site root
documents/              product, design, RBAC and API specifications
docs/                   integration notes
```

---

## Running locally with Docker Compose

The compose stack is the fastest path — it starts Postgres, Redis, the API, a Celery worker, the Celery beat scheduler, and the Vite dev server.

**Prerequisites:** Docker and Docker Compose.

```bash
# 1. Create your environment file
cp .env.example .env

# 2. Start everything
docker compose up --build
```

Then open:

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |
| API docs (ReDoc) | http://localhost:8000/redoc |

The `backend` service runs `alembic upgrade head` before starting uvicorn, so the schema is migrated automatically on every `up`. If a migration fails the container exits rather than serving against an out-of-date schema.

To stop and remove the Postgres/Redis volumes:

```bash
docker compose down -v
```

> **Note:** `docker-compose.yml` sets `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `JWT_SECRET_KEY`, `DEBUG`, `TOKEN_ENCRYPTION_KEY` and `FRONTEND_URL` inline for the backend services, so the stack boots without a `.env`. Those inline values are development placeholders — in particular `DEBUG=true`, which is what allows the placeholder secrets to be used at all. Any other variable — AI provider keys, Stripe, OAuth credentials — must be added to the compose environment or the service will run with that feature disabled.

---

## Running locally without Docker

You need Python 3.11+, Node 18+, a PostgreSQL 15 instance, and (optionally) Redis.

**Backend**

```bash
cd backend
python3.11 -m venv venv
source venv/bin/activate          # Windows: .\venv\Scripts\activate
pip install -r requirements.txt

# Configure the environment (from the repository root):
cp .env.example .env              # set DATABASE_URL to your Postgres instance

# Create the empty database, then apply migrations:
createdb marketengine             # migrations create tables, not the database
alembic upgrade head

# Optional: load sample data (deletes existing data)
python scripts/seed.py

uvicorn app.main:app --reload --port 8000
```

**Frontend**

```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

The Vite dev server proxies `/api` to `http://localhost:8000`. To point the frontend at a different backend, set `VITE_API_URL` in `frontend/.env`:

```
VITE_API_URL=http://localhost:8000/api/v1
```

Windows users can use the bundled `start.bat` / `start.ps1` helpers, which launch both servers.

---

## Environment variables

All backend configuration lives in **`.env` at the repository root** — that is where `backend/app/core/config.py` looks for it. Copy the template and fill it in:

```bash
cp .env.example .env
```

[`.env.example`](.env.example) lists every variable the backend reads, with placeholder values and notes on which are required. `.env` is gitignored; `.env.example` is committed and must never contain a real credential.

Only four variables are needed for a local run:

| Variable | Purpose |
|---|---|
| `DEBUG` | Set `true` locally. With `DEBUG=false` the app refuses to start while the JWT secrets are still placeholders. |
| `DATABASE_URL` | Postgres connection string; must use the `postgresql+asyncpg://` driver. |
| `SECRET_KEY` | Application signing secret. |
| `JWT_SECRET_KEY` | Signs access and refresh tokens. |
| `TOKEN_ENCRYPTION_KEY` | Fernet key encrypting stored platform credentials. Required when `DEBUG=false`; derived from `SECRET_KEY` in development if unset. |

Everything else is optional — an unset AI, Stripe, S3, email, or OAuth variable disables that feature rather than breaking startup.

Frontend variables are separate: Vite reads `VITE_`-prefixed values from `frontend/.env` at build time. Only `VITE_API_URL` is currently used.

---

## Rate limiting

Authentication and AI generation endpoints are rate limited with [slowapi](https://github.com/laurentS/slowapi). Counters live in Redis (`REDIS_URL`) so a limit holds across every worker and instance.

| Endpoint | Limit | Keyed on |
|---|---|---|
| `POST /auth/login` | 5 / minute | client IP |
| `POST /auth/login` | 10 / hour | email address |
| `POST /auth/login/2fa` | 15 / minute | client IP |
| `POST /auth/register` | 5 / hour | client IP |
| `POST /auth/forgot-password` | 3 / hour | client IP + email |
| `POST /accounts/{id}/ai/*` | 20 / hour | user |

Exceeding a limit returns **429** with a `Retry-After` header. The AI limit is keyed on the user rather than the IP, so a shared office address does not throttle a whole team.

These are an abuse backstop, not a billing control — they reset on their own and are per-process without Redis. What a plan actually allows is enforced separately by [entitlements](#entitlements), which is what returns **402**.

> **Behind a proxy, uvicorn needs `--proxy-headers` *and* `--forwarded-allow-ips`.** Otherwise every request appears to come from the proxy's address, all clients share one bucket, and normal traffic trips the per-IP limits within seconds — five bad logins from anyone would lock out the whole user base.
>
> `--proxy-headers` alone is not enough: uvicorn only honours `X-Forwarded-For` when the *immediate peer* is listed in `--forwarded-allow-ips`, which defaults to `127.0.0.1`. On Render (and in any container setup) the platform proxy connects from a non-local address, so the header is ignored and you are back to one shared bucket. Verified: with a non-matching `--forwarded-allow-ips`, six requests carrying six different `X-Forwarded-For` values were counted against a single bucket and the sixth was refused.
>
> The Dockerfiles and compose command pass `--proxy-headers --forwarded-allow-ips='*'`. Trusting any peer is safe when only the platform's proxy can reach the port, which is the case on Render — do not expose the container directly to the internet with that setting.
>
> **If the service is started some other way — a start command configured in a hosting dashboard, for example — those flags must be added there too**, or the per-IP limits behave as a single global limit.

If Redis is unreachable the limiter falls back to in-process counters and logs a warning (an error outside `DEBUG`). Nothing breaks, but limits then apply *per worker* rather than globally, which is materially weaker — treat that log line as a production alert.

### 2FA challenge hardening

The short-lived challenge token issued between the password step and the TOTP step carries a `jti` and has matching server-side state, so it is:

- **single-use** — consumed on a successful sign-in and rejected on replay, and
- **attempt-capped** — 5 wrong codes per challenge, after which that challenge is refused with 429 and the user must sign in again.

The per-IP limit on `/auth/login/2fa` is deliberately looser (15/minute) than the 5-attempt cap, so the cap is the binding constraint on guessing. When both were 5, the IP limit fired first and the per-challenge cap never got to act — and a user who mistyped their code five times was blocked for a full minute even after signing in again for a fresh challenge.

Without these a captured challenge token was replayable until expiry and allowed unlimited guesses at a six-digit code. This state also uses Redis, with the same per-process fallback.

---

## Credential encryption

Social-platform credentials (`api_key`, `api_secret`, `access_token`, `refresh_token` on `social_accounts`) are encrypted at rest with Fernet, so a database dump or replica does not expose every connected account's tokens.

This is transparent to application code: the columns use an `EncryptedText` type that encrypts on write and decrypts on read, so the ORM only ever sees plaintext. Because the stored form is ciphertext, these columns **cannot be filtered, sorted, or indexed on in SQL** — anything needing that must load the row and compare in Python.

Generate a key per environment:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set it as `TOKEN_ENCRYPTION_KEY`. Production (`DEBUG=false`) refuses to boot without one. In development it may be left blank, in which case a key is derived from `SECRET_KEY` — a convenience for local work, never a security control.

> **Treat the key as long-lived and back it up with your other secrets.** Changing it makes every stored credential undecryptable and the affected accounts must reconnect. There is no automatic re-encryption path.

Databases that predate this feature are converted by migration `aeed3c1c5c4e`, which encrypts existing plaintext rows. It is idempotent — values that already decrypt cleanly are skipped — so re-running it is safe.

---

## Database migrations

The schema is managed by [Alembic](https://alembic.sqlalchemy.org/). Migrations live in `backend/alembic/versions/`, and `alembic/env.py` reads `DATABASE_URL` from `app.core.config.settings` — the same value the application uses — so there is no separate database URL to keep in sync.

Run all Alembic commands from the `backend/` directory.

**Apply migrations** (safe to re-run; a no-op when already current):

```bash
cd backend
alembic upgrade head
```

**Create a migration** after changing a model:

```bash
alembic revision --autogenerate -m "short description"
```

Autogenerate compares the models against the live database, so the database must be at `head` first. Always read the generated file before committing it — Alembic does not detect every change (notably table and column renames, which it sees as a drop plus an add).

**Other useful commands:**

| Command | Purpose |
|---|---|
| `alembic current` | Show the revision the database is on |
| `alembic history` | List all migrations |
| `alembic check` | Report whether models and database have diverged |
| `alembic downgrade -1` | Roll back one migration |

### Existing databases created before Alembic

A database created by the old `init_db` / `migrate_db.py` path already contains every table in the baseline migration, so `alembic upgrade head` would fail with `relation already exists`. Record it as already at the baseline instead, which writes to `alembic_version` and runs no DDL:

```bash
cd backend
alembic stamp head
alembic check        # should report no changes
```

If `alembic check` does report differences, the database drifted from the models under the old ad-hoc scripts. Reconcile it before relying on autogenerate — otherwise the next autogenerated migration will contain those unrelated corrections. Fresh databases need none of this; just run `alembic upgrade head`.

> **Alembic is the only thing that creates schema.** The application performs no DDL at startup: `init_db()` in `app/core/database.py` only waits for the database to accept connections. It previously ran `Base.metadata.create_all()` plus ad-hoc `ALTER TABLE ... IF NOT EXISTS` statements, which meant a model change could reach a database without a migration. If you change a model, you must generate a migration — nothing else will apply it.

## Media library

Uploads used to land in a single `uploads/` directory, be referenced by URL strings in `Post.media_urls`, and be tracked by nothing. Nobody could tell what a workspace was storing, whether a file was still in use, or how much of its allowance it had spent — `storage_bytes` was an entitlement that always reported zero because nothing counted anything.

Files now go **straight to object storage**. The client asks for a presigned URL, PUTs to it, then tells us it landed; the API never carries the bytes, which is what makes a large upload possible without holding a worker for its duration.

```
POST /media/presign   validate the claim  →  presigned PUT URL + server-generated key
        ↓ (browser PUTs directly to S3, no Authorization header)
POST /media/confirm   verify what landed  →  Media row
```

**Validation is deliberately split across those two calls.** Presign can only check what the client *claims* — declared type, declared size, remaining storage. Confirm checks what actually arrived: that the object exists, its real size from `head_object`, and its real format from the leading bytes via a ranged GET. A client that declares a small PNG and uploads something else is caught at confirm, and no row is written — so a lie produces an orphaned object rather than a library entry. Image dimensions come from that same ranged prefix (Pillow parses headers lazily), never a full download.

The storage limit is checked twice for the same reason: once at presign so the user is refused before spending minutes uploading, and again at confirm against the *measured* size. An upload that clears the first check and fails the second has its object deleted rather than left unreferenced in the bucket.

Accepted types are narrow on purpose — every one is identifiable from its magic number, which is what makes the confirm-time check meaningful. **SVG is excluded**: it is a document format that executes script, and it was removed from the old upload endpoint for that reason.

**Deletion is always soft.** A file a post points at is never removed outright — the object stays so the post's history keeps working, and the response says so rather than letting "deleted" mean two different things. `PostMedia` is what makes that possible: without it, "is this still in use?" could only be answered by string-matching URLs, which misses a file behind an expired presigned link and cannot tell a library file from a pasted external one.

**Without an S3 bucket**, a `LocalStorageBackend` keeps development working through the same interface — it hands back a URL to a signed shim on this API, so the *client* flow is byte-identical to production. That matters: a dev path that differs from production is a dev path that hides bugs. It refuses to run outside `DEBUG`, because writing user media to a container filesystem looks like it works right up until the next deploy throws it away. The shim's HMAC is not decoration — without it, the endpoint would accept a PUT to any path a caller invents.

Storage config lives in `S3_BUCKET` / `S3_REGION` / `S3_ACCESS_KEY` / `S3_SECRET_KEY` / `S3_ENDPOINT_URL`. `BACKEND_URL` is only used by the local fallback.

## Connection health

A social connection degrades silently: the token has an expiry nobody watches, or a customer revokes access in the platform's own settings. The first anyone hears is a scheduled post failing at 9am with an auth error, by which time the slot is gone.

An hourly sweep inside the worker loop computes `CONNECTED` / `EXPIRING` / `FAILED` / `UNKNOWN` per account, tries to refresh what it can first, and persists the result. `UNKNOWN` is deliberate: a connection nobody has checked is not the same as a healthy one, and defaulting to `CONNECTED` would be a clean bill of health nobody issued.

**Notification is once per state change, not once per sweep.** An hourly reminder that the same account is still broken is how people learn to filter the notification out — and then the one that matters gets filtered too. Only members with `accounts.manage` are told, since reconnecting requires it and telling a contributor is asking them to forward it.

**A live 401 beats expiry arithmetic.** The publish path marks an account `FAILED` directly when a platform rejects the credentials, rather than waiting up to an hour for the sweep to agree. The match is deliberately narrow — a timeout or a 429 is not an auth failure, and marking an account broken on one would send a false alarm.

**Reconnecting updates the row in place.** The OAuth authorize endpoints accept `?reconnect=<social_account_id>`, carried through the signed state to the callback. Without it a reconnect creates a *second* `SocialAccount` and orphans the first one's history — every post's `target_accounts` entry, every `PublishingJob`, every `PostPerformance` row keyed on it. The workspace ends up with two entries for one page: one with all the history, one with the working credentials. Reconnecting also skips the plan's connection cap, since it adds no connection and a workspace at its limit must still be able to fix a broken account.

## Dashboard

`GET /accounts/{id}/settings/dashboard?range=today|yesterday|7d|30d|90d|custom&from&to` returns every widget in one payload — connected accounts with health, post counts, pending approvals, engagement totals, followers, top posts and recent activity.

One call rather than six, so the widgets cannot disagree about what the selected range means, and the page costs a fixed number of queries regardless of how much content the workspace holds. Each widget is one aggregate query; the post counts are conditional aggregates in a single pass rather than four round trips over the same rows.

**Ranges resolve in the workspace's timezone**, read from `settings.timezone` (defaulting to UTC). "Today" for a team in Sydney is not the same fourteen hours as "today" in UTC, and a dashboard quietly using the server's clock shows an agency the wrong day's numbers every morning. Windows are half-open, so a post published at exactly midnight belongs to one day rather than two. An unrecognised timezone falls back to UTC with a log line rather than failing the page.

Two deliberate exceptions to the range: **pending approvals** and **recent activity** ignore it. A post submitted three weeks ago is still waiting, and hiding it because it falls outside "last 7 days" is how an approval queue silently grows.

**Follower growth returns `null`, not `0`, until daily snapshots exist** (`analytics_daily`, see [Analytics](#analytics)). Zero means "no change measured"; null means "not measured", and a flat 0% would be a claim the data cannot support. `engagement_rate` is null for the same reason when there is no reach to divide by — 0% reads as "bad", not "no data". It is computed against reach rather than impressions, since reach is people and impressions counts the same person twice.

## Analytics

Four views over one window: `GET /accounts/{id}/analytics/{summary,platforms,posts,audience}`. All
four take the same `range=today|yesterday|7d|30d|90d|custom&from&to` parameters as the dashboard and
resolve them through the same code, so the analytics page and the dashboard cannot disagree about
what "last 30 days" means. Add `&format=csv` to any of them to get the same query as a download.

### Where the numbers come from

`analytics_daily` holds one row per social account per day, unique on `(social_account_id, date)`. A
nightly pass in the worker asks each connected account's provider for `get_analytics()`, upserts the
day, refreshes per-post metrics for the last 30 days, and prunes history. The sync retries a
`PlatformRateLimited` up to three times with exponentially backed-off, fully jittered delays; other
provider errors are logged and skipped, so one broken connection does not cost the workspace its
whole night's data.

The upsert writes **only the metrics actually present in the response**. A partial re-run — a
provider that answered for followers but rate-limited on insights — therefore cannot erase what an
earlier run stored.

### Null is not zero

Every metric column is nullable, and null means *this platform does not report it*. What each
provider genuinely returns:

| Platform | Reports |
|---|---|
| Facebook | followers, impressions, profile visits |
| Instagram | followers, following, posts, reach, impressions, profile visits |
| LinkedIn | followers (organization pages only) |
| X | followers, following, posts — reach and impressions need a paid tier |
| YouTube | followers, posts, video views |

Storing an unreported metric as `0` would put a real, flat, wrong line on a chart and drag every
cross-platform average down by the platforms that were never measured. Totals with no contributors
stay null, CSV exports write an empty cell rather than the string `None`, and the UI renders an em
dash.

`engagement_rate` is interactions over reach, and is null in **both** directions of that division:
no reach to divide by, *or* no interaction metric reported at all. The second case is the one that
bites — a workspace connected only to X and LinkedIn has real reach and an entirely unmeasured
numerator, and coalescing those nulls to zero produced a confident `0.0%` for a workspace with
61,000 reach. 0% reads as "your content is failing"; null reads as "not measured". A *partially*
reported numerator is summed with the absent parts as zero, since a platform that reports likes but
has no "saves" concept genuinely contributed no saves.

### Cumulative metrics are never summed

`followers`, `following` and `posts_count` are running totals, not daily amounts: 1,000 followers on
Monday plus 1,010 on Tuesday is not 2,010. Aggregates take the latest value per account in the
window, and growth is last-minus-first. Everything else in `METRIC_FIELDS` is a daily amount and is
summed normally. `CUMULATIVE_FIELDS` in `app/models/analytics_daily.py` is the single list both
rules read from.

Deltas against the preceding window return null — rendered as a dash — rather than a number whenever
either side is missing or the previous value was zero. "Up 100%" measured against a period with no
data is a fabrication, and growth from zero has no percentage.

### Retention

Pruning is per organization, from the `analytics_history_days` entitlement, with a seven-day floor
so a misconfigured plan cannot delete a workspace's entire history. A plan with no limit set keeps
everything. Because limits live on the *plan*, two workspaces on the same tier necessarily share a
retention window; a paying workspace keeps more than a free one by being on a different plan.
### Suggested posting times

`GET /analytics/best-times` returns a weekday × hour heatmap and the top three
slots; `/best-times/next` returns those slots as concrete upcoming datetimes so
a chip can fill the scheduler without the browser doing weekday arithmetic in
its own timezone.

This replaced a heatmap drawn from `Math.random()` captioned with a fabricated
"22% uplift". Everything about the design follows from not doing that again:
**the payload carries a `source` of `observed` or `default`, and every cell
carries `observed`**, so a reader can always tell a measurement from a
convention. The UI renders the three states differently — a tinted cell, a blank
one, and a dimmed grid with a caption — rather than leaving it to be inferred.

**Where the numbers come from, and where they do not.** `analytics_daily` stores
a date and no hour, so it cannot say anything about time of day and is not
consulted. The dataset is `Post.published_at` joined to `post_performance`.
Attribution is per connected account, not merely per platform: posts are
filtered by the connection in `target_accounts` *and* by the performance row's
`platform_type`, so a post sent to Instagram and Facebook contributes its
Instagram numbers to the Instagram account only.

**Two thresholds.** Below twelve measured posts in the window the account's own
history is anecdote rather than evidence — three posts that happened to land on
a Tuesday would otherwise make Tuesday the recommendation forever — so the
platform's usual times are shown instead, labelled as such. And a single cell
needs at least two posts before it counts as measured rather than noise, so one
spectacular post cannot become a recommendation.

**Ranking is by average, not total.** A slot used twenty times out-totals a
better one used twice, and the question is where the next post should go, not
where most have gone.

**A slot never tried scores null, not zero.** Zero would say "we posted here and
nobody engaged", which is a different and false claim — so those cells render
blank rather than dark, since dark reads as "tried and failed".

Hours are on the workspace's clock: "post at 9am" means 9am where the audience
is. The slot-to-datetime conversion goes through the same resolution recurring
schedules use, so a suggestion inside a spring-forward gap lands on an instant
that exists.


### Tested on Postgres, not just SQLite

`tests/test_analytics_postgres.py` executes each of the four query functions against a real
Postgres, and skips when none is reachable. It exists because the suite's in-memory SQLite harness
accepts SQL that Postgres rejects: the posts query originally rounded a `double precision`, which
SQLite computes happily and Postgres refuses outright — there is only `round(numeric, int)`. All 600
tests passed while `/analytics/posts` was a hard 500 in production. The file asserts almost nothing
about the numbers; it exists to prove the SQL runs at all on the database the product ships on.

### The page

`/analytics` has four tabs — Overview, Platforms, Content, Audience — sharing the range picker at the
top and each with its own CSV button that exports exactly the query on screen, sort order included.
Content sorts server-side rather than in the browser, since the table shows a capped number of rows
and re-sorting the fetched page would reorder a slice instead of finding the actual top posts.


## Workspace settings

`GET`/`PUT /accounts/{id}/settings/`. The `settings` JSON blob holds per-workspace
preferences that do not each deserve a column:

| Key | Drives |
|---|---|
| `timezone` | Every date range on the dashboard and analytics |
| `approvals_required` | Whether the review workflow is on |
| `client_approval_required` | Whether approval also needs client sign-off |

Unknown keys inside the blob are stored untouched — it is a deliberate extension point for
client-side preferences. The three above are type-checked and, for `timezone`, validated against
the IANA database and stored stripped, because a value that reads back wrong later is the same
failure as one that was never written.

**Unknown keys at the *top* level are a 422, not a silent 200.** `{"timezone": "..."}` is a
plausible mistake — the key is real one level down — and Pydantic's default is to ignore extras.
A write that reports success and changes nothing is indistinguishable from one that worked.

### The JSON-column trap

The merge builds a **new** dict:

```python
account.settings = {**(account.settings or {}), **body.settings}
```

It previously mutated the loaded dict in place and assigned it back to itself. SQLAlchemy decides
whether to emit an `UPDATE` by comparing an attribute's before and after values; here they were the
same object, so `history.has_changes()` was `False` and the flush wrote nothing. The endpoint
returned 200 carrying the old values. A plain `JSON` column has no change tracking of its own —
only a fresh object is visible as a change. (`MutableDict.as_mutable(JSON)` is the other fix; a new
dict per write is less machinery and harder to get subtly wrong.)

Two things hid this. No test had ever called the endpoint and the frontend does not use it, so the
only exercise it got was manual. And on a *fresh* workspace `settings` is NULL, so `or {}` produced
a new dict and the write landed — the bug only appeared on the second write, which means a
per-field round-trip test against an empty blob passes against the broken code.
[test_settings_writer.py](backend/tests/test_settings_writer.py) therefore seeds a non-empty blob
in its fixture, and every round trip re-reads through a separate `GET` rather than trusting the
`PUT`'s own reply, which renders from the in-memory object.

The cost was not hypothetical: `approvals_required` lives only on this blob and is written only by
this endpoint, so while the writer dropped its input the review workflow could not be switched on
through the API at all.


## Recurring schedules and the posting queue

Two ways to publish without picking a date each time. A **recurring schedule**
repeats one template post on an RRULE; the **queue** is a weekly set of slots that
different posts drop into. Endpoints live under
`/api/v1/accounts/{id}/scheduling/`.

### Everything is stored as local wall-clock time

This is the design, and daylight saving is the reason. "Every Monday at 10:00"
means 10:00 on the workspace's clock, and the UTC instant that corresponds to it
moves by an hour twice a year. A schedule kept as "this UTC instant plus 604800
seconds" is correct for about five months and then publishes at 09:00 or 11:00
for the rest of the year — a drift nobody reports as a bug, because it looks
like the product is simply unreliable.

So a `RecurringSchedule` stores an RRULE, a timezone name and a **naive** local
start. `next_run_at` is UTC because the worker compares it to `now()`, but it is
*recomputed from the rule* after every run, never advanced by adding an interval.
All recurrence arithmetic happens in naive local time and is converted to UTC
exactly once, at the end. Queue slots follow the same rule: weekday plus local
time, resolved per occurrence.

Verified against a New York workspace over a window straddling the November
transition: local time stays `10:00` throughout while the UTC instant moves from
`14:00` to `15:00`.

### The two local times that are not ordinary

| Case | What happens | Policy |
|---|---|---|
| **Nonexistent** — 02:30 on a spring-forward date, when the clock jumps 02:00 → 03:00 | The reading never occurs | Publish at 03:00, an hour late once a year |
| **Ambiguous** — 01:30 on a fall-back date, which happens twice an hour apart | Two candidate instants | Take the first |

Skipping the nonexistent occurrence was the alternative, and it is worse: a
weekly post would silently vanish one week a year, and silence is a harder
failure to notice than an hour's delay. Publishing at both ambiguous instants
would post the same content twice, which the customer's audience sees.

`zoneinfo` implements both through `fold=0`, so the code relies on that rather
than reimplementing it, and detects the two cases only in order to report them —
the UI labels a slot that will shift, and the occurrence preview shows the UTC
offset so a transition is visible rather than looking like a bug.

There is one more guard worth naming. Asking for "the next occurrence after
06:00 UTC" on a fall-back date converts that reference to 01:00 local — a
reading that already happened an hour earlier — and the rule's next answer,
01:30 local, converts back to an instant *before* the reference. Returned as-is,
the worker would see a due instant in the past, publish, store the same
`next_run_at`, and publish again on the next pass. `next_occurrence` therefore
requires the UTC value to move strictly forward.

### Each occurrence is its own post

A run copies the template into a new post rather than republishing the template.
One row cannot hold two statuses, two `published_at` times, two permalinks or
two sets of performance rows, so pointing jobs at the template would mean every
run overwrote the last and a weekly post's history collapsed to a single row.
The template is never published; it stays a draft.

Copying goes through `app/services/post_cloning.py`, which derives the fields
from the table and excludes per-occurrence state. The endpoint's previous inline
duplicate listed thirteen fields by hand, so it silently dropped the
per-platform settings added in 1.7 and every `PostVariant` row — a duplicated
Reel came back a plain feed post. Both paths now use the one implementation.

A worker that has been down does **not** flush its backlog: missed occurrences
are skipped and `next_run_at` moves to the next future one. Emptying a week of a
daily schedule into a single minute is worse for the customer than the gap it
repairs.

### The queue

Slots are a weekday and a local time, saved as a whole week rather than
individually — a half-applied change would leave a workspace posting at times
nobody chose. "Add to queue" places a post in the next slot that is both in the
future and unoccupied; drafts do not occupy slots, since they have no scheduled
time. A full queue and an unconfigured one raise different errors, because one
is a capacity problem and the other is a setup step.


### Scheduling a single post

`POST /posts/{id}/schedule` takes exactly one of:

* `scheduled_at_local` — a wall-clock reading on the **workspace's** clock,
  `2026-03-09T10:00:00`, with no offset. This is what a person means when they
  pick a time, and what the composer sends.
* `scheduled_at` — an absolute instant, which must carry an offset.

A naive `scheduled_at` is refused rather than assumed to be UTC. The composer
previously built its instant with `new Date(...)` in the browser, so the time
someone typed was read in whatever timezone their laptop was in: an agency in
London scheduling for a Sydney client set a time eleven hours out, and the error
moved by an hour whenever either side's clocks changed. The display path had the
same fault in reverse — a post set for 10:00 Sydney rendered as 23:00 to a
London viewer, and saving that form back wrote 23:00 Sydney — so both directions
read and write on the workspace's clock now, and the composer labels which clock
that is.

Local readings go through the same resolution as recurring schedules, so a time
inside the spring-forward gap lands on the first instant that exists rather than
failing, and the two features cannot disagree about what a wall-clock time means.

### Post writes refuse unknown fields

`PostCreate` and `PostUpdate` set `extra="forbid"`. Pydantic's default is to
drop unknown keys, so a request naming a field the schema does not have returned
200 having stored nothing — the settings-writer bug one level up, at the
contract.

That leaves one legitimate casualty, which is why `target_accounts` is accepted
as an alias for `target_account_ids`: the response returns the former and writes
take the latter, so reading a post, editing it and sending it back — the
ordinary way to use an API — would otherwise be rejected. Naming both at once is
an error rather than a guess, since guessing is how a post publishes to the
wrong account.

## Bulk import

`POST /accounts/{id}/posts/bulk-import` takes a CSV with the columns `content`,
`scheduled_at`, `platforms`, `media_urls` and `link`. Only `content` is
required; a row with no date imports as a draft.
`GET .../bulk-import/template` returns an example file.

### Two phases, and the first writes nothing

The default is a dry run: it parses the file, validates every row, and returns
a per-row report having created nothing and spent no quota. Sending the same
file with `confirm=true` creates the rows that passed. No server-side session
is held between the two — the client re-sends the file — so a stale preview
cannot be confirmed against a file that has since changed.

A spreadsheet of fifty posts is exactly the input where a column is misnamed or
a platform misspelt, and discovering that after fifteen rows have been created
leaves a mess only the user can untangle.

### Rows fail individually; the file fails as a whole

A bad row is reported and skipped, and the rest import. Refusing forty-nine good
rows over one bad one is not a service, and the report has already shown the
user exactly which failed and why. A *missing column*, by contrast, fails the
whole file: that is one mistake, not fifty.

Every error names a field and says what to do instead — `'tomorrow-ish' is not
a date and time we recognise. Use YYYY-MM-DD HH:MM` — because a row number and
a shrug is not a report.

### Validation is the composer's own

Each row is turned into an **unsaved** `Post` and passed to
`post_validation.validate_post`, the same function the composer calls. An import
therefore cannot accept content the composer would reject, and the two cannot
drift. Advisory problems (a missing alt text) come back as warnings and do not
block the row.

### One atomic reservation

Monthly quota is taken once, for the whole importable set, before anything is
created:

```python
await enforce_post_limit(db, account_id, adding=report["importable"])
```

Not a loop of single increments. Fifty separate calls let a concurrent import
interleave and carry a workspace past its allowance, and leave a partial spend
behind if the run fails halfway. Because the guard lives in the UPDATE's `WHERE`
clause, an over-limit reservation is refused whole: nothing is created and
nothing is spent, so the next, smaller import still fits.

Rejected rows are not charged.

### Details that came from using it

* Times in the file are read on the **workspace's** clock, not the server's or
  the uploader's — the same contract the composer and recurring schedules use.
  A spreadsheet has no notion of timezone, so reading its times as UTC would
  silently move every import for any workspace outside UTC.
* The file is decoded as `utf-8-sig`, because Excel writes a byte-order mark and
  without it the first column arrives named `\ufeffcontent` and every row looks
  like it is missing its text.
* Headers match case- and space-insensitively, since a spreadsheet round trip
  turns `scheduled_at` into `Scheduled At`.
* List columns accept `|` or `;` as well as `,` — a comma inside a CSV cell is a
  fight nobody should have to win.
* The template is **generated**, with dates a few days out and the platforms the
  workspace has actually connected. The first version had fixed dates, so
  downloading it and uploading it straight back — the obvious first thing to try
  — failed every row on "that date is in the past". A test now requires the
  template to import cleanly as its own input.

## AI writing assists

Five operations on the author's own text, under `/accounts/{id}/ai/`:
`rewrite`, `shorten`, `expand`, `change-tone` and `suggest-hashtags`, plus
`GET /assist-options` describing what the server will accept.

They sit on the existing AI router, which carries `meter_ai_request` as a
router-level dependency — so every one is charged against
`ai_requests_per_month` before a provider is reached, and adding a sixth assist
cannot accidentally ship unmetered.

### Failures are failures

The older `/generate-content` endpoint catches a provider error, substitutes
mock text with the exception message interpolated into it, and records the row
`COMPLETED`. That puts an internal error string into the user's post and leaves
the usage log unable to answer "how often does this break".

The assists do the opposite: a provider error marks the `AIGeneration` row
`FAILED` with the exception, and returns **502** with a message that says the
text has not been changed. The composer then leaves the author's writing alone —
which is the contract its undo depends on. (The older endpoint's behaviour is
recorded in the walkthrough defect log rather than changed here.)

### A named provider is honoured or refused

`provider` accepts `openai`, `anthropic` or `gemini`. One that is not
configured on the deployment is a **400 naming what is configured**, never a
silent swap: being quietly answered by a different model than you asked for is
indistinguishable, from the outside, from the requested one behaving oddly.
Omitting it uses whichever is configured, and a deployment with no keys at all
falls back to a local mock so the composer is usable in development.

### Tone is an enum

The tone value is interpolated into the system prompt, so it is a closed set —
`professional`, `casual`, `friendly`, `witty`, `authoritative`,
`inspirational`, `urgent`, `empathetic`. An open string there is an
instruction-injection hole, and "make it sound like X" where X is a paragraph of
the caller's choosing is not a tone control.

### Platform awareness

`platform` does two things. It puts the platform's character limit into the
prompt, taken from the same connector capabilities the 1.7 validator uses — an
assist that returns text the composer immediately marks invalid has wasted the
author's time *and* a metered request. And it sets the hashtag count and
register: twelve on Instagram, four on LinkedIn, two on X. The same list on both
reads as under-tagged in one place and as spam in the other.

When several platforms are targeted, the composer aims the assist at the
**tightest** one. A rewrite that fits X fits everywhere; one that fits Instagram
is 1,900 characters too long for X.

### Hashtag parsing

Models drift between a JSON array, a comma list, a newline block and a fenced
code block, so all four are accepted — failing over formatting would spend the
allowance for nothing. What is *not* accepted is prose: a model that declines
("I'm sorry, I can't help with that.") splits into chunks that clean up into
plausible-looking strings, and returning `imsorry` as a hashtag is worse than
returning nothing. Chunks with contractions, or longer than three words, are
rejected; if nothing survives the caller gets "no usable hashtags", which is the
honest answer. It is a heuristic and will not catch a one-word refusal — the
alternative is refusing legitimate multi-word tags, which would cost users more
often than this costs them.

### The composer menu

An "AI assist" dropdown on the content field, applying results **in place with
undo**. The previous text is kept and one click restores it, because an assist
that replaces your writing with no way back is one people are afraid to press.

Nothing fires on its own — no assist on blur, on debounce or on mount. Every
call is metered, so every call is one the author asked for by name, and the menu
says so.

## Reports

`POST /accounts/{id}/reports/` queues one; the worker generates it; `GET
.../{id}/download?format=pdf|csv|xlsx` hands back a short-lived presigned URL.
Weekly, monthly, quarterly or a custom span.

**202, not 201.** The row exists, the files do not yet. Generating inline would
hold the connection through an aggregation and three renders, which dies behind
a proxy on any period worth reporting on. The page polls, and stops polling
when nothing is building.

### The period is fixed when the report is created

Stored as two dates on the row, never recomputed. "Last month" evaluated at read
time answers a different question every month, so a report titled *August*
downloaded in December would silently re-aggregate as November — the numbers
under a constant title would change.

It is also always the **last complete** period. A monthly report generated on
the 3rd that covers three days is a number nobody asked for, and it would change
if regenerated. Periods resolve on the workspace's clock, so *September* means
September on the customer's calendar.

### The numbers are the analytics page's numbers

`reporting.aggregate` is built on `analytics_query`, not beside it. An agency
that screenshots the dashboard and emails the PDF is the whole point of the
feature, and two implementations of "sum the reach" is how those two numbers
drift apart. The null discipline survives into the documents: an unreported
metric is an em dash in the PDF and an **empty cell** in the CSV and workbook,
never a zero and never the string `None`.

Excel writes numbers as numbers. A formatted string would make every column sort
alphabetically and every `SUM` return zero — the first thing a spreadsheet user
tries.

### One format failing does not fail the report

PDF needs WeasyPrint, which needs **pango** at the system level (`brew install
pango`; `libpango-1.0-0` and `libpangoft2-1.0-0` on Debian). A host without it
still produces CSV and Excel: the format is simply absent from `file_keys`,
which is the honest record of what happened, and the row carries a note saying
which formats were unavailable. Only if *every* renderer fails does the report
fail. The PDF test skips rather than fails when the library is missing, the same
convention as the Postgres-gated suites.

### White-label

`branding` carries a company name, logo URL, two colours and a footer note,
gated by the `white_label` entitlement.

It is resolved **once, at creation, and frozen on the row**. A customer who
rebrands should not find last quarter's PDF has changed colours, and one whose
plan lapses should not retroactively lose branding from a file they already had.

Without the entitlement the customer's branding is *stored but not applied*, and
the settings endpoint returns both `branding` (what is saved) and `effective`
(what a report would use today) so the difference is visible rather than
mysterious. That is a fallback rather than an error on purpose: a hard failure
at the plan boundary would mean a scheduled report silently stops arriving the
month a plan changes.

Values are sanitised before they reach the template — hex colours only, `http(s)`
logo URLs only, unknown keys dropped — because the document is rendered from an
HTML template and sent to the workspace's own clients. Post titles are
autoescaped for the same reason.

### Scheduled reports

A workspace sets `reports_cadence` to `off`, `weekly` or `monthly`, beside the
timezone and approval flags on its settings blob. The worker queues one when the
period has closed.

Idempotent **by period**, not by a stored `next_run_at`: "has a monthly report
for August already been made?" is a question the reports table answers exactly,
while a next-run timestamp can drift, be missed while a worker is down, or fire
twice after a restart — and each of those puts a duplicate in front of a
customer. A workspace younger than the period is skipped; there is nothing to
report on before it existed.

A "report ready" notification goes to whoever asked, or to the workspace owner
for a scheduled one. Not to every member: telling five people the monthly report
exists is how people learn to ignore notifications.

## Campaign performance

`GET /accounts/{id}/campaigns/{campaign_id}/performance` is the analytics page's
data narrowed to one campaign: totals, progress against schedule, a per-platform
split, and top posts. It is gated on `analytics.view` rather than on campaign
access, because reading the workspace's numbers one campaign at a time is still
reading them.

### What a campaign can and cannot be credited with

`post_performances` is the only table with a campaign dimension, reached through
`posts.campaign_id`. Everything on the dashboard is built from it.

`analytics_daily` — followers, account-level reach, audience demographics — is a
**per-connection daily snapshot that does not know which campaign was running**.
Filtering it by campaign would mean inventing attribution, so those figures are
absent from the dashboard and from campaign reports rather than approximated.
The payload carries a `not_attributable` note saying so, and the UI prints it,
because a missing follower count otherwise looks like a bug rather than a
refusal.

One limitation is stated in the module because it is invisible otherwise:
`PostPerformance` columns are `NOT NULL DEFAULT 0`, so a platform that reports
nothing is stored as `0` and cannot be told apart from one that reported zero.
The module does not pretend to recover that distinction. What it does do is
refuse to divide by an unmeasured denominator — an engagement rate with no reach
is null, not `0.00%`.

### The window is the campaign's own

Campaign dates are calendar dates **on the workspace's clock**, so a campaign
running the 10th to the 20th for a Sydney workspace does not start at 00:00 UTC.
A missing `start_date` means "since it was created"; a missing `end_date` means
"still running", and an open-ended campaign has *no* elapsed fraction — its
window ends now, so a percentage would always read 100%. Null there, not 100.

Posts are also bounded by that window. A post attached to a campaign long after
it ended is not part of what the campaign did, and counting it would let a
finished campaign's numbers keep moving.

### Reports delegate rather than re-implement

`POST /accounts/{id}/campaigns/{campaign_id}/report` queues an ordinary report
with a `campaign_id` — same statuses, formats, downloads, retention and
entitlement meter as every other report. Routing around the meter by going via a
campaign would make the entitlement meaningless.

The period is the campaign's span **at the moment of the request**, stored on the
row. An open-ended campaign otherwise gets a report covering a different window
each time it is regenerated, and a client's second copy would not match their
first. `reports.campaign_id` is `ON DELETE SET NULL`: deleting a campaign must
not delete a report a client has already been sent.

Top posts come from `analytics_query.posts` with a campaign filter rather than a
query of their own, so a post's numbers on a campaign dashboard are the numbers
the analytics page shows for that post.

## Unified inbox

Comments, direct messages and mentions from every connected account, under
`/accounts/{id}/inbox/`. Threads carry a status, an assignee, tags and internal
notes; replies go back out through the provider.

### Built on the connector abstraction

Nothing here knows a platform's vocabulary. Providers gained `get_comments`,
`get_messages`, `get_mentions`, `reply_to_comment` and `send_message`, each
returning a common shape, and the sync only ever speaks that shape.

Mentions are a separate capability from comments, not a variant of them: X has
mentions and no readable comments, which one flag cannot express.

| Platform | Comments | Messages | Mentions |
|---|---|---|---|
| Facebook | ✅ Page post comments | ✅ Conversations API (`pages_messaging`) | — |
| Instagram | ✅ Media comments | ✅ (`instagram_manage_messages`) | — |
| LinkedIn | ✅ Organization posts only | — messaging API is partner-gated | — |
| X | — replies are not readable on this tier | — needs elevated access | ✅ Mentions timeline |
| YouTube | ✅ Channel comment threads | — | — |

A capability flag says the *API* offers something; whether this deployment has
been approved for the permission surfaces at call time as a provider error, not
as a silently empty inbox. A test asserts that every flag set to true has a real
implementation behind it — a flag that claims a feature the server then refuses
is the lying-matrix pattern this project keeps removing.

### Everything turns on external_id

Polling re-fetches the same items every pass by design. A thread is found by the
platform's id for the conversation, a message by the platform's id for the
message, both under a unique constraint. Without that, every poll duplicates the
inbox — and the duplicates look like new mail.

Three related rules fall out of the same thinking:

* An **existing message is never rewritten**. A platform can re-serve the same
  comment with the author's name rendered differently, and updating it each poll
  churns the row and makes "has anything happened here" unanswerable.
* Activity markers **only move forward**. A late-arriving older item must not
  rewrite `last_message_at` and shuffle the inbox under whoever is reading it.
* An item with **no external_id is skipped**: there is nothing to be idempotent
  on, so storing it would duplicate forever.

Inbound mail **reopens a resolved thread** — a customer replying to a closed
conversation has not been dealt with.

### Unsupported is not an error

A platform whose capabilities say it has no DM API is never asked for one, and a
provider that raises `NotSupportedError` anyway — LinkedIn comments on a
personal profile, say — is recorded as *unsupported* rather than as a failure.
The two need different things from the reader: one is a fact about the platform,
the other is a fault to investigate. The UI states the gaps plainly, because an
empty list and "this platform has no message API" look identical and mean
opposite things.

### Replying sends first, records second

The provider call happens before the local row is written. The other order
leaves a reply visible in our inbox that the customer never received, which is
worse than an error the sender can see. A comment reply targets the most recent
inbound message rather than the thread root, keeping the conversation threaded
the way the platform displays it.

Replying needs `content.create`, not just `content.view`: it speaks to the
workspace's customers in its name, so a viewer who can read the inbox must not
be able to do it. Mentions cannot be replied to from here at all — a mention
lives on someone else's post, and answering means composing a public post, which
belongs to the composer.

**Internal notes** are a message with `direction=internal`. A direction rather
than a flag, because every query that means "what did the customer see" already
filters on direction — so a note cannot leak into one by being forgotten. They
deliberately do not move the thread up the inbox: it sorts by customer activity,
and a team member writing to themselves is not that.

Tags are lowercased and de-duplicated on the way in, since "Refund" and "refund"
filtering as two tags is how a tag list becomes useless within a week.

### Polling now, webhooks later

The worker polls every five minutes; these are rate-limited endpoints and a
tighter loop spends the budget without seeing more. The Meta webhook receiver
from 0.9 can feed the same upsert path later, making polling a backstop rather
than the primary route.


## Review and approvals

An optional workflow between drafting and publishing, enabled per workspace.

```
DRAFT ──submit──> IN_REVIEW ──approve──> [CLIENT_REVIEW] ──approve──> APPROVED
  ^                   │                        │                         │
  └──withdraw─────────┴──request_changes───────┴─────────────────────────┘
                             ↓
                    CHANGES_REQUESTED ──submit──> IN_REVIEW
```

**Every transition goes through `approvals.transition()`.** It is the only code that writes `Post.status` for review purposes. Status used to be assigned wherever a handler felt like it, which works until two endpoints disagree about whether an approved post can go back to draft — and then the answer depends on which button the user clicked.

**A manager's approval is not the client's.** With `client_approval_required`, internal sign-off moves a post to `CLIENT_REVIEW` and only the external reviewer reaches `APPROVED`. Collapsing those would let an internal approval stand in for the customer's, which is the failure that matters commercially.

**The gate is per workspace, and applies to scheduling as well as publishing** — a gate on publish alone isn't a gate, the post just goes out later. Both default off, so a team that never enables approvals publishes exactly as before. `client_approval_required` implies `approvals_required`: client review without internal review would send drafts straight to an external reviewer with nobody having looked first.

**CLIENT visibility is narrowed at the query level**, not in the response — so pagination totals are right too, and a client cannot learn how many drafts exist. They see `CLIENT_REVIEW`, `APPROVED` and `PUBLISHED`; single-post routes carry the same check, or every post would still be reachable by id. Reaching outside that set returns **404, not 403**: telling an external reviewer that an internal draft exists is itself a disclosure.

**Mentions** are `@[uuid]` tokens rather than `@name` — names are ambiguous and change. Membership is re-checked at write time: mentioning an arbitrary id would otherwise notify a stranger and confirm to the mentioner that the id is real. The stored mention list is not re-derived on read, so editing a comment cannot retroactively change who was notified.

| Method | Path |
|---|---|
| `POST` | `/posts/{id}/submit-for-review` |
| `POST` | `/posts/{id}/approve` |
| `POST` | `/posts/{id}/request-changes` (comment required) |
| `POST` | `/posts/{id}/withdraw` |
| `GET` | `/posts/{id}/review` |
| `PATCH` | `/posts/{id}/assignment` |
| `GET`/`POST`/`PATCH`/`DELETE` | `/posts/{id}/comments` |

`GET /review` returns `allowed_actions`, computed against the same matrix the endpoints enforce, so the panel cannot offer a button that 403s. Comments need only `content.view` — a CLIENT has to be able to say why they are rejecting something, and they cannot create content.

> `PENDING_APPROVAL` is superseded by `IN_REVIEW`. Postgres cannot drop an enum label, so it stays declared and the migration backfills existing rows; nothing writes it any more.

## Per-platform variants

One post, customised per platform. The base `Post` holds the master content an author writes once; a `PostVariant` overrides it for one platform — so you trim the version that goes to X without touching what LinkedIn receives.

**Every override column is nullable, and NULL means "inherit" — not "empty".** That distinction is the whole design. A variant created purely to set a first comment keeps following the master content as it is edited; if absence and emptiness were the same value, it would silently freeze that platform's copy at whatever the master said when the variant was created. An explicit `""` is a deliberate choice to publish no text there, and resolution honours it.

Resolution happens in `resolve_content(post, slug, variant)` — the same function the publish path calls, so the composer's preview cannot disagree with what actually goes out. A variant is keyed on platform slug, not on a connected account: two X accounts on one post share one "X version", which is what an author means by customising for a platform.

> The connectors' `PostVariant` dataclass was renamed to **`ResolvedContent`** when this table arrived. A variant is what an author *wrote*; resolved content is what publishing *arrived at* after layering it over the master. Two things under one name, one of them not a model, is a trap.

**Validation** checks each target against *its own* provider's `Capabilities`, so a 400-character post fails X (280) and passes LinkedIn (3,000) rather than failing as a whole. Every rule reads from the connector, so a platform's limits live in exactly one place and adding a platform cannot forget to add its validation.

Errors are structured `{platform, field, message, severity}` so the composer can put each one next to the input that caused it. `warning` does not block saving — a missing alt text is worth telling an author about, but refusing to let them schedule over it would be the tool overruling them.

The character count includes hashtags, which are stored separately but publish in the body. It deliberately does **not** model X's URL shortening (every link counts as 23 characters regardless of length): counting links in full errs toward warning about a post that would have fit, rather than accepting one that will not.

| Method | Path |
|---|---|
| `GET` | `/posts/{id}/variants` |
| `PUT` | `/posts/{id}/variants/{platform_slug}` |
| `DELETE` | `/posts/{id}/variants/{platform_slug}` |
| `GET` | `/posts/{id}/variants/{platform_slug}/preview` |
| `POST` | `/posts/{id}/validate` |

`PUT` rather than POST/PATCH because a platform has at most one variant, so the slug fully identifies it — the composer saves a tab without first knowing whether one exists. Slugs are normalised through the registry, so `x`, `twitter` and `X (Twitter)` all address the same variant instead of creating two.

## Publishing

Publishing is a queue of database rows, not an inline loop. Each post fans out into one **`PublishingJob`** per target social account, and each attempt writes a **`PublishingLog`** row carrying the platform's own response.

It used to run inline: an endpoint flipped the post to `PUBLISHING` and fired a background task that looped over the targets. Three things were wrong with that, and they are why this exists:

- **Not durable.** A process death mid-loop left the post in `PUBLISHING`. The sweeper's only recourse was to reset the *whole post* and republish every target — including the ones that had already succeeded, so recovery could double-post.
- **Not retryable per target.** One expired token failed the post, and the healthy accounts had to be republished along with it.
- **Not observable.** A failure was a string in a JSON array: no attempt count, no next-retry time, no record of what the platform said.

**Deliberately not Celery.** The worker is a plain asyncio loop in the FastAPI lifespan ([app/core/scheduler.py](backend/app/core/scheduler.py)); the durability a broker would have provided comes from the database instead. Nothing is held in a queue that can disagree with the database about what was published.

```
publish / schedule ──> create_jobs_for_post()   one QUEUED job per target
                                                run_at = now, or scheduled_at
worker loop (5s) ────> claim_due_jobs()          FOR UPDATE SKIP LOCKED
                  ──> execute_job()              provider registry
                  ──> requeue_stale_claims()     claimed > 20 min ago
                       │
                       └─> derive_post_status()  jobs → post.status
```

**Claiming is what makes multiple instances safe.** `FOR UPDATE SKIP LOCKED` means rows one worker locks are invisible to another's `SELECT`, and the claim commits while the locks are held — so by the time they release, the rows no longer match the queue filter. Without it both workers take every job and every post goes out twice; [test_publishing_concurrency.py](backend/tests/test_publishing_concurrency.py) proves it, and needs real Postgres to do so.

**Retries back off exponentially** — 30s, 60s, 120s… capped at 30 minutes, with ±25% jitter so a batch that fails together does not retry in lockstep. A platform's `Retry-After` on a 429 always wins over the curve. A permanent error (a revoked token, a rejected payload) fails immediately rather than burning three attempts to tell the user the same thing.

**Post status is derived, not stored independently.** All jobs succeeded → `PUBLISHED`; some failed → `PARTIALLY_PUBLISHED`; all failed → `FAILED`; any still pending → `PUBLISHING`. `posting_results` is rebuilt from the same rows, so it is a projection rather than a second source of truth that can disagree.

Two endpoints expose it, and the post detail modal renders them per platform with a retry button:

| Method | Path | Permission |
|---|---|---|
| `GET` | `/api/v1/accounts/{id}/posts/{id}/jobs` | `content.view` |
| `POST` | `/api/v1/accounts/{id}/posts/{id}/jobs/{job_id}/retry` | `content.publish` |

Retrying reruns **only that job** — the accounts that already published are untouched. Retrying a job that already succeeded is refused with a 409, because it would post the content a second time.

## Social connectors

Every platform lives behind one `SocialProvider` in [backend/app/connectors/](backend/app/connectors/). Before this, platform behaviour was spread across three layers and the same `if "facebook" in slug ... elif` chain was written four times — publishing covered five platforms, pre-publish token refresh covered two, and account verification and manual refresh each had their own shape. Adding a platform meant finding all four.

```
app/connectors/
  base.py      SocialProvider, Capabilities, PublishResult, PostVariant,
               NotSupportedError, and the shared OAuth/refresh plumbing
  media.py     platform-agnostic helpers (media re-hosting, SSRF guard,
               hashtags, ffmpeg image+audio -> video)
  facebook.py  instagram.py  linkedin.py  twitter.py  youtube.py
  registry.py  get_provider(slug) -> SocialProvider
```

`get_provider(slug)` is the only dispatch. It keeps the substring matching the old code used (`"insta"`, `slug == "x"`) so no existing `social_platforms` row stops resolving.

**Every platform call is awaited.** Providers use `httpx.AsyncClient`, and even the ffmpeg render in `media.py` runs through `asyncio.create_subprocess_exec`. `asyncio.to_thread` survives only around the small disk operations that have no async equivalent — reading and writing the render's temporary files.

This matters because the thread pool is shared with bcrypt password hashing ([main.py](backend/app/main.py) sizes it so a publish burst cannot starve logins). Waiting on Instagram's encoder (up to two minutes of polling) or a YouTube resumable upload (a 600-second timeout) used to occupy one of sixteen threads for the whole duration. Two structural tests keep it that way: one asserts no `httpx.Client` remains under `app/connectors/`, the other that `to_thread` appears only in `media.py`.

A method a platform has no API for raises `NotSupportedError`, which is deliberately distinct from "not built yet": a caller that sees it should stop asking rather than retry.

**Publishing** goes through `posts.py::_do_publish_to_platforms`, which both the publish endpoint and [the scheduler](backend/app/core/scheduler.py) call — one implementation, not two. Each target yields a `PublishResult`; the post lands on `PUBLISHED`, `PARTIALLY_PUBLISHED` or `FAILED`. `manual_required` is its own status because YouTube Community posts have no API and the UI offers a "publish by hand" helper instead of an error.

`PublishResult.retryable` distinguishes a rate limit or 5xx from a revoked token. **Nothing acts on it yet** — the scheduler's `retry_count` is crash-recovery only and never retries a platform error — but classifying it where the HTTP status is still in hand is the only place it can be done honestly.

**Capabilities.** `GET /api/v1/accounts/{account_id}/social-accounts/{id}/capabilities` reports what a platform accepts, so the composer can validate before a user spends effort on a post that will be rejected:

| | chars | images | video | carousel | links |
|---|---|---|---|---|---|
| facebook | 63,206 | yes | yes | yes | yes |
| instagram | 2,200 | yes | yes | yes | no |
| linkedin | 3,000 | yes | **no** | no | yes |
| twitter | **280** | **no** | no | no | yes |
| youtube | 5,000 | no | yes | no | no |

The two bold "no"s report what the *connector* does, not what the platform allows: the X publisher drops media silently and the LinkedIn one rejects video outright. Reporting the API's real limits would promise something the connector will not deliver.

`None` on a numeric field means no limit — not unknown, not zero.

## Entitlements

What each plan allows lives in the database — `plans`, `features`, `plan_features` and `usage_records` — not in the source. Limits used to be a `TIER_LIMITS` dictionary, which meant changing one needed a deploy and a customer who negotiated a higher cap could not have it.

| Feature key | Unit | Counted |
|---|---|---|
| `workspaces` | count | live |
| `team_members` | count | live |
| `social_accounts` | count | live |
| `posts_per_month` | count | metered |
| `ai_requests_per_month` | count | metered |
| `storage_bytes` | bytes | live |
| `analytics_history_days` | count | live |
| `reports_per_month` | count | metered |
| `white_label` | boolean | — |

**Live** features are counted with a query each time, so deleting a workspace frees the slot. **Metered** ones accumulate in `usage_records` for the calendar month and are not refunded — deleting a post does not give the allowance back, and an AI request that fails downstream has still cost us the call.

A limit of `NULL` is unlimited; `0` means the plan does not include the feature. A missing `plan_features` row reads as `0`, never as unlimited — failing open on a missing entitlement would be the worst available default.

Exceeding a limit returns **402 Payment Required**, not 403: the caller is authorised, the plan simply does not cover it, and upgrading makes it work.

Metering is a single guarded statement rather than a read followed by a write:

```sql
INSERT INTO usage_records (...) VALUES (...)
ON CONFLICT (organization_id, feature_key, period_start) DO UPDATE
  SET count = usage_records.count + :amount
  WHERE usage_records.count + :amount <= :limit
RETURNING count
```

No row comes back when the guard rejects it, which is how the caller learns it was refused. Reading the count first would let two requests arriving at limit-1 both decide they fit — see [test_entitlement_concurrency.py](backend/tests/test_entitlement_concurrency.py).

Limits are cached for 60 seconds per organization (Redis when configured, per-process otherwise). Every write path — a plan change, a limits edit, an admin CRUD call — invalidates the cache, so a raised cap takes effect immediately.

Superadmins manage plans and limits at `/admin/plans` in the SPA, backed by `GET|POST|PATCH /api/v1/admin/plans`, `PUT /api/v1/admin/plans/{id}/limits` and `GET /api/v1/admin/features`. Retiring a plan deactivates it rather than deleting the row, because organizations reference plans by tier key and a missing plan would leave them with no limits at all.

Customers see the same numbers on the billing page, from `GET /api/v1/organizations/{id}/usage`. Usage is organization-wide: one allowance shared across every workspace.

**Limits are never stored on the organization row.** `organizations` carried `monthly_post_limit`, `max_team_members`, `max_platforms` and `max_workspaces`, denormalised from `TIER_LIMITS`. Migration `f2a90c4d7b18` drops them. They had stopped driving enforcement but were still being served — so a superadmin raising a cap would change `plan_features` while those columns kept the old number, and the UI would show a limit that disagreed with what enforcement did. Every endpoint that reports a limit (`/organizations/{id}/usage`, `/accounts/{id}/settings/`, `/accounts/{id}/settings/usage`, `/accounts/{id}/billing/`) now resolves it through `EntitlementService`, so there is one answer rather than four.

## Admin panel

Every route under `/api/v1/admin` requires `is_superadmin` **and** an active account, through
one shared `require_superadmin` dependency. These expose the whole customer book, so the gate is
tested per route rather than per module.

### Revenue

`GET /admin/revenue` and `/admin/revenue/trend`. MRR is the sum of `plans.price_monthly` over
organizations whose subscription is ACTIVE and not soft-deleted; ARR is that times twelve.

Three things are deliberately excluded from MRR, because each is a way for a dashboard to flatter
itself:

* **TRIALING** has not paid — that is what the conversion figure measures.
* **PAST_DUE** has an uncollected invoice. It is reported beside MRR as `at_risk_mrr`, never inside it.
* **Soft-deleted organizations**, which are not customers.

Enterprise is priced by negotiation and its plan row carries no amount, so MRR *understates* the
real figure. Rather than quietly omit the largest customers, the payload returns
`unpriced_active_organizations` and the UI says so above the number.

Prices are read from the `plans` table, so editing a plan in the admin UI moves the revenue report
with no deploy. `/admin/stats` previously carried its own hard-coded price dict — 29/79/199/499
against real prices of 49/149/399/0, applied to every organization regardless of whether it was
paying — so two admin screens quoted different revenue. It now reads the same function.

### Why there is a subscription event log

`organizations` stores only the *current* tier and status. That answers "what is being billed now"
and nothing with a date in it: churn last 30 days, trial conversions, and an MRR trend all need to
know *when* something changed. `updated_at` cannot stand in — it moves on every write, so an
organization that cancelled a year ago and was renamed yesterday would count as this month's churn.

`subscription_events` records one row per transition, written at all six places tier or status
changes: the checkout confirmation, four Stripe webhook branches, and signup. A no-op change writes
nothing, so a redelivered webhook does not read as churn followed by a re-signup.

`mrr_amount` is copied onto the event rather than derived later. A price change should alter what
customers pay next month, not silently rewrite what the business earned last quarter — which is
exactly what joining history to today's `plans` row would do.

The log starts when this shipped, so `tracking_since` accompanies every movement figure and the
chart says "no history yet" instead of drawing a line at zero that implies the business had none.

### Connected-account health

`GET /admin/connection-health` — counts per `AccountHealth` state (every state present even at
zero, since a missing key reads as "unknown" and an explicit zero reads as "none"), plus every
FAILED connection with its workspace, organization and plan. Ordered longest-broken first: a
connection down for a week matters more than one that broke this morning. The 1.9 strip tells one
customer they are broken; this tells support which customers are.

### API error monitoring

The 500 handler writes an `api_errors` row and returns its id in the response body, so "it broke"
becomes a row lookup. Only *unhandled* exceptions land there — a 403 or a validation error is the
application working, and storing those would bury the real failures.

Two details carry the weight:

* **The write opens its own database session.** By the time the handler runs, the request's session
  has usually seen a failed statement, and on Postgres every subsequent statement in that
  transaction raises `InFailedSQLTransaction`. Reusing it would fail silently — and the request
  that most needs recording is precisely the one whose session is broken.
* **Recording never raises.** Every failure inside it is caught; the response goes out regardless.

Tracebacks are truncated from the *front*, keeping the tail: the last frames are the ones that
raised, while the first are ASGI plumbing identical on every row. Rows are pruned after 90 days by
a daily pass in the worker, separate from the analytics pass so one failing does not block the
other. `GET /admin/errors` filters by exception class and path prefix; the list omits tracebacks
and `/admin/errors/{id}` carries them, because fifty multi-kilobyte traces would make the list
unusable.

### No invented numbers

`AdminDashboard` previously rendered entirely hard-coded data: user counts with month-over-month
percentages, twelve months of revenue split across plan names the product does not have, and a
"recent signups" table of invented people with invented email addresses. The last is the worst,
being indistinguishable from real customer data. It is all gone. Where a figure genuinely is not
known yet — month-over-month deltas, which need history the event log has only started collecting
— the page shows no delta rather than a plausible one.

The connectors carried four more, found by a browser walkthrough rather than by review, and they
were worse: engagement numbers on real posts, which reach analytics dashboards and the PDFs
agencies send to their clients.

* `TwitterConnector.get_post_metrics` and its LinkedIn twin returned random integers
  **unconditionally** — not gated on a development token, not on `DEBUG`. Their own docstrings said
  "Returns fabricated numbers." Three consecutive reads of one post gave 755, 72 and 674 likes.
* Every connector's `except Exception` in the metrics fetch logged *"falling back to mock"* and
  returned random integers, so an expired token, a rate limit or a provider outage produced
  plausible engagement **and hid the failure that caused it**.
* The "development placeholder" paths were reachable in production: `is_mock_token()` matches any
  token merely *containing* `"test"` and returns `True` for an empty one, so a live credential or a
  token that failed to decrypt was served invented data.
* Publishing seeded a fully zeroed `PostPerformance` row per platform. A row of zeros is not an
  empty state — it says the post was measured and reached nobody. On X and LinkedIn the zeros were
  never replaced, so those posts kept a permanent, confident "0 reach" indistinguishable from a real
  result. Removing the first three would have achieved nothing while this remained.

All four are gone. X and LinkedIn now raise `NotSupportedError`, which is the base class's own
default and the honest answer; a failed fetch reports nothing and leaves the last real measurement
standing; a placeholder token reports nothing; and a performance row is created when real numbers
arrive rather than at publish time. `random` is no longer imported anywhere under `app/connectors/`,
and `tests/test_no_fabricated_metrics.py` fails if it returns.

Absence is carried to the pixels: `Post.performance` is null with no rows, `analytics_query.posts`
inner-joins so an unmeasured post is simply not listed, and the calendar says *"Twitter does not
expose per-post metrics, so there is nothing to report"* rather than drawing zeroes. Migration
`b8d3aa61c94f` deletes what was already stored — every X and LinkedIn row, since neither connector
ever had a real fetch, and every row still entirely zero. Facebook, Instagram and YouTube rows are
left alone: each had a real fetch with a fabricated fallback, so their rows mix measurement and
invention with nothing to separate them, and deleting real data to be rid of invented data is its
own loss.


## Running the tests

```bash
cd backend
pip install -r requirements-dev.txt
DEBUG=true python -m pytest tests/ -q
```

[`requirements-dev.txt`](backend/requirements-dev.txt) pins the test and lint tooling and includes `requirements.txt`, so it is the only file a contributor needs to install.

The suite runs against in-memory SQLite and needs no Postgres or Redis. Shared fixtures (app client, database session, user/account/member factories, auth headers, plan seeding and `set_limit`) live in [backend/tests/conftest.py](backend/tests/conftest.py).

Three files are the exception, for two different reasons.

[test_publishing_concurrency.py](backend/tests/test_publishing_concurrency.py) proves that two workers cannot claim the same publishing job, and [test_entitlement_concurrency.py](backend/tests/test_entitlement_concurrency.py) proves that two requests arriving at the same limit cannot both succeed. Both need two connections running two transactions at once — which the single-connection SQLite harness cannot express, and where `with_for_update(skip_locked=True)` is a silent no-op.

[test_analytics_postgres.py](backend/tests/test_analytics_postgres.py) is there for the opposite reason: not because SQLite is too weak to express the guarantee, but because it is too *permissive* to catch the bug. It accepts SQL Postgres rejects — `round(double precision, int)` among it — so a query can pass all 600-odd tests and 500 in production. It executes each analytics query once on the real database.

All three create a scratch database on the server named by `DATABASE_URL` (overridable with `TEST_POSTGRES_ADMIN_URL`), drop it afterwards, and **skip** when no Postgres is reachable. CI runs a Postgres service, so they execute there; locally they will skip unless Postgres is up.

Linting:

```bash
cd backend
ruff check .
```

Ruff was added as part of repo hygiene and the project has no `ruff` configuration yet, so a bare run currently reports a large backlog of pre-existing findings against Ruff's defaults — including `B008` on FastAPI's standard `Depends(...)`-in-defaults idiom, which is a false positive here. Tune the rule set in `pyproject.toml` before wiring this into CI.

---

## Operational scripts

One-off scripts live in `backend/scripts/` and are run from the `backend/` directory:

| Script | Purpose |
|---|---|
| `setup_database.py` | Convenience wrapper: `alembic upgrade head`, optionally `--seed`. |
| `seed.py` | Replace all data with demo users, accounts, and posts. Assumes migrations have run. |
| `purge_deleted_users.py` | Hard-purge soft-deleted users past the retention window. Supports `--days` and `--dry-run`. |
| `check_routes.py` | Print every registered API route. |
| `check_users.py` | List users in the database. |
| `query_accounts.py` | List connected social accounts. |
| `download_avatars.py` | Fetch and cache social profile avatars. |
| `fetch_ig.py` | Fetch an Instagram profile picture. |

```bash
cd backend
alembic upgrade head              # migrate first -- seed.py does not create tables
python scripts/seed.py
python scripts/purge_deleted_users.py --dry-run
```

Schema changes belong in a migration, not in a script — see [Database migrations](#database-migrations). The former `create_db.py` and `migrate_db.py` were removed when Alembic was introduced.

---

## Further documentation

Detailed specifications are in [documents/](documents/):

| Document | Contents |
|---|---|
| [PRD.md](documents/PRD.md) | Product requirements and vision |
| [API-Specification.md](documents/API-Specification.md) | Endpoint reference |
| [Database-Design.md](documents/Database-Design.md) | Schema and relationships |
| [RBAC-Permissions.md](documents/RBAC-Permissions.md) | Roles and permission matrix |
| [TechStack.md](documents/TechStack.md) | Technology decisions |
| [DesignDoc.md](documents/DesignDoc.md) | Architecture |
| [Modern-UI-Design-System.md](documents/Modern-UI-Design-System.md) | Design system |
| [UI-Dashboard-Specification.md](documents/UI-Dashboard-Specification.md) | Dashboard specification |
| [UserDocumentation.md](documents/UserDocumentation.md) | End-user guide |
| [LegalCompliance.md](documents/LegalCompliance.md) | Compliance notes |
| [PlatformRequirements.md](documents/PlatformRequirements.md) | Per-platform API requirements |
| [docs/LINKEDIN_INTEGRATION.md](docs/LINKEDIN_INTEGRATION.md) | LinkedIn integration notes |
