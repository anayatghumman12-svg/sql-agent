"""FastAPI entry point: accepts questions and reports job status."""
import logging
import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app import settings
from app.jobs import load_job, save_job
from app.tasks import run_agent_task

logging.basicConfig(level=settings.LOG_LEVEL, format=settings.LOG_FORMAT)
logger = logging.getLogger(__name__)

app = FastAPI(title="Autonomous SQL Analysis Agent")


class AskRequest(BaseModel):
    """Body of POST /ask."""

    question: str = Field(
        min_length=settings.MIN_QUESTION_LENGTH,
        max_length=settings.MAX_QUESTION_LENGTH,
    )


class AskResponse(BaseModel):
    """Response of POST /ask."""

    job_id: str


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    """Queue a question for the agent and return a job id immediately.

    Args:
        req: Request body containing the question.

    Returns:
        AskResponse with the job id to poll.
    """
    job_id = uuid.uuid4().hex
    # Save "pending" BEFORE queuing: otherwise a fast worker could finish and
    # write "done", and our pending write would then overwrite it.
    save_job(job_id, {"status": settings.STATUS_PENDING})
    run_agent_task.delay(job_id, req.question)
    logger.info("Queued job %s", job_id)
    return AskResponse(job_id=job_id)


@app.get("/status/{job_id}")
def status(job_id: str) -> dict:
    """Return the current state of a job.

    Args:
        job_id: Id returned by POST /ask.

    Returns:
        The job state (pending, done, or failed).

    Raises:
        HTTPException: 404 if the job id is unknown or expired.
    """
    job = load_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    return job