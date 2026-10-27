"""Central configuration. Every hardcoded value lives here."""
import os

# Redis
REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
CACHE_TTL_SECONDS: int = 60 * 60 * 24      # cached answers live for 24 hours
JOB_TTL_SECONDS: int = 60 * 60 * 24
# Redis key layout: each job lives under "job:<id>"
JOB_KEY_PREFIX: str = "job:"

# Postgres
DATABASE_URL: str = os.getenv(
    "DATABASE_URL", "postgresql://agent_ro:agent_ro@postgres:5432/shop"
)
DB_CONNECT_TIMEOUT_SECONDS: int = 5
SCHEMA_NAME: str = "public"
# Text columns with at most this many distinct values get their values
# listed in the schema description (e.g. order status), so the model can
# see what the data actually contains.
SCHEMA_MAX_DISTINCT_VALUES: int = 15
SCHEMA_PROFILED_TYPES: tuple[str, ...] = ("text", "character varying")

# Agent
MAX_ATTEMPTS: int = 3
SQL_ROW_LIMIT: int = 200                    # max rows shown to the model
SQL_TIMEOUT_MS: int = 10_000

# LLM
# "anthropic" or "google". Lets us switch model provider from .env alone.
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "anthropic")
LLM_MODEL: str = os.getenv("LLM_MODEL", "claude-sonnet-4-6")
LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
# Temperature 0 keeps SQL generation as repeatable as possible.
LLM_TEMPERATURE: float = 0.0
# Generous on purpose: Gemini's internal "thinking" tokens count against this
# limit, and a structured answer can be cut off if it is too small.
LLM_MAX_TOKENS: int = 4096
LLM_TIMEOUT_SECONDS: int = 60
LLM_MAX_RETRIES: int = 2          # network-level retries inside the SDK, not agent attempts

# Job status values
STATUS_PENDING: str = "pending"
STATUS_DONE: str = "done"
STATUS_FAILED: str = "failed"

# Failure messages
REASON_INTERNAL_ERROR: str = "Internal error while processing the job"
REASON_NOT_CONFIDENT: str = (
    "Agent could not produce a confident result after {max_attempts} attempts"
)
REASON_GAVE_UP: str = "Agent gave up after {attempts} attempt(s): {detail}"
# SQL error text shown to the reviewer is cut to this length to save tokens.
ERROR_TEXT_MAX_CHARS: int = 500

# Logging
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT: str = "%(asctime)s %(levelname)s %(name)s: %(message)s"

# Request validation
MIN_QUESTION_LENGTH: int = 3
MAX_QUESTION_LENGTH: int = 500

# Cache
CACHE_KEY_PREFIX: str = "cache:"
# Normalisation removes everything except word characters and whitespace,
# so "Total revenue?" and "total revenue" map to the same cache entry.
NORMALIZE_STRIP_PATTERN: str = r"[^\w\s]"
# Fields of a finished job that are worth reusing. Status and the cached
# flag are per-job, so they are not stored.
CACHED_FIELDS: tuple[str, ...] = ("answer", "sql_used", "attempts")