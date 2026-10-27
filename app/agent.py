"""Autonomous SQL agent: generate SQL, run it, review its own result, retry.

The agent (the model) decides whether a result is trustworthy. Python only
routes on that decision (accept / retry / give up) and enforces the attempt cap.
"""
import json
import logging
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache

import psycopg2
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field, model_validator

from app import prompts, settings
from app.db import QueryResult, describe_schema, execute_query

logger = logging.getLogger(__name__)


class Decision(str, Enum):
    """What the agent decides after reviewing its own result."""

    ACCEPT = "accept"
    RETRY = "retry"
    GIVE_UP = "give_up"


class SQLPlan(BaseModel):
    """Structured output of the SQL-generation call.

    Field order matters: `reasoning` comes first so the model thinks before
    it commits to a query.
    """

    reasoning: str = Field(
        description="Brief reasoning: which tables, columns and filters the question needs."
    )
    sql: str = Field(description="One read-only PostgreSQL SELECT statement.")


class Review(BaseModel):
    """Structured output of the self-review call (the agent's judgment)."""

    analysis: str = Field(
        description="Step-by-step assessment of whether the outcome can be trusted."
    )
    decision: Decision = Field(description="accept, retry or give_up.")
    answer: str = Field(
        default="",
        description="Final plain-English answer. Required when decision is accept.",
    )
    feedback: str = Field(
        default="",
        description="Required for retry (what to change) and give_up (why).",
    )

    @model_validator(mode="after")
    def _check_required_text(self) -> "Review":
        """Reject malformed outputs where the decision lacks its required text.

        This validates the SHAPE of the model's output; it does not judge
        whether the decision itself is right.

        Returns:
            The validated review.

        Raises:
            ValueError: If an accept has no answer, or a retry/give_up has
                no feedback.
        """
        if self.decision == Decision.ACCEPT and not self.answer.strip():
            raise ValueError("accept requires an answer")
        if self.decision != Decision.ACCEPT and not self.feedback.strip():
            raise ValueError("retry and give_up require feedback")
        return self


@dataclass
class Attempt:
    """One finished attempt, kept so the next attempt can learn from it."""

    number: int
    sql: str
    observation: str
    analysis: str
    feedback: str


@dataclass
class AgentOutcome:
    """Final result of the agent loop, handed back to the Celery task."""

    succeeded: bool
    attempts: int
    sql_used: str
    answer: str = ""
    reason: str = ""


@lru_cache(maxsize=1)
def _llm() -> BaseChatModel:
    """Create the chat model once per worker process.

    The provider is chosen by settings.LLM_PROVIDER so the rest of the agent
    does not care which vendor answers.

    Returns:
        A configured chat model.

    Raises:
        RuntimeError: If LLM_API_KEY is not set.
    """
    if not settings.LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY is not set; add it to .env")

    if settings.LLM_PROVIDER == "google":
        # Imported lazily so the Anthropic path works without this package.
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.LLM_MODEL,
            google_api_key=settings.LLM_API_KEY,
            temperature=settings.LLM_TEMPERATURE,
            max_output_tokens=settings.LLM_MAX_TOKENS,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            max_retries=settings.LLM_MAX_RETRIES,
        )

    return ChatAnthropic(
        model=settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        timeout=settings.LLM_TIMEOUT_SECONDS,
        max_retries=settings.LLM_MAX_RETRIES,
    )


@lru_cache(maxsize=1)
def _schema() -> str:
    """Read the schema once per worker process (it does not change at runtime).

    Returns:
        The schema description from the database.
    """
    return describe_schema()


def _history_text(history: list[Attempt]) -> str:
    """Format earlier attempts so the model can revise its approach.

    Args:
        history: Attempts made so far for this question (may be empty).

    Returns:
        A text block, or an empty string when there were no earlier attempts.
    """
    if not history:
        return ""
    blocks = [
        f"Attempt {a.number}\nSQL:\n{a.sql}\nOutcome:\n{a.observation}\n"
        f"Reviewer feedback: {a.feedback}"
        for a in history
    ]
    return "\n\nEarlier attempts that were rejected:\n\n" + "\n\n".join(blocks)


