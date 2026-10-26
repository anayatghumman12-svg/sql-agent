"""Celery tasks: run the agent in the background and store the outcome."""
import logging

from app import settings
from app.agent import run_agent
from app.cache import store_cached_answer
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
        result = run_agent(question)
        save_job(job_id, {
            "status": settings.STATUS_DONE,
            **result,
            "cached": False,
        })
        # Only successful answers are cached; failures are never stored.
        store_cached_answer(question, result)
        logger.info("Job %s finished", job_id)
    except Exception:
        # A crashing worker must not leave the job "pending" forever.
        logger.exception("Job %s crashed", job_id)
        save_job(job_id, {
            "status": settings.STATUS_FAILED,
            "reason": settings.REASON_INTERNAL_ERROR,
        })