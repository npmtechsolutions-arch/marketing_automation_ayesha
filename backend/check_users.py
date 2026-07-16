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
