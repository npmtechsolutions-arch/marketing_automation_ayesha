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

## Running the tests

```bash
cd backend
pip install -r requirements-dev.txt
DEBUG=true python -m pytest tests/ -q
```

[`requirements-dev.txt`](backend/requirements-dev.txt) pins the test and lint tooling and includes `requirements.txt`, so it is the only file a contributor needs to install.

The suite runs against in-memory SQLite and needs no Postgres or Redis. Shared fixtures (app client, database session, user/account/member factories, auth headers, plan seeding and `set_limit`) live in [backend/tests/conftest.py](backend/tests/conftest.py).

Two files are the exception. [test_publishing_concurrency.py](backend/tests/test_publishing_concurrency.py) proves that two workers cannot claim the same publishing job, and [test_entitlement_concurrency.py](backend/tests/test_entitlement_concurrency.py) proves that two requests arriving at the same limit cannot both succeed. Both need two connections running two transactions at once — which the single-connection SQLite harness cannot express, and where `with_for_update(skip_locked=True)` is a silent no-op. Each creates its own scratch database on the server named by `DATABASE_URL` (overridable with `TEST_POSTGRES_ADMIN_URL`) and drops it afterwards, and **skips** when no Postgres is reachable. CI runs a Postgres service, so it executes there; locally it will skip unless Postgres is up.

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
