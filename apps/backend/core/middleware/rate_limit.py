"""NFR-4: Rate limiting middleware via slowapi."""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from core.config import settings


def create_limiter() -> Limiter:
    """Create a slowapi Limiter backed by Redis for distributed rate limiting.

    Redis-backed rate limits are shared across all gateway replicas,
    ensuring consistent enforcement during horizontal scaling (NFR-2).
    """
    return Limiter(
        key_func=get_remote_address,
        storage_uri=settings.REDIS_URL,
        default_limits=[settings.RATE_LIMIT_PUBLIC],
    )
