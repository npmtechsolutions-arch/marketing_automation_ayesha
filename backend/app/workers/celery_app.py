from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "marketengine",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Auto-discover task modules
celery_app.conf.include = [
    "app.workers.tasks",
    "app.workers.scheduler",
]
