from celery.schedules import crontab

from app.workers.celery_app import celery_app

# ---------------------------------------------------------------------------
# Celery Beat periodic task schedule
# ---------------------------------------------------------------------------

celery_app.conf.beat_schedule = {
    # Fetch engagement metrics for all published posts every 6 hours
    "fetch_all_post_performance": {
        "task": "app.workers.tasks.fetch_post_performance",
        "schedule": crontab(minute=0, hour="*/6"),
        "args": ("__all__",),
        "options": {"queue": "metrics"},
    },
    # Delete notifications older than 90 days - daily at midnight UTC
    "cleanup_old_notifications": {
        "task": "app.workers.tasks.cleanup_old_notifications",
        "schedule": crontab(minute=0, hour=0),
        "options": {"queue": "maintenance"},
    },
    # Permanently purge users soft-deleted past the retention window - daily at 3:30 AM UTC
    "purge_soft_deleted_users": {
        "task": "app.workers.tasks.purge_soft_deleted_users",
        "schedule": crontab(minute=30, hour=3),
        "options": {"queue": "maintenance"},
    },
    # Refresh OAuth tokens expiring within the next 24 hours - every 12 hours
    "refresh_expiring_tokens": {
        "task": "app.workers.tasks.refresh_expiring_tokens",
        "schedule": crontab(minute=0, hour="*/12"),
        "options": {"queue": "maintenance"},
    },
    # Aggregate daily analytics for all accounts - daily at 1 AM UTC
    "aggregate_daily_analytics": {
        "task": "app.workers.tasks.aggregate_analytics",
        "schedule": crontab(minute=0, hour=1),
        "args": ("__all__", "daily"),
        "options": {"queue": "analytics"},
    },
}
