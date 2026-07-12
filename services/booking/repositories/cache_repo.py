"""FR-4: Cache invalidation and lookup interface."""

from sqlalchemy.ext.asyncio import AsyncSession


class CacheRepository:
    """Redis cache operations — SRP, NFR-6, NFR-7.

    All public methods are failure-tolerant; callers wrap in try/except
    so Redis outages never break API responses (AGENTS.md).
    """

    def __init__(self, session: AsyncSession, redis_client: object | None = None) -> None:
        self.session = session
        self.redis = redis_client

    async def invalidate(self, key: str) -> None:
        """FR-4: Invalidate cache key. Called post-commit, failure-tolerant."""
        ...

    async def get(self, key: str) -> str | None:
        """FR-4: Read-through cache for catalog endpoints."""
        ...

    async def set(self, key: str, value: str, ttl: int = 300) -> None:
        """FR-4: Write cache with short TTL."""
        ...