def generate_sql(question: str, history: list[Attempt]) -> SQLPlan:
    """Ask the model to write (or revise) SQL for a question.

    Args:
        question: The user's plain-English question.
        history: Earlier rejected attempts with the reviewer's feedback.

    Returns:
        The model's reasoning and SQL.
    """
    messages = [
        ("system", prompts.SQL_SYSTEM_PROMPT),
        (
            "human",
            f"Database schema:\n{_schema()}\n\nQuestion: {question}"
            f"{_history_text(history)}",
        ),
    ]
    plan = _llm().with_structured_output(SQLPlan).invoke(messages)
    logger.info("Model reasoning: %s", plan.reasoning)
    logger.info("Generated SQL: %s", plan.sql)
    return plan


def _result_as_text(result: QueryResult) -> str:
    """Serialise a query result so it can be shown to the model.

    Args:
        result: The rows returned by the database.

    Returns:
        A JSON string (dates and decimals are converted with str()).
    """
    return json.dumps(
        {
            "columns": result.columns,
            "row_count": len(result.rows),
            "rows": result.rows,
            "truncated": result.truncated,
        },
        default=str,
    )


def _observe(query: str) -> str:
    """Run the SQL and describe what happened, as text for the reviewer.

    A database error is not judged here: it is turned into text so the
    reviewing model sees it and decides what to do about it.

    Args:
        query: The SQL produced by the model.

    Returns:
        JSON text with either the result rows or an error message.
    """
    try:
        return _result_as_text(execute_query(query))
    except (psycopg2.Error, ValueError) as exc:
        logger.warning("Query failed: %s", exc)
        message = str(exc)[: settings.ERROR_TEXT_MAX_CHARS]
        return json.dumps({"error": message})


def review_result(
    question: str, plan: SQLPlan, observation: str, attempt_number: int
) -> Review:
    """Let the model judge its own result and decide what happens next.

    Args:
        question: The user's question.
        plan: The SQL the model wrote for this attempt.
        observation: The result rows or error text from running that SQL.
        attempt_number: Which attempt this is (1-based).

    Returns:
        The model's analysis and decision.
    """
    messages = [
        ("system", prompts.REVIEW_SYSTEM_PROMPT),
        (
            "human",
            f"Database schema:\n{_schema()}\n\nQuestion: {question}\n\n"
            f"This is attempt {attempt_number} of {settings.MAX_ATTEMPTS}.\n\n"
            f"SQL:\n{plan.sql}\n\nOutcome:\n{observation}",
        ),
    ]
    review = _llm().with_structured_output(Review).invoke(messages)
    logger.info(
        "Attempt %d review: decision=%s | %s",
        attempt_number, review.decision.value, review.analysis,
    )
    return review


def run_agent(question: str) -> AgentOutcome:
    """Answer one question, retrying until the agent trusts its result.

    Args:
        question: The user's plain-English question.

    Returns:
        An AgentOutcome: a trusted answer, or an honest failure with a reason.

    Raises:
        Exception: Infrastructure errors (LLM unreachable, database down);
            the Celery task turns them into a failed job.
    """
    history: list[Attempt] = []

    for attempt_number in range(1, settings.MAX_ATTEMPTS + 1):
        plan = generate_sql(question, history)
        observation = _observe(plan.sql)
        review = review_result(question, plan, observation, attempt_number)

        # Python only ROUTES on the agent's decision; it never makes one.
        if review.decision == Decision.ACCEPT:
            return AgentOutcome(
                succeeded=True,
                attempts=attempt_number,
                sql_used=plan.sql,
                answer=review.answer.strip(),
            )
        if review.decision == Decision.GIVE_UP:
            return AgentOutcome(
                succeeded=False,
                attempts=attempt_number,
                sql_used=plan.sql,
                reason=settings.REASON_GAVE_UP.format(
                    attempts=attempt_number, detail=review.feedback.strip()
                ),
            )
        history.append(Attempt(
            number=attempt_number,
            sql=plan.sql,
            observation=observation,
            analysis=review.analysis,
            feedback=review.feedback,
        ))

    # The agent kept asking to retry and the attempt cap was reached:
    # say so honestly instead of guessing.
    return AgentOutcome(
        succeeded=False,
        attempts=settings.MAX_ATTEMPTS,
        sql_used=history[-1].sql,
        reason=settings.REASON_NOT_CONFIDENT.format(
            max_attempts=settings.MAX_ATTEMPTS
        ),
    )