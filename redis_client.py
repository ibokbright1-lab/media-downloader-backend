import os
import redis
import json

def get_redis_connection():
    """
    Creates a Redis connection that works:
    - On Render (uses REDIS_URL)
    - Locally (falls back to localhost)
    """

    redis_url = os.environ.get("REDIS_URL")

    if redis_url:
        # Production / Render
        return redis.from_url(redis_url, decode_responses=True)

    # Local development fallback
    return redis.Redis(
        host="localhost",
        port=6379,
        db=0,
        decode_responses=True
    )


# Create a single reusable connection
r = get_redis_connection()


def cache_metadata(url: str, data: dict, expire_seconds: int = 3600):
    r.setex(f"metadata:{url}", expire_seconds, json.dumps(data))


def get_cached_metadata(url: str):
    data = r.get(f"metadata:{url}")
    if data:
        return json.loads(data)
    return None


def set_task_state(task_id: str, state: dict):
    r.set(f"task:{task_id}", json.dumps(state))


def get_task_state(task_id: str):
    data = r.get(f"task:{task_id}")
    if data:
        return json.loads(data)
    return None


def delete_task_state(task_id: str):
    r.delete(f"task:{task_id}")
