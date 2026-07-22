"""FR-4: Cache invalidation and lookup interface."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

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

    async def invalidate_pattern(self, pattern: str) -> int:
        """FR-4: Delete all keys matching a glob pattern. Returns count deleted."""
        if self.redis is None:
            return 0
        try:
            keys: list[bytes] = []
            async for key in self.redis.scan_iter(match=pattern):
                keys.append(key)
            if not keys:
                return 0
            return await self.redis.delete(*keys)
        except Exception:
            logger.warning("invalidate_pattern_failed", pattern=pattern)
            return 0

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

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: int = 300,
        serialize: Callable[[Any], str] = json.dumps,
        deserialize: Callable[[str], Any] = json.loads,
    ) -> Any:
        """FR-4: Cache-aside pattern — read from cache or compute & store."""
        if self.redis is None:
            return await factory()
        try:
            cached = await self.redis.get(key)
        except Exception:
            logger.warning("cache_read_failed", key=key)
            return await factory()

        if cached is not None:
            if isinstance(cached, bytes):
                cached = cached.decode()
            return deserialize(cached)

        value = await factory()
        try:
            await self.redis.set(key, serialize(value), ex=ttl)
        except Exception:
            logger.warning("cache_write_failed", key=key)
        return value

    async def publish_invalidation(self, channel: str, data: dict[str, Any]) -> None:
        """FR-4: Publish cache invalidation event via Redis Pub/Sub."""
        if self.redis is None:
            return
        try:
            await self.redis.publish(channel, json.dumps(data))
        except Exception:
            logger.warning("publish_invalidation_failed", channel=channel)
