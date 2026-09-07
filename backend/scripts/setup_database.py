"""Bring a database up to date, optionally with sample data.

A thin convenience wrapper around the real tooling::

    alembic upgrade head          # apply migrations
    python scripts/seed.py        # optional sample data

Equivalent to running those directly -- use whichever you prefer.

The database itself must already exist; migrations create tables, not
databases. Under docker compose the ``postgres`` service creates it from
``POSTGRES_DB``. Locally::

    createdb marketengine

Usage:
    python scripts/setup_database.py              # migrate only
    python scripts/setup_database.py --seed       # migrate, then seed
"""
import sys
from pathlib import Path

# These scripts live in backend/scripts/, but import the application package
# from backend/. Put the backend root on sys.path so `import app...` resolves
# whether the script is run as `python scripts/<name>.py` or `python -m`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import asyncio
import subprocess

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def run_migrations() -> None:
    """Run `alembic upgrade head` from the backend root."""
    print("\n[1/2] Applying migrations (alembic upgrade head)...")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_ROOT,
    )
    if result.returncode != 0:
        raise SystemExit(
            "\nMigrations failed.\n"
            "If this is an existing database created before Alembic was "
            "introduced, its tables already exist. Record it as already at the "
            "baseline instead of re-creating them:\n\n"
            "    alembic stamp head\n"
        )
    print("Migrations applied.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Seed sample data after migrating (WARNING: deletes existing data)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("DATABASE SETUP")
    print("=" * 60)

    run_migrations()

    if args.seed:
        print("\n[2/2] Seeding sample data...")
        from seed import seed as run_seed

        asyncio.run(run_seed())
    else:
        print("\n[2/2] Skipping seed (pass --seed to load sample data).")

    print("\n" + "=" * 60)
    print("DATABASE SETUP COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    main()
