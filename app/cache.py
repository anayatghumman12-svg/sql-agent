"""Answer cache: identical (normalised) questions skip the agent entirely."""
import hashlib
import json
import logging
import re
from typing import Any, Optional

import redis

from app import settings
from app.redis_client import client

logger = logging.getLogger(__name__)


def normalize_question(question: str) -> str:
    """Reduce a question to a canonical form for cache lookups.

    Lowercases, removes punctuation and collapses repeated whitespace.
    Deliberately conservative: it does not try to match synonyms, because
    merging two genuinely different questions would return a wrong answer.

    Args:
        question: The raw question from the user.

    Returns:
        The normalised question (may be empty if it had no word characters).
    """
    lowered = question.lower()
    without_punctuation = re.sub(settings.NORMALIZE_STRIP_PATTERN, "", lowered)
    return " ".join(without_punctuation.split())


def _cache_key(normalized: str) -> str:
    """Build the Redis key for a normalised question.

    The question is hashed so the key has a fixed length and contains no
    awkward characters, however long the question is.

    Args:
        normalized: Output of normalize_question().

    Returns:
        A key such as "cache:9f86d0...".
    """
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"{settings.CACHE_KEY_PREFIX}{digest}"


def get_cached_answer(question: str) -> Optional[dict[str, Any]]:
    """Look up a previously computed answer.

    A Redis failure is logged and treated as a cache miss, so a broken cache
    slows requests down but never blocks them.

    Args:
        question: The raw question from the user.

    Returns:
        A dict with the fields in settings.CACHED_FIELDS, or None on a miss.
    """
    normalized = normalize_question(question)
    if not normalized:
        return None
    try:
        raw = client.get(_cache_key(normalized))
    except redis.RedisError:
        logger.exception("Cache read failed; falling back to the agent")
        return None
    if raw is None:
        return None
    logger.info("Cache hit for %r", normalized)
    return json.loads(raw)


def store_cached_answer(question: str, result: dict[str, Any]) -> None:
    """Save a successful answer so repeated questions can reuse it.

    Args:
        question: The raw question from the user.
        result: The finished job fields; only settings.CACHED_FIELDS are kept.

    Returns:
        None. A Redis failure is logged and swallowed, because the user
        already has their answer and only the speed-up is lost.
    """
    normalized = normalize_question(question)
    if not normalized:
        return
    payload = {field: result[field] for field in settings.CACHED_FIELDS}
    try:
        client.set(
            _cache_key(normalized),
            json.dumps(payload),
            ex=settings.CACHE_TTL_SECONDS,
        )
        logger.info("Cached answer for %r", normalized)
    except redis.RedisError:
        logger.exception("Cache write failed (answer was still delivered)")