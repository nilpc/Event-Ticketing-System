"""FR-7: SeatLockService — distributed lock with hoarding protection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import BookingConflictError, SeatUnavailableError
from services.booking.repositories.lock_repo import LockRepository
from services.booking.repositories.seat_repo import SeatRepository
from services.booking.schemas.seat_lock import SeatLockResponse

logger = structlog.get_logger()

# FR-7: Lock and hold limits
SEAT_LOCK_TTL = 600  # 10 minutes
HOLD_LIMIT_TTL = 600  # 10 minutes


class SeatLockService:
    """FR-7: Seat locking business logic — lock, hold limit, idempotency key."""

    def __init__(
        self,
        session: AsyncSession,
        lock_repo: LockRepository,
        seat_repo: SeatRepository,
    ) -> None:
        self.lock_repo = lock_repo
        self.seat_repo = seat_repo

    async def lock_seat(self, show_id: UUID, seat_id: str, user_id: UUID) -> SeatLockResponse:
        """FR-7: Lock seat with distributed lock + hoarding limit + server-generated key."""
        import secrets

        # Layer 1: User hold limit — prevent seat hoarding
        if not await self.lock_repo.acquire_user_hold(show_id, user_id, HOLD_LIMIT_TTL):
            raise BookingConflictError(
                "You have reached the maximum number of held seats. "
                "Please complete or release existing holds."
            )

        # Layer 2: Distributed lock — SETNX with TTL
        if not await self.lock_repo.acquire_seat_lock(show_id, seat_id, user_id, SEAT_LOCK_TTL):
            # Release the hold we just acquired since we can't lock the seat
            await self.lock_repo.release_user_hold_limit(show_id, user_id)
            raise BookingConflictError("Seat is currently locked by another user.")

        # Layer 3: Non-locking DB read to verify seat is AVAILABLE
        try:
            await self.seat_repo.get_seat_price(show_id, seat_id)
        except SeatUnavailableError:
            # Seat doesn't exist — release locks
            await self.lock_repo.release_seat_lock_safe(show_id, seat_id, user_id)
            await self.lock_repo.release_user_hold_limit(show_id, user_id)
            raise

        # Layer 4: Server-generated idempotency key (NEVER accepted from client)
        idempotency_key = secrets.token_urlsafe(32)

        expires_at = datetime.now(UTC) + timedelta(seconds=SEAT_LOCK_TTL)
        logger.info(
            "seat_locked",
            show_id=str(show_id),
            seat_id=seat_id,
            user_id=str(user_id),
        )
        return SeatLockResponse(idempotency_key=idempotency_key, expires_at=expires_at)
