"""Celery application instance, shared by the API (producer) and worker (consumer)."""
from celery import Celery

from app import settings

# Redis is the broker (task queue). Job results are stored by our own code
# in jobs.py, so no Celery result backend is needed.
celery_app = Celery(
    "sql_agent",
    broker=settings.REDIS_URL,
    include=["app.tasks"],   # tells the worker where our task functions live
)