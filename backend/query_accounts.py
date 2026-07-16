import asyncio
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.platform import SocialAccount

async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(SocialAccount))
        accounts = result.scalars().all()
        print(f"Found {len(accounts)} social accounts:")
        for a in accounts:
            print(f"ID: {a.id} | Platform ID: {a.platform_id} | Name: {a.account_name} | Handle: {a.account_handle}")

if __name__ == "__main__":
    asyncio.run(main())
