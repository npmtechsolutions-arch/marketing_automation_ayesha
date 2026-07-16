import logging
from datetime import datetime, timedelta, timezone

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Post publishing
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def publish_post(self, post_id: str):
    """Fetch a scheduled post from the DB, publish to each connected platform,
    and update the post status accordingly."""
    try:
        logger.info("Publishing post %s", post_id)

        # TODO: Replace with real DB session
        # post = db.query(Post).filter(Post.id == post_id).first()
        # if not post:
        #     logger.error("Post %s not found", post_id)
        #     return {"status": "error", "message": "Post not found"}

        # Placeholder: iterate connected platforms and publish
        platforms_published = []
        platforms_failed = []

        # from app.services.platform_service import PlatformService
        # for platform in post.platforms:
        #     try:
        #         result = PlatformService.publish(post, platform)
        #         platforms_published.append(platform.platform_type)
        #     except Exception:
        #         platforms_failed.append(platform.platform_type)

        # Update post status
        # post.status = "published" if not platforms_failed else "partially_failed"
        # post.published_at = datetime.now(timezone.utc)
        # db.commit()

        # Create notification for the user
        # Notification.create(user_id=post.user_id, type="post_published", ...)

        logger.info(
            "Post %s published to %s, failed on %s",
            post_id,
            platforms_published or "none",
            platforms_failed or "none",
        )
        return {
            "status": "published",
            "published": platforms_published,
            "failed": platforms_failed,
        }
    except Exception as exc:
        logger.exception("Failed to publish post %s", post_id)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Performance metrics
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def fetch_post_performance(self, post_id: str):
    """Fetch engagement metrics from each platform for a published post and
    store them in the post_performance table."""
    try:
        logger.info("Fetching performance for post %s", post_id)

        # TODO: Replace with real DB + platform API calls
        # post = db.query(Post).filter(Post.id == post_id).first()
        # for platform in post.platforms:
        #     metrics = PlatformService.fetch_performance(post_id, platform)
        #     PostPerformance.upsert(post_id=post_id, platform=platform.type, **metrics)
        # db.commit()

        return {"status": "success", "post_id": post_id}
    except Exception as exc:
        logger.exception("Failed to fetch performance for post %s", post_id)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# AI content generation
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_ai_content(
    self,
    generation_id: str,
    prompt: str,
    platforms: list[str],
    tone: str,
):
    """Call the AI service to generate marketing content and update the
    ai_generations record with the result."""
    try:
        logger.info("Generating AI content for generation %s", generation_id)

        # TODO: Replace with real implementation
        # from app.services.ai_service import AIService
        # result = AIService.generate_content(
        #     prompt=prompt,
        #     platforms=platforms,
        #     tone=tone,
        #     business_context={},
        # )
        # generation = db.query(AIGeneration).filter(AIGeneration.id == generation_id).first()
        # generation.result = result
        # generation.status = "completed"
        # db.commit()

        return {"status": "completed", "generation_id": generation_id}
    except Exception as exc:
        logger.exception("AI generation %s failed", generation_id)
        # Mark generation as failed
        # generation.status = "failed"
        # generation.error = str(exc)
        # db.commit()
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_email(self, to: str, subject: str, template: str, context: dict):
    """Send a transactional email via SendGrid."""
    try:
        logger.info("Sending email to %s: %s", to, subject)

        # TODO: Replace with real SendGrid implementation
        # from app.services.email_service import EmailService
        # EmailService.send(to=to, subject=subject, template=template, context=context)

        return {"status": "sent", "to": to}
    except Exception as exc:
        logger.exception("Failed to send email to %s", to)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Platform sync
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def sync_platform_metrics(self, platform_id: str):
    """Sync follower counts and account-level metrics for a connected
    platform."""
    try:
        logger.info("Syncing metrics for platform %s", platform_id)

        # TODO: Replace with real implementation
        # platform = db.query(ConnectedPlatform).filter(...).first()
        # metrics = PlatformService.fetch_account_metrics(platform)
        # platform.follower_count = metrics["followers"]
        # platform.last_synced_at = datetime.now(timezone.utc)
        # db.commit()

        return {"status": "synced", "platform_id": platform_id}
    except Exception as exc:
        logger.exception("Failed to sync platform %s", platform_id)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Analytics aggregation
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def aggregate_analytics(self, account_id: str, period: str = "daily"):
    """Aggregate post performance data into summary analytics for the
    given account and time period."""
    try:
        logger.info(
            "Aggregating %s analytics for account %s", period, account_id
        )

        # TODO: Replace with real aggregation logic
        # posts = db.query(Post).filter(Post.account_id == account_id, ...).all()
        # totals = {"impressions": 0, "engagements": 0, "clicks": 0, ...}
        # for post in posts:
        #     for perf in post.performance:
        #         totals["impressions"] += perf.impressions
        #         ...
        # AnalyticsSummary.upsert(account_id=account_id, period=period, **totals)
        # db.commit()

        return {"status": "aggregated", "account_id": account_id, "period": period}
    except Exception as exc:
        logger.exception("Failed to aggregate analytics for account %s", account_id)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Maintenance
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def cleanup_old_notifications(self):
    """Delete notifications older than 90 days."""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        logger.info("Cleaning up notifications older than %s", cutoff.isoformat())

        # TODO: Replace with real DB cleanup
        # deleted = db.query(Notification).filter(Notification.created_at < cutoff).delete()
        # db.commit()
        # logger.info("Deleted %d old notifications", deleted)

        return {"status": "cleaned", "cutoff": cutoff.isoformat()}
    except Exception as exc:
        logger.exception("Failed to clean up notifications")
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def purge_soft_deleted_users(self, retention_days: int | None = None):
    """Permanently delete users soft-deleted more than ``retention_days`` ago.

    This is the irreversible second stage of account deletion: the API only
    sets ``deleted_at``; this task removes the user, the workspaces they own,
    and all associated data once the retention window has elapsed.
    """
    import asyncio

    from app.core.config import settings
    from app.services.purge_service import purge_soft_deleted_users as _purge

    try:
        days = retention_days if retention_days is not None else settings.SOFT_DELETE_RETENTION_DAYS
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        logger.info(
            "Purging users soft-deleted before %s (retention %d days)",
            cutoff.isoformat(),
            days,
        )

        summary = asyncio.run(_purge(cutoff))

        logger.info(
            "Purge complete: removed %d users and %d accounts",
            summary["users"],
            summary["accounts"],
        )
        return {"status": "purged", "cutoff": cutoff.isoformat(), **summary}
    except Exception as exc:
        logger.exception("Failed to purge soft-deleted users")
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def refresh_expiring_tokens(self):
    """Check for platform OAuth tokens expiring within 24 hours and
    attempt to refresh them."""
    try:
        expiry_threshold = datetime.now(timezone.utc) + timedelta(hours=24)
        logger.info(
            "Refreshing tokens expiring before %s", expiry_threshold.isoformat()
        )

        # TODO: Replace with real token refresh logic
        # platforms = db.query(ConnectedPlatform).filter(
        #     ConnectedPlatform.token_expires_at < expiry_threshold,
        #     ConnectedPlatform.token_expires_at > datetime.now(timezone.utc),
        # ).all()
        # refreshed = 0
        # for platform in platforms:
        #     try:
        #         new_token = PlatformService.refresh_token(platform)
        #         platform.access_token = new_token["access_token"]
        #         platform.token_expires_at = new_token["expires_at"]
        #         refreshed += 1
        #     except Exception:
        #         logger.warning("Could not refresh token for platform %s", platform.id)
        # db.commit()
        # logger.info("Refreshed %d / %d expiring tokens", refreshed, len(platforms))

        return {"status": "refreshed"}
    except Exception as exc:
        logger.exception("Failed to refresh expiring tokens")
        raise self.retry(exc=exc)
