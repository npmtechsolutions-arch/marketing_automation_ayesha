import sys
from pathlib import Path

# These scripts live in backend/scripts/, but import the application package
# from backend/. Put the backend root on sys.path so `import app...` resolves
# whether the script is run as `python scripts/<name>.py` or `python -m`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.user import User

async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
        print(f"Found {len(users)} users:")
        for u in users:
            print("-" * 50)
            print(f"Email: {u.email}")
            print(f"Password Hash: {u.password_hash}")
            print(f"Active: {u.is_active}")

if __name__ == "__main__":
    asyncio.run(main())
