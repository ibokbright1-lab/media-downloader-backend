import os
from celery import Celery

redis_url = os.environ.get("REDIS_URL", "redis://red-d6jtkn75r7bs739qu5v0:6379")

celery_app = Celery(
    "tasks",
    broker=redis_url,
    backend=redis_url,
)

