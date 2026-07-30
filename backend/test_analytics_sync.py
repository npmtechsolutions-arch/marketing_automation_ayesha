import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import AsyncSessionLocal
from app.models.post import Post, PostStatus
from app.models.post_performance import PostPerformance
from app.api.v1.endpoints.analytics import _sync_all_account_posts

async def test_sync_flow():
    async with AsyncSessionLocal() as session:
        # Find the specific mock post f234435e-f6ac-44bb-8a6d-9aa1c2b587e9
        stmt = (
            select(Post)
            .where(Post.id == uuid.UUID("f234435e-f6ac-44bb-8a6d-9aa1c2b587e9"))
            .options(selectinload(Post.performances))
        )
        res = await session.execute(stmt)
        target_post = res.scalars().first()
        
        if not target_post:
            print("ERROR: Mock post f234435e-f6ac-44bb-8a6d-9aa1c2b587e9 not found in DB.")
            return
            
        print(f"Testing with post: {target_post.id} (Account: {target_post.account_id})")

        # Let's set its fetched_at to 10 minutes ago and clear its metrics so it is eligible for sync
        for perf in target_post.performances:
            perf.fetched_at = datetime.now(timezone.utc) - timedelta(minutes=10)
            perf.reach = 0
            perf.likes = 0
            
        await session.commit()
        print("Set fetched_at to 10 minutes ago, reach=0, likes=0 in DB.")

        # Execute the sync
        print("Running _sync_all_account_posts...")
        await _sync_all_account_posts(target_post.account_id, session)
        
        # Verify it updated in DB
        # Re-fetch performance
        stmt = (
            select(PostPerformance)
            .where(PostPerformance.post_id == target_post.id)
        )
        res = await session.execute(stmt)
        perfs = res.scalars().all()
        
        success = True
        for perf in perfs:
            print(f"Platform: {perf.platform_type}")
            print(f"  Reach: {perf.reach}")
            print(f"  Likes: {perf.likes}")
            print(f"  Fetched At: {perf.fetched_at}")
            if perf.reach == 0 or perf.likes == 0:
                success = False
                
        if success:
            print("SUCCESS! Post performance metrics have been successfully synchronized.")
        else:
            print("ERROR: Some metrics are still zero.")

if __name__ == "__main__":
    asyncio.run(test_sync_flow())
