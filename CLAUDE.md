# Working notes for Claude

Conventions for this repo. The README documents the product; this file holds the
things that have actually caused bugs here, so they do not cause them twice.
Every entry earned its place by a specific incident.

## Testing

- **Code that opens its own DB session (error logging, background tasks) must be
  covered by the conftest engine redirect — audit when adding either.** The 500
  handler's `error_log.record` correctly opens its own session: by the time it
  runs, the request's transaction is dead and every further statement in it
  would raise. But the `get_db` override does not cover a session opened
  directly, so for one session every 500 raised inside a test wrote to the
  developer's real Postgres. `conftest` now points `AsyncSessionLocal` at the
  test engine. The general rule: whenever the harness changes, or a new code
  path opens its own session, re-inventory both sides.

- **Revert the fix, confirm the test fails, restore.** Every phase here has done
  this. A test that passes both with and without the fix is pinning nothing, and
  the failure is silent. This has caught weak tests repeatedly — most sharply in
  §12, where a per-field round-trip test passed against the bug it was written
  for because the fixture started from an empty JSON blob.

- **Verify against the running server, not only the suite.** Live curl against
  port 8001 has found bugs the suite structurally could not, in almost every
  phase: a 500 on the settings endpoint, an unreachable admin panel, a
  self-refunding AI meter, `engagement_rate` reporting 0.0% for a workspace with
  61,000 reach, `/analytics/posts` 500ing on Postgres, and an all-zero
  connection-health panel from a wrong enum key.

- **A test that anchors on `date.today()` is anchored to the machine, not the
  product.** Windows here resolve in the *workspace's* timezone, so on a machine
  east of UTC — between local midnight and UTC midnight — a row written "today"
  lands a day outside the window. Six analytics tests passed for weeks and broke
  at 00:17 IST: always wrong, visible five and a half hours a day. Compute the
  date on the same clock the code under test uses.

- **The frontend has tests now: `npm test` in `frontend/` (vitest).** Added with
  the #13-#16 fixes, which were all "the UI says something the server does not".
  They cover pure logic deliberately extracted out of components -- status
  mapping, seat maths, schedule defaults -- so no DOM assertions and no snapshot
  files. When a UI defect is really a rule, move the rule into `src/lib/` and
  pin it there; the component keeps only the markup. Run it alongside the
  typecheck, and remember the backend suite holds the *other half* of two of
  these contracts (`tests/test_status_contract.py`).

- **Capture `httpx.AsyncClient` once, at import, before any test patches it.**
  A fake that reads `httpx.AsyncClient` inside its own `install()` wraps
  whatever is already installed — so a second fake in the same test handed its
  transport to the *first* fake's factory, which promptly overrode it. Every
  request went to the previous fake's handler while the new one sat at zero
  requests, which reads as "the code never called the API" rather than "the
  harness is wrong". Found in the TikTok poll-loop test, whose whole point was
  counting clients.

- **`dark:` utilities follow the app's theme toggle only because
  `index.css` says so.** Tailwind v4's default `dark:` variant is
  `prefers-color-scheme`, and this app switches themes with a `.dark` class on
  `:root` — so every `dark:` utility silently followed the operating system and
  ignored the toggle. `@custom-variant dark (&:where(:root.dark, :root.dark *))`
  is what connects them; do not remove it. Found by screenshotting a new page in
  both themes and seeing dark red text on a dark background. The safer default
  for new work is still the `--page-*` / `--surface-*` CSS variables, which have
  always tracked the toggle.

- **`npx tsc --noEmit` in `frontend/` checks nothing.** The root `tsconfig.json`
  has `"files": []` and only project *references*, so the bare invocation
  type-checks an empty program and exits 0 no matter what is broken. Use
  **`npx tsc -p tsconfig.app.json --noEmit`** (or `tsc -b`). Verified the only
  way worth trusting: writing `const probe: number = "nope"` into `src/` and
  confirming the command fails. It had been reported green through a whole
  phase before anyone made it fail on purpose.

