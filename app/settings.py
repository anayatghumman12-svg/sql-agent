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