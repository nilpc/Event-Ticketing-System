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
SEAT_LOCK_TTL = 600
HOLD_LIMIT_TTL = 600
MAX_SEATS_PER_CHECKOUT = 8


class SeatLockService:
    def __init__(
        self, session: AsyncSession, lock_repo: LockRepository, seat_repo: SeatRepository
    ) -> None:
        self.lock_repo = lock_repo
        self.seat_repo = seat_repo

    async def lock_seats(
        self, show_id: UUID, seat_ids: list[str], user_id: UUID
    ) -> SeatLockResponse:
        import secrets

        if len(seat_ids) == 0:
            raise BookingConflictError("No seats selected.")
        if len(seat_ids) > MAX_SEATS_PER_CHECKOUT:
            raise BookingConflictError(f"Maximum {MAX_SEATS_PER_CHECKOUT} seats per checkout.")
        for seat_id in seat_ids:
            try:
                await self.seat_repo.verify_seat_available(show_id, seat_id)
            except SeatUnavailableError:
                raise
        locked: list[str] = []
        try:
            for seat_id in seat_ids:
                if not await self.lock_repo.acquire_user_hold(
                    show_id, user_id, HOLD_LIMIT_TTL, max_holds=MAX_SEATS_PER_CHECKOUT
                ):
                    raise BookingConflictError(
                        "You have reached the maximum number of held seats. Please complete or release existing holds."
                    )
                acquired = await self.lock_repo.acquire_seat_lock(
                    show_id, seat_id, user_id, SEAT_LOCK_TTL
                )
                if not acquired:
                    await self.lock_repo.release_user_hold_limit(show_id, user_id)
                    raise BookingConflictError(
                        f"Seat {seat_id} is currently locked by another user."
                    )
                locked.append(seat_id)
        except (BookingConflictError, SeatUnavailableError):
            for sid in locked:
                await self.lock_repo.release_seat_lock_safe(show_id, sid, user_id)
                await self.lock_repo.release_user_hold_limit(show_id, user_id)
            raise
        idempotency_key = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(seconds=SEAT_LOCK_TTL)
        logger.info("seats_locked", show_id=str(show_id), seat_ids=seat_ids, user_id=str(user_id))
        return SeatLockResponse(
            idempotency_key=idempotency_key, expires_at=expires_at, locked_seat_ids=seat_ids
        )