- **SQLite accepts SQL that Postgres rejects.** The suite runs on in-memory
  SQLite. `round(double precision, int)` does not exist in Postgres — only
  `round(numeric, int)` — so a query passed all 600-odd tests and 500'd in
  production. `tests/test_analytics_postgres.py` executes each analytics query
  against real Postgres and skips without one; add to it when writing
  non-trivial SQL. Same for the two concurrency files, which need real
  transactions because `FOR UPDATE SKIP LOCKED` is a no-op on SQLite.

## SQLAlchemy

- **A SQLAlchemy `Enum` column stores the member NAME, not the value.** Postgres
  holds `'FREE'`; `SubscriptionTier.FREE.value` is `'free'`. Joining
  `plans.key == organizations.subscription_tier` therefore matched nothing, and
  an outer join of nothing totals zero: MRR read as $0 against a full customer
  book, and nothing raised. Do the mapping in Python, or compare explicitly —
  never join a plain string column to an enum column.

- **A plain `JSON`/`JSONB` column has no change tracking.** Mutating the loaded
  dict and assigning it back to itself leaves `history.has_changes()` False, the
  flush emits no `UPDATE`, and the endpoint returns 200 having written nothing.
  Always build a new dict: `obj.blob = {**(obj.blob or {}), **updates}`.

- `db.refresh()` drops eager loads, so a relationship read afterwards becomes a
  lazy load and raises `MissingGreenlet`. Re-query with `selectinload` plus
  `.execution_options(populate_existing=True)` — without the latter the identity
  map hands back the pre-write collection.

## Migrations

- **`op.create_table` fires an enum's `before_create` with `checkfirst=False`,
  memoised per Alembic process.** A fresh run passes; a downgrade-then-upgrade in
  the same process raises `DuplicateObjectError`. Use
  `postgresql.ENUM(..., create_type=False)` with an explicit `.create(bind,
  checkfirst=True)`; the generic `sa.Enum(create_type=False)` silently ignores
  the flag. Always test the round trip in one process.

- Postgres enums support `ADD VALUE` only, never `DROP`, and a label added in a
  transaction cannot be *used* in it — an explicit `op.execute("COMMIT")` has to
  come before any backfill. Alembic autogenerate does not detect added values.

## Numbers shown to users

- **Null is not zero, and both must survive to the pixels.** A metric a platform
  does not report contributes nothing to a total rather than a zero; a total with
  no contributors stays null; CSV writes an empty cell, not `"None"`; the UI
  renders an em dash. Storing absent-as-zero puts a real, flat, wrong line on a
  chart and drags every cross-platform average down.

- **A rate with no denominator is null, not 0%.** 0% churn out of no customers is
  not a good month, and 0% engagement against unmeasured interactions reads as
  "your content is failing" when the truth is "we cannot measure this".

- **Never ship fabricated numbers.** Three have been removed: a posting heatmap
  drawn from `Math.random()`, a hard-coded price table that made two admin
  screens quote different revenue, and an admin dashboard of invented signups
  with invented email addresses. The last is the worst kind — indistinguishable
  from real customer data. An empty state is always better. If a figure needs
  history the system has not collected, say so (`tracking_since`) rather than
  drawing a line at zero.

- **One source of truth per number.** Limits live in `plan_features`, prices in
  `plans`. A serialised copy that no longer drives enforcement is the drift
  pattern this project keeps killing.

## System dependencies

- **WeasyPrint needs pango**, which pip does not install: the package imports
  and then fails at render time with "cannot load library libpango-1.0-0". On
  macOS `brew install pango`; on Debian `libpango-1.0-0` and
  `libpangoft2-1.0-0`. Code that renders PDFs should degrade to "this format is
  unavailable" rather than failing the whole job, and its tests should skip
  rather than fail — the same convention as the Postgres-gated suites.

## Shell

- **Never `git checkout <file>` to undo an experiment.** It reverts to HEAD and
  discards uncommitted work — it destroyed a file's in-progress conversion once.
  Copy to the scratchpad first, then restore from there.
