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

> **Note:** `docker-compose.yml` sets `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `JWT_SECRET_KEY` and `FRONTEND_URL` inline for the backend services, so the stack boots without a `.env`. Those inline values are development placeholders. Any other variable — AI provider keys, Stripe, OAuth credentials — must be added to the compose environment or the service will run with that feature disabled.

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

Everything else is optional — an unset AI, Stripe, S3, email, or OAuth variable disables that feature rather than breaking startup.

Frontend variables are separate: Vite reads `VITE_`-prefixed values from `frontend/.env` at build time. Only `VITE_API_URL` is currently used.

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

## Running the tests

```bash
cd backend
pip install -r requirements-dev.txt
DEBUG=true python -m pytest tests/ -q
```

[`requirements-dev.txt`](backend/requirements-dev.txt) pins the test and lint tooling and includes `requirements.txt`, so it is the only file a contributor needs to install.

The suite runs against in-memory SQLite and needs no Postgres or Redis. Shared fixtures (app client, database session, user/account/member factories, auth headers) live in [backend/tests/conftest.py](backend/tests/conftest.py).

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
