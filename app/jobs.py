"""Read and write job state in Redis."""
import json
import logging
from typing import Any, Optional

import redis

from app import settings

logger = logging.getLogger(__name__)

# One shared client; decode_responses returns str instead of bytes.
_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def _key(job_id: str) -> str:
    """Build the Redis key for a job.

    Args:
        job_id: Unique job identifier.

    Returns:
        The namespaced Redis key, e.g. "job:abc123".
    """
    return f"{settings.JOB_KEY_PREFIX}{job_id}"


def save_job(job_id: str, data: dict[str, Any]) -> None:
    """Store (or overwrite) a job's state with an expiry.

    Args:
        job_id: Unique job identifier.
        data: JSON-serialisable job state (status, answer, sql_used, ...).

    Returns:
        None.

    Raises:
        redis.RedisError: If Redis is unreachable (logged, then re-raised).
    """
    try:
        _client.set(_key(job_id), json.dumps(data), ex=settings.JOB_TTL_SECONDS)
    except redis.RedisError:
        logger.exception("Failed to save job %s", job_id)
        raise


def load_job(job_id: str) -> Optional[dict[str, Any]]:
    """Fetch a job's state.

    Args:
        job_id: Unique job identifier.

    Returns:
        The job state dict, or None if the job does not exist or has expired.

    Raises:
        redis.RedisError: If Redis is unreachable (logged, then re-raised).
    """
    try:
        raw = _client.get(_key(job_id))
    except redis.RedisError:
        logger.exception("Failed to load job %s", job_id)
        raise
    return json.loads(raw) if raw else None