import asyncio
import argparse
import sys
import os

# Add parent directory to path so app imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def run_setup(seed_db=False):
    print("=" * 60)
    print("STARTING DATABASE SETUP PROCESS")
    print("=" * 60)

    # 1. Create database if it doesn't exist
    from create_db import main as create_database
    print("\n[Step 1/3] Ensuring PostgreSQL database exists...")
    await create_database()

    # 2. Initialize Base Tables and Run Migrations
    from app.core.database import engine, Base
    from migrate_db import migrate as run_migrations

    print("\n[Step 2/3] Initializing base database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Base database tables initialized successfully.")

    print("\n[Step 3/3] Checking and applying platform-specific migrations...")
    await run_migrations()

    # 3. Optional Seeding
    if seed_db:
        print("\n[Optional Step] Seeding database with dummy data...")
        from seed import seed as run_seed
        await run_seed()
        print("Database successfully seeded.")

    print("\n" + "=" * 60)
    print("DATABASE SETUP COMPLETED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Setup and migrate database.")
    parser.add_argument(
        "--seed", 
        action="store_true", 
        help="Seed the database with sample/test data (WARNING: drops existing data)"
    )
    args = parser.parse_args()

    asyncio.run(run_setup(seed_db=args.seed))
