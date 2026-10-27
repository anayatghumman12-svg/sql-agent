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
        outcome = run_agent(question)
        # Routing on the agent's own outcome (trusted answer vs gave up).
        if outcome.succeeded:
            result = {
                "answer": outcome.answer,
                "sql_used": outcome.sql_used,
                "attempts": outcome.attempts,
            }
            save_job(job_id, {
                "status": settings.STATUS_DONE,
                **result,
                "cached": False,
            })
            # Only trusted answers are cached; failures never are.
            store_cached_answer(question, result)
        else:
            # sql_used and attempts stay visible even on failure.
            save_job(job_id, {
                "status": settings.STATUS_FAILED,
                "reason": outcome.reason,
                "sql_used": outcome.sql_used,
                "attempts": outcome.attempts,
            })
        logger.info(
            "Job %s finished (succeeded=%s, attempts=%d)",
            job_id, outcome.succeeded, outcome.attempts,
        )
    except Exception as exc:
        # A crashing worker must not leave the job "pending" forever.
        logger.exception("Job %s crashed", job_id)
        save_job(job_id, {
            "status": settings.STATUS_FAILED,
            "reason": f"{settings.REASON_INTERNAL_ERROR} ({type(exc).__name__})",
        })