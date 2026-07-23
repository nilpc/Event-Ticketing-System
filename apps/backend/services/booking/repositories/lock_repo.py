"""FR-6, FR-7: Repository for Redis-based queue, seat locks, and user hold limits."""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import RedisUnavailableError
from core.redis import get_redis

logger = structlog.get_logger()

# Lua CAS script for safe seat lock release.
# Only deletes if the current value matches the expected user_id.
_RELEASE_SEAT_LOCK_LUA = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""

# Lua script for re-entrant seat lock acquisition.
# Returns 1 if lock acquired or refreshed (same user), 0 if held by another user.
_ACQUIRE_SEAT_LOCK_LUA = """
local current = redis.call("GET", KEYS[1])
if current == false then
    return redis.call("SET", KEYS[1], ARGV[1], "EX", ARGV[2]) and 1 or 0
elseif current == ARGV[1] then
    redis.call("EXPIRE", KEYS[1], ARGV[2])
    return 1
else
    return 0
end
"""


class LockRepository:
    """Redis lock/state operations — SRP, NFR-6.

    DB session accepted for interface consistency; real implementation
    delegates to redis.asyncio.
    """

    def __init__(
        self, session: AsyncSession | None = None, redis_client: object | None = None
    ) -> None:
        self.session = session
        self._redis = redis_client  # injected; falls back to singleton

    @property
    def redis(self):
        if self._redis is not None:
            return self._redis
        try:
            return get_redis()
        except Exception:
            logger.warning("redis_unavailable")
            return None

    # --- Seat Locking (FR-7) ---

    async def acquire_seat_lock(
        self, show_id: UUID, seat_id: str, user_id: UUID, ttl: int = 600
    ) -> bool:
        """FR-7: Re-entrant lock — SET if free, refresh if same user, reject if another user."""
        if self.redis is None:
            raise RedisUnavailableError("Redis unavailable — cannot acquire seat lock.")
        key = f"seat_lock:{show_id}:{seat_id}"
        result = await self.redis.eval(
            _ACQUIRE_SEAT_LOCK_LUA, 1, key, str(user_id), ttl
        )
        return int(result) == 1

    async def get_seat_lock(self, show_id: UUID, seat_id: str) -> UUID | None:
        """FR-7: Read current lock holder."""
        if self.redis is None:
            return None
        key = f"seat_lock:{show_id}:{seat_id}"
        val = await self.redis.get(key)
        if val is None:
            return None
        try:
            return UUID(val)
        except (ValueError, TypeError):
            return None

    async def release_seat_lock_safe(self, show_id: UUID, seat_id: str, user_id: UUID) -> None:
        """FR-7: CAS release — only free if still held by this user."""
        if self.redis is None:
            return
        key = f"seat_lock:{show_id}:{seat_id}"
        try:
            await self.redis.eval(_RELEASE_SEAT_LOCK_LUA, 1, key, str(user_id))
        except Exception:
            logger.warning("seat_lock_release_failed", show_id=str(show_id), seat_id=seat_id)

    # --- User Hold Limit (FR-7) ---

    async def acquire_user_hold(
        self, show_id: UUID, user_id: UUID, ttl: int = 600, max_holds: int = 8
    ) -> bool:
        """FR-7: Enforce per-user hold limit.

        Uses a Redis counter per (show_id, user_id) to track held seats.
        Returns False if user already holds the max (default 8, matches MAX_SEATS_PER_CHECKOUT).
        """
        if self.redis is None:
            raise RedisUnavailableError("Redis unavailable — cannot enforce hold limit.")
        hold_key = f"user_hold:{show_id}:{user_id}"
        current_count = await self.redis.incr(hold_key)
        if current_count == 1:
            await self.redis.expire(hold_key, ttl)
        if current_count > max_holds:
            await self.redis.decr(hold_key)
            return False
        return True

    async def release_user_hold_limit(self, show_id: UUID, user_id: UUID) -> None:
        """FR-7: Remove user hold after terminal booking outcome."""
        if self.redis is None:
            return
        hold_key = f"user_hold:{show_id}:{user_id}"
        try:
            await self.redis.delete(hold_key)
        except Exception:
            logger.warning("user_hold_release_failed", show_id=str(show_id), user_id=str(user_id))

    # --- Queue (FR-6) ---

    async def validate_queue_session(self, queue_token: str, user_id: UUID) -> bool:
        """FR-6: Verify queue session token belongs to user and is active."""
        if self.redis is None:
            raise RedisUnavailableError("Redis unavailable — cannot validate queue session.")
        key = f"queue:session:{queue_token}"
        stored = await self.redis.get(key)
        if stored is None:
            return False
        return stored == str(user_id)

    async def consume_queue_session(
        self,
        queue_token: str,
        show_id: UUID | None = None,
        user_id: UUID | None = None,
    ) -> None:
        """FR-6: Invalidate queue token and admitted marker after successful checkout."""
        if self.redis is None:
            return
        key = f"queue:session:{queue_token}"
        await self.redis.delete(key)
        # Also remove the admitted marker so recover() doesn't return this stale token
        if show_id is not None and user_id is not None:
            admitted_key = f"admitted:{show_id}:{user_id}"
            await self.redis.delete(admitted_key)

    # --- Idempotency (FR-8) ---

    async def is_idempotency_key_available(self, idempotency_key: str) -> bool:
        """FR-8: Redis SET NX; returns True if key was newly created."""
        if self.redis is None:
            raise RedisUnavailableError("Redis unavailable — cannot check idempotency key.")
        key = f"idempotency:{idempotency_key}"
        result = await self.redis.set(key, "1", nx=True, ex=900)
        return bool(result)

    # --- Queue Position (FR-6) ---

    async def enqueue_user(self, show_id: UUID, user_id: UUID) -> int:
        """FR-6: Add user to queue sorted set. Returns position (1-indexed)."""
        if self.redis is None:
            return 1
        import time

        queue_key = f"queue:{show_id}"
        score = time.time()
        await self.redis.zadd(queue_key, {str(user_id): score})
        pos = await self.redis.zrank(queue_key, str(user_id))
        return (pos or 0) + 1

    async def get_queue_position(self, show_id: UUID, user_id: UUID) -> int | None:
        """FR-6: Get user's position in queue. None if not in queue."""
        if self.redis is None:
            return 1
        queue_key = f"queue:{show_id}"
        pos = await self.redis.zrank(queue_key, str(user_id))
        if pos is None:
            return None
        return pos + 1

    async def is_user_admitted(self, show_id: UUID, user_id: UUID) -> bool:
        """FR-6: Check if user has been admitted from queue."""
        if self.redis is None:
            return True
        key = f"admitted:{show_id}:{user_id}"
        return bool(await self.redis.exists(key))

    async def admit_user(self, show_id: UUID, user_id: UUID, ttl: int = 600) -> str:
        """FR-6: Admit user from queue, generate and store queue token."""
        import secrets

        if self.redis is None:
            return secrets.token_urlsafe(32)
        token = secrets.token_urlsafe(32)
        # Remove from queue sorted set
        queue_key = f"queue:{show_id}"
        await self.redis.zrem(queue_key, str(user_id))
        # Store admitted session
        session_key = f"queue:session:{token}"
        await self.redis.set(session_key, str(user_id), ex=ttl)
        # Mark as admitted
        admitted_key = f"admitted:{show_id}:{user_id}"
        await self.redis.set(admitted_key, token, ex=ttl)
        return token

    async def get_admitted_token(self, show_id: UUID, user_id: UUID) -> str | None:
        """FR-6: Get existing queue token for crash recovery."""
        if self.redis is None:
            return None
        admitted_key = f"admitted:{show_id}:{user_id}"
        return await self.redis.get(admitted_key)
