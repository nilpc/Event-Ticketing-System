from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import RedisUnavailableError
from core.redis import get_redis

logger = structlog.get_logger()
_RELEASE_SEAT_LOCK_LUA = '\nif redis.call("GET", KEYS[1]) == ARGV[1] then\n    return redis.call("DEL", KEYS[1])\nelse\n    return 0\nend\n'
_ACQUIRE_SEAT_LOCK_LUA = '\nlocal current = redis.call("GET", KEYS[1])\nif current == false then\n    return redis.call("SET", KEYS[1], ARGV[1], "EX", ARGV[2]) and 1 or 0\nelseif current == ARGV[1] then\n    redis.call("EXPIRE", KEYS[1], ARGV[2])\n    return 1\nelse\n    return 0\nend\n'


class LockRepository:
    def __init__(
        self, session: AsyncSession | None = None, redis_client: object | None = None
    ) -> None:
        self.session = session
        self._redis = redis_client

    @property
    def redis(self):
        if self._redis is not None:
            return self._redis
        try:
            return get_redis()
        except Exception:
            logger.warning("redis_unavailable")
            return None

    async def acquire_seat_lock(
        self, show_id: UUID, seat_id: str, user_id: UUID, ttl: int = 600
    ) -> bool:
        if self.redis is None:
            raise RedisUnavailableError("Redis unavailable — cannot acquire seat lock.")
        key = f"seat_lock:{show_id}:{seat_id}"
        result = await self.redis.eval(_ACQUIRE_SEAT_LOCK_LUA, 1, key, str(user_id), ttl)
        return int(result) == 1

    async def get_seat_lock(self, show_id: UUID, seat_id: str) -> UUID | None:
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
        if self.redis is None:
            return
        key = f"seat_lock:{show_id}:{seat_id}"
        try:
            await self.redis.eval(_RELEASE_SEAT_LOCK_LUA, 1, key, str(user_id))
        except Exception:
            logger.warning("seat_lock_release_failed", show_id=str(show_id), seat_id=seat_id)

    async def acquire_user_hold(
        self, show_id: UUID, user_id: UUID, ttl: int = 600, max_holds: int = 8
    ) -> bool:
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
        if self.redis is None:
            return
        hold_key = f"user_hold:{show_id}:{user_id}"
        try:
            await self.redis.delete(hold_key)
        except Exception:
            logger.warning("user_hold_release_failed", show_id=str(show_id), user_id=str(user_id))

    async def validate_queue_session(self, queue_token: str, user_id: UUID) -> bool:
        if self.redis is None:
            raise RedisUnavailableError("Redis unavailable — cannot validate queue session.")
        key = f"queue:session:{queue_token}"
        stored = await self.redis.get(key)
        if stored is None:
            return False
        return stored == str(user_id)

    async def consume_queue_session(
        self, queue_token: str, show_id: UUID | None = None, user_id: UUID | None = None
    ) -> None:
        if self.redis is None:
            return
        key = f"queue:session:{queue_token}"
        await self.redis.delete(key)
        if show_id is not None and user_id is not None:
            admitted_key = f"admitted:{show_id}:{user_id}"
            await self.redis.delete(admitted_key)

    async def is_idempotency_key_available(self, idempotency_key: str) -> bool:
        if self.redis is None:
            raise RedisUnavailableError("Redis unavailable — cannot check idempotency key.")
        key = f"idempotency:{idempotency_key}"
        result = await self.redis.set(key, "1", nx=True, ex=900)
        return bool(result)

    async def enqueue_user(self, show_id: UUID, user_id: UUID) -> int:
        if self.redis is None:
            return 1
        import time

        queue_key = f"queue:{show_id}"
        score = time.time()
        await self.redis.zadd(queue_key, {str(user_id): score})
        pos = await self.redis.zrank(queue_key, str(user_id))
        return (pos or 0) + 1

    async def get_queue_position(self, show_id: UUID, user_id: UUID) -> int | None:
        if self.redis is None:
            return 1
        queue_key = f"queue:{show_id}"
        pos = await self.redis.zrank(queue_key, str(user_id))
        if pos is None:
            return None
        return pos + 1

    async def is_user_admitted(self, show_id: UUID, user_id: UUID) -> bool:
        if self.redis is None:
            return True
        key = f"admitted:{show_id}:{user_id}"
        return bool(await self.redis.exists(key))

    async def admit_user(self, show_id: UUID, user_id: UUID, ttl: int = 600) -> str:
        import secrets

        if self.redis is None:
            return secrets.token_urlsafe(32)
        token = secrets.token_urlsafe(32)
        queue_key = f"queue:{show_id}"
        await self.redis.zrem(queue_key, str(user_id))
        session_key = f"queue:session:{token}"
        await self.redis.set(session_key, str(user_id), ex=ttl)
        admitted_key = f"admitted:{show_id}:{user_id}"
        await self.redis.set(admitted_key, token, ex=ttl)
        return token

    async def get_admitted_token(self, show_id: UUID, user_id: UUID) -> str | None:
        if self.redis is None:
            return None
        admitted_key = f"admitted:{show_id}:{user_id}"
        return await self.redis.get(admitted_key)
