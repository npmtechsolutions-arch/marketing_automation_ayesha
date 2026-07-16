import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.post import Post, PostStatus
from app.api.v1.endpoints.posts import publish_to_platforms

logger = logging.getLogger(__name__)

async def check_and_publish_scheduled_posts():
    async with AsyncSessionLocal() as session:
        try:
            now = datetime.now(timezone.utc)
            # Find posts with status SCHEDULED whose scheduled_at is in the past (<= now)
            result = await session.execute(
                select(Post).where(
                    Post.status == PostStatus.SCHEDULED,
                    Post.scheduled_at <= now,
                    Post.deleted_at.is_(None)
                )
            )
            scheduled_posts = result.scalars().all()
            if scheduled_posts:
                logger.info(f"Found {len(scheduled_posts)} scheduled posts to publish.")
            for post in scheduled_posts:
                logger.info(f"Automatically transitioning scheduled post {post.id} to PUBLISHING.")
                post.status = PostStatus.PUBLISHING
                await session.flush()
                # Commit immediately so other loop iterations or processes don't pick it up
                await session.commit()
                
                # Start the publishing task in the background
                asyncio.create_task(publish_to_platforms(post.id))
        except Exception as e:
            logger.error(f"Error in check_and_publish_scheduled_posts: {e}")

async def scheduled_post_worker():
    logger.info("Starting scheduled post background worker loop...")
    while True:
        try:
            await check_and_publish_scheduled_posts()
        except Exception as e:
            logger.error(f"Error in scheduled_post_worker loop iteration: {e}")
        await asyncio.sleep(10) # check every 10 seconds
