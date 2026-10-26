"""Agent v1: generate SQL, run it once, explain the result in plain English.

The self-review and retry loop is added on Day 6; for now there is exactly one
attempt and no judgment about the result.
"""
import json
import logging
from functools import lru_cache
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

from app import prompts, settings
from app.db import QueryResult, describe_schema, execute_query

logger = logging.getLogger(__name__)


class SQLPlan(BaseModel):
    """Structured output of the SQL-generation call.

    Field order matters: `reasoning` comes first so the model thinks before
    it commits to a query.
    """

    reasoning: str = Field(
        description="Brief reasoning: which tables, columns and filters the question needs."
    )
    sql: str = Field(description="One read-only PostgreSQL SELECT statement.")


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


def _message_text(reply: Any) -> str:
    """Extract plain text from a chat model reply.

    Args:
        reply: An AIMessage whose content is a string or a list of blocks.

    Returns:
        The concatenated text.
    """
    content = reply.content
    if isinstance(content, str):
        return content
    return "".join(
        block.get("text", "") for block in content if isinstance(block, dict)
    )


def generate_sql(question: str) -> SQLPlan:
    """Ask the model to write SQL for a question.

    Args:
        question: The user's plain-English question.

    Returns:
        The model's reasoning and SQL.
    """
    messages = [
        ("system", prompts.SQL_SYSTEM_PROMPT),
        ("human", f"Database schema:\n{_schema()}\n\nQuestion: {question}"),
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
            "rows": result.rows,
            "truncated": result.truncated,
        },
        default=str,
    )


def summarize(question: str, query: str, result: QueryResult) -> str:
    """Turn a query result into a plain-English answer.

    Args:
        question: The user's question.
        query: The SQL that produced the result.
        result: The rows returned by the database.

    Returns:
        A short human-readable answer.
    """
    messages = [
        ("system", prompts.SUMMARY_SYSTEM_PROMPT),
        (
            "human",
            f"Question: {question}\n\nSQL used:\n{query}\n\n"
            f"Result:\n{_result_as_text(result)}",
        ),
    ]
    return _message_text(_llm().invoke(messages)).strip()


def run_agent(question: str) -> dict[str, Any]:
    """Answer one question with a single generate -> execute -> summarise pass.

    Args:
        question: The user's plain-English question.

    Returns:
        A dict with `answer`, `sql_used` and `attempts` (always 1 for now).

    Raises:
        Exception: Any LLM, database or SQL error; the Celery task turns it
            into a failed job.
    """
    plan = generate_sql(question)
    result = execute_query(plan.sql)
    logger.info("Query returned %d row(s)", len(result.rows))
    answer = summarize(question, plan.sql, result)
    return {"answer": answer, "sql_used": plan.sql, "attempts": 1}