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

One file is the exception. [backend/tests/test_entitlement_concurrency.py](backend/tests/test_entitlement_concurrency.py) proves that two requests arriving at the same limit cannot both succeed, and that needs two connections running two transactions at once — which the single-connection SQLite harness cannot express. It creates its own scratch database on the server named by `DATABASE_URL` (overridable with `TEST_POSTGRES_ADMIN_URL`) and drops it afterwards, and **skips** when no Postgres is reachable. CI runs a Postgres service, so it executes there; locally it will skip unless Postgres is up.

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
