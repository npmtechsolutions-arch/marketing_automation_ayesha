import asyncio
import uuid
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.strategy import Strategy
from app.models.user import User

async def main():
    async with AsyncSessionLocal() as session:
        # Find user
        res = await session.execute(select(User).where(User.email == "user@gmail.com"))
        user = res.scalar_one_or_none()
        if not user:
            print("User user@gmail.com not found!")
            return
        
        print(f"Found User: {user.email} (id: {user.id})")
        
        # Get strategies
        res = await session.execute(select(Strategy))
        strategies = res.scalars().all()
        print(f"Total strategies: {len(strategies)}")
        for s in strategies:
            print(f"- Strategy ID: {s.id}")
            print(f"  Name: {s.name}")
            print(f"  Goal: {s.goal}")
            print(f"  Platform Mix: {s.platform_mix}")
            print(f"  Posting Frequency: {s.posting_frequency}")
            print(f"  Content Themes: {s.content_themes}")
            print(f"  Reasoning: {s.reasoning}")
            print(f"  Is Active: {s.is_active}")
            print(f"  Created At: {s.created_at}")

if __name__ == "__main__":
    asyncio.run(main())
