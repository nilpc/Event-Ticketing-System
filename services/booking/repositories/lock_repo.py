"""FR-6, FR-7: Repository for Redis-based queue, seat locks, and user hold limits."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


class LockRepository:
    """Redis lock/state operations — SRP, NFR-6.

    DB session accepted for interface consistency; real implementation
    delegates to redis.asyncio.
    """

    def __init__(self, session: AsyncSession, redis_client: object | None = None) -> None:
        self.session = session
        self.redis = redis_client

    # --- Seat Locking (FR-7) ---

    async def acquire_seat_lock(
        self, show_id: UUID, seat_id: str, user_id: UUID, ttl: int = 600
    ) -> bool:
        """FR-7: SETNX with TTL; returns False if already locked."""
        ...

    async def get_seat_lock(self, show_id: UUID, seat_id: str) -> UUID | None:
        """FR-7: Read current lock holder."""
        ...

    async def release_seat_lock_safe(
        self, show_id: UUID, seat_id: str, user_id: UUID
    ) -> None:
        """FR-7: CAS release — only free if still held by this user."""
        ...

    # --- User Hold Limit (FR-7) ---

    async def acquire_user_hold(
        self, show_id: UUID, user_id: UUID, ttl: int = 600
    ) -> bool:
        """FR-7: Enforce 10-min per-user hold limit."""
        ...

    async def release_user_hold_limit(self, show_id: UUID, user_id: UUID) -> None:
        """FR-7: Remove user hold after terminal booking outcome."""
        ...

    # --- Queue (FR-6) ---

    async def validate_queue_session(self, queue_token: str, user_id: UUID) -> bool:
        """FR-6: Verify queue session token belongs to user and is active."""
        ...

    async def consume_queue_session(self, queue_token: str) -> None:
        """FR-6: Invalidate queue token after successful checkout."""
        ...

    # --- Idempotency (FR-8) ---

    async def is_idempotency_key_available(self, idempotency_key: str) -> bool:
        """FR-8: Redis SET NX; returns True if key was newly created."""
        ...
