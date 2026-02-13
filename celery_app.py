 
from celery import Celery

celery_app = Celery(
    "media_downloader_backend",
    broker="redis://:${REDIS_PASSWORD}@${REDIS_HOST}:${REDIS_PORT}/0",
    backend="redis://:${REDIS_PASSWORD}@${REDIS_HOST}:${REDIS_PORT}/0"
)


celery_app.conf.task_routes = {
    "downloader.download.start_download_task": {"queue": "downloads"},
}
