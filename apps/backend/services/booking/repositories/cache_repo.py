"""FR-4: Cache invalidation and lookup interface."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    import redis.asyncio as aioredis

logger = structlog.get_logger()


class CacheRepository:
    """Redis cache operations — SRP, NFR-6, NFR-7.

    All public methods are failure-tolerant; callers wrap in try/except
    so Redis outages never break API responses (AGENTS.md).
    """

    def __init__(self, redis_client: aioredis.Redis | None = None) -> None:
        self.redis = redis_client

    async def invalidate(self, key: str) -> None:
        """FR-4: Invalidate cache key. Called post-commit, failure-tolerant."""
        if self.redis is None:
            return
        await self.redis.delete(key)

    async def get(self, key: str) -> str | None:
        """FR-4: Read-through cache for catalog endpoints."""
        if self.redis is None:
            return None
        result = await self.redis.get(key)
        if isinstance(result, bytes):
            return result.decode()
        return result

    async def set(self, key: str, value: str, ttl: int = 300) -> None:
        """FR-4: Write cache with short TTL."""
        if self.redis is None:
            return
        await self.redis.set(key, value, ex=ttl)
