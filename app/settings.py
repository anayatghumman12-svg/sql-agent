"""Central configuration. Every hardcoded value lives here."""
import os

# Redis
REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
CACHE_TTL_SECONDS: int = 60 * 60 * 24      # cached answers 24 ghante rahenge
JOB_TTL_SECONDS: int = 60 * 60 * 24

# Postgres
DATABASE_URL: str = os.getenv(
    "DATABASE_URL", "postgresql://agent_ro:agent_ro@postgres:5432/shop"
)
# "anthropic" or "google". Lets us switch model provider from .env alone.
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "anthropic")
# Agent
MAX_ATTEMPTS: int = 3
LLM_MODEL: str = os.getenv("LLM_MODEL", "claude-sonnet-4-6")
LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
SQL_ROW_LIMIT: int = 200                    # result ka max size model ko dikhane ke liye
SQL_TIMEOUT_MS: int = 10_000

# Job status values
STATUS_PENDING: str = "pending"
STATUS_DONE: str = "done"
STATUS_FAILED: str = "failed"
# Logging
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT: str = "%(asctime)s %(levelname)s %(name)s: %(message)s"

# Redis key layout: each job lives under "job:<id>"
JOB_KEY_PREFIX: str = "job:"

# Request validation
MIN_QUESTION_LENGTH: int = 3
MAX_QUESTION_LENGTH: int = 500

# Placeholder task (replaced by the real agent on Day 5-6)
DUMMY_TASK_SECONDS: int = 5

# Failure message when the worker itself crashes
REASON_INTERNAL_ERROR: str = "Internal error while processing the job"
# Cache
CACHE_KEY_PREFIX: str = "cache:"
# Normalisation removes everything except word characters and whitespace,
# so "Total revenue?" and "total revenue" map to the same cache entry.
NORMALIZE_STRIP_PATTERN: str = r"[^\w\s]"
# Fields of a finished job that are worth reusing. Status and the cached
# flag are per-job, so they are not stored.
CACHED_FIELDS: tuple[str, ...] = ("answer", "sql_used", "attempts")
# LLM call behaviour. Temperature 0 keeps SQL generation as repeatable as possible.
LLM_TEMPERATURE: float = 0.0
LLM_MAX_TOKENS: int = 1024
LLM_TIMEOUT_SECONDS: int = 60
LLM_MAX_RETRIES: int = 2          # network-level retries inside the SDK, not agent attempts

# Database access
DB_CONNECT_TIMEOUT_SECONDS: int = 5
SCHEMA_NAME: str = "public"
# Text columns with at most this many distinct values get their values
# listed in the schema description (e.g. order status), so the model can
# see what the data actually contains.
SCHEMA_MAX_DISTINCT_VALUES: int = 15
SCHEMA_PROFILED_TYPES: tuple[str, ...] = ("text", "character varying")