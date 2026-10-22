"""Celery tasks. The real agent loop replaces the dummy body on Day 5-6."""
import logging
import time

from app import settings
from app.celery_app import celery_app
from app.jobs import save_job

logger = logging.getLogger(__name__)


@celery_app.task(name="run_agent")
def run_agent_task(job_id: str, question: str) -> None:
    """Process one question in the background and store the outcome in Redis.

    Args:
        job_id: Identifier the client polls with.
        question: The user's plain-English question.

    Returns:
        None. The result is written to Redis, not returned.
    """
    logger.info("Job %s started: %r", job_id, question)
    try:
        # Placeholder for the real agent: simulates slow work so the
        # "pending" state is visible when polling.
        time.sleep(settings.DUMMY_TASK_SECONDS)
        save_job(job_id, {
            "status": settings.STATUS_DONE,
            "answer": f"[dummy] You asked: {question}",
            "sql_used": "SELECT 1",
            "attempts": 1,
            "cached": False,
        })
        logger.info("Job %s finished", job_id)
    except Exception:
        # A crashing worker must not leave the job "pending" forever.
        logger.exception("Job %s crashed", job_id)
        save_job(job_id, {
            "status": settings.STATUS_FAILED,
            "reason": settings.REASON_INTERNAL_ERROR,
        })