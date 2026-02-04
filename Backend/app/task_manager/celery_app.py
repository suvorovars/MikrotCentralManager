import os
from celery import Celery
from celery.schedules import crontab

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_WORKER_CONCURRENCY = int(os.getenv("CELERY_WORKER_CONCURRENCY", "5"))
CELERY_WORKER_POOL = os.getenv("CELERY_WORKER_POOL", "prefork")
CELERY_WORKER_MAX_TASKS_PER_CHILD = int(os.getenv("CELERY_WORKER_MAX_TASKS_PER_CHILD", "100"))

celery_app = Celery(
    "task_manager",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["task_manager.worker"],
)

celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    worker_concurrency=CELERY_WORKER_CONCURRENCY,
    worker_pool=CELERY_WORKER_POOL,
    worker_max_tasks_per_child=CELERY_WORKER_MAX_TASKS_PER_CHILD,
    timezone=os.getenv("CELERY_TIMEZONE", "UTC"),
    enable_utc=True,
    beat_schedule={
        "dispatch_scheduled_tasks": {
            "task": "task_manager.worker.dispatch_scheduled_tasks",
            "schedule": crontab(minute="*/1"),
        }
    },
)
