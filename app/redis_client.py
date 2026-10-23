"""One shared Redis client for job state and the answer cache."""
import redis

from app import settings

# decode_responses=True returns str instead of bytes.
client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)