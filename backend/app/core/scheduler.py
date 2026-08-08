import asyncio
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.post import Post, PostStatus
from app.api.v1.endpoints.posts import publish_to_platforms

logger = logging.getLogger(__name__)

# A post normally finishes publishing within a few minutes, but a worst-case
# multi-target post can legitimately run ~13 min (YouTube's 600s upload timeout +
# 180s image->video render + Instagram's 120s processing poll). Only treat a post
# as stranded (owner process died mid-publish) well beyond that, so we never reset
# one that is genuinely still uploading.
STUCK_PUBLISHING_MINUTES = 20
# How many times to auto-retry a stuck post before giving up and marking FAILED.
MAX_PUBLISH_RETRIES = 3

# Hold strong references to in-flight publish tasks. asyncio only keeps a weak
# reference to tasks created with create_task(), so without this a running
# publish can be garbage-collected mid-flight — leaving the post stuck in
# PUBLISHING and never actually posted. Discard each task when it completes.
_running_publish_tasks: set[asyncio.Task] = set()


def _spawn_publish(post_id) -> None:
    task = asyncio.create_task(publish_to_platforms(post_id))
    _running_publish_tasks.add(task)
    task.add_done_callback(_running_publish_tasks.discard)


async def recover_stuck_publishing_posts():
    """Reset posts stranded in PUBLISHING (owner process died mid-publish).

    Retries them up to MAX_PUBLISH_RETRIES, then marks them FAILED so the user
    can see and act on them instead of them being silently stuck forever.
    """
    async with AsyncSessionLocal() as session:
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=STUCK_PUBLISHING_MINUTES)
            result = await session.execute(
                select(Post)
                .where(
                    Post.status == PostStatus.PUBLISHING,
                    Post.updated_at < cutoff,
                    Post.deleted_at.is_(None),
                )
                .with_for_update(skip_locked=True)
            )
            stuck = result.scalars().all()
            if not stuck:
                return

            for post in stuck:
                if (post.retry_count or 0) < MAX_PUBLISH_RETRIES:
                    post.retry_count = (post.retry_count or 0) + 1
                    post.status = PostStatus.SCHEDULED
                    post.scheduled_at = datetime.now(timezone.utc)
                    post.error_message = None
                    logger.warning(
                        "Recovering stuck post %s (retry %d/%d).",
                        post.id, post.retry_count, MAX_PUBLISH_RETRIES,
                    )
                else:
                    post.status = PostStatus.FAILED
                    post.error_message = (
                        "Publishing was interrupted repeatedly (server restart or "
                        "timeout). Please try publishing again."
                    )
                    logger.error(
                        "Giving up on stuck post %s after %d retries.",
                        post.id, post.retry_count,
                    )
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Error recovering stuck publishing posts: {e}")


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
    # overwhelming the server. References are held so they aren't GC'd mid-run.
    for post_id in post_ids:
        logger.info(f"Publishing scheduled post {post_id}.")
        _spawn_publish(post_id)


async def scheduled_post_worker():
    logger.info("Starting scheduled post background worker loop...")
    while True:
        try:
            await check_and_publish_scheduled_posts()
            await recover_stuck_publishing_posts()
        except Exception as e:
            logger.error(f"Error in scheduled_post_worker loop iteration: {e}")
        await asyncio.sleep(10)  # check every 10 seconds
