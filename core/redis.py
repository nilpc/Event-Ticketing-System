"""NFR-7: Redis client singleton."""

from __future__ import annotations

import redis.asyncio as aioredis

from core.config import settings

_redis_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    """Return a shared redis.asyncio client (lazy-init singleton)."""
    global _redis_client  # noqa: PLW0603
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
    return _redis_client
