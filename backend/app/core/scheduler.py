import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.post import Post, PostStatus
from app.api.v1.endpoints.posts import publish_to_platforms

logger = logging.getLogger(__name__)

async def check_and_publish_scheduled_posts():
    # Phase 1: atomically claim the due posts.
    post_ids: list = []
    async with AsyncSessionLocal() as session:
        try:
            now = datetime.now(timezone.utc)
            # Find posts with status SCHEDULED whose scheduled_at is in the past
            # (<= now). FOR UPDATE SKIP LOCKED locks the rows this worker reads so
            # a second worker / server instance skips them instead of grabbing the
            # same posts — without this, horizontal scaling would double-publish.
            result = await session.execute(
                select(Post)
                .where(
                    Post.status == PostStatus.SCHEDULED,
                    Post.scheduled_at <= now,
                    Post.deleted_at.is_(None),
                )
                .with_for_update(skip_locked=True)
            )
            scheduled_posts = result.scalars().all()
            if not scheduled_posts:
                return

            logger.info(f"Found {len(scheduled_posts)} scheduled posts to publish.")
            # Flip every claimed post to PUBLISHING and commit once, while still
            # holding the row locks. By the time the locks release, these posts no
            # longer match the SCHEDULED filter, so they can't be picked up again.
            for post in scheduled_posts:
                post.status = PostStatus.PUBLISHING
                post_ids.append(post.id)
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Error claiming scheduled posts: {e}")
            return

    # Phase 2: fire the publish tasks. They are bounded by the publish semaphore
    # inside publish_to_platforms(), so a large batch queues rather than
    # overwhelming the server.
    for post_id in post_ids:
        logger.info(f"Publishing scheduled post {post_id}.")
        asyncio.create_task(publish_to_platforms(post_id))

async def scheduled_post_worker():
    logger.info("Starting scheduled post background worker loop...")
    while True:
        try:
            await check_and_publish_scheduled_posts()
        except Exception as e:
            logger.error(f"Error in scheduled_post_worker loop iteration: {e}")
        await asyncio.sleep(10) # check every 10 seconds
