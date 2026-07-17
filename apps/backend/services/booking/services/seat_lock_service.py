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
MAX_SEATS_PER_CHECKOUT = 8


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

    async def lock_seats(self, show_id: UUID, seat_ids: list[str], user_id: UUID) -> SeatLockResponse:
        """FR-7: Lock multiple seats atomically."""
        import secrets

        if len(seat_ids) == 0:
            raise BookingConflictError("No seats selected.")
        if len(seat_ids) > MAX_SEATS_PER_CHECKOUT:
            raise BookingConflictError(f"Maximum {MAX_SEATS_PER_CHECKOUT} seats per checkout.")

        # Verify all seats are available (Layer 3) first
        for seat_id in seat_ids:
            try:
                await self.seat_repo.verify_seat_available(show_id, seat_id)
            except SeatUnavailableError:
                raise

        # Acquire holds for each seat
        locked: list[str] = []
        try:
            for seat_id in seat_ids:
                # Layer 1: User hold limit
                if not await self.lock_repo.acquire_user_hold(show_id, user_id, HOLD_LIMIT_TTL):
                    raise BookingConflictError(
                        "You have reached the maximum number of held seats. "
                        "Please complete or release existing holds."
                    )

                # Layer 2: Distributed lock
                if not await self.lock_repo.acquire_seat_lock(show_id, seat_id, user_id, SEAT_LOCK_TTL):
                    await self.lock_repo.release_user_hold_limit(show_id, user_id)
                    raise BookingConflictError(f"Seat {seat_id} is currently locked by another user.")

                locked.append(seat_id)
        except (BookingConflictError, SeatUnavailableError):
            # Release any locks we already acquired
            for sid in locked:
                await self.lock_repo.release_seat_lock_safe(show_id, sid, user_id)
                await self.lock_repo.release_user_hold_limit(show_id, user_id)
            raise

        idempotency_key = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(seconds=SEAT_LOCK_TTL)

        logger.info(
            "seats_locked",
            show_id=str(show_id),
            seat_ids=seat_ids,
            user_id=str(user_id),
        )
        return SeatLockResponse(
            idempotency_key=idempotency_key,
            expires_at=expires_at,
            locked_seat_ids=seat_ids,
        )
