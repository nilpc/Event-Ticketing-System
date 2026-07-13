"""FR-8, FR-10: BookingService — atomic checkout (§6 Layer 1)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import BookingStatus
from core.exceptions import (
    BookingConflictError,
    InvalidTokenError,
    PersistenceError,
    SeatUnavailableError,
)
from services.booking.repositories.booking_repo import BookingRepository
from services.booking.repositories.cache_repo import CacheRepository
from services.booking.repositories.lock_repo import LockRepository
from services.booking.repositories.seat_repo import SeatRepository
from services.booking.schemas.booking import BookResponse

logger = structlog.get_logger()

# FR-8: Booking expires in 10 minutes
BOOKING_EXPIRY_MINUTES = 10


class BookingService:
    """FR-8, FR-10: Atomic checkout — §6 Layer 1 reference implementation."""

    def __init__(
        self,
        session: AsyncSession,
        seat_repo: SeatRepository,
        booking_repo: BookingRepository,
        lock_repo: LockRepository,
        cache_repo: CacheRepository,
    ) -> None:
        self.session = session
        self.seat_repo = seat_repo
        self.booking_repo = booking_repo
        self.lock_repo = lock_repo
        self.cache_repo = cache_repo

    async def initialize_checkout(
        self,
        show_id: uuid.UUID,
        seat_id: str,
        user_id: uuid.UUID,
        idempotency_key: str,
        queue_token: str,
        request_id: str,
    ) -> BookResponse:
        """FR-8: Atomic booking initialization.

        This is Layer 1 in docs/requirements.md §6 — the single highest-value
        section. We follow it exactly, including the except branches.
        """
        # FR-8: Idempotency check (must be before queue validation for replays)
        if not await self.lock_repo.is_idempotency_key_available(idempotency_key):
            existing = await self.booking_repo.get_booking_by_idempotency(idempotency_key)
            if existing:
                return BookResponse(
                    booking_id=existing.booking_id,
                    status=existing.status.value,
                    expires_at=existing.expires_at,
                )
            raise BookingConflictError("Duplicate payload.")

        # Validate queue session token
        if not await self.lock_repo.validate_queue_session(queue_token, user_id):
            raise InvalidTokenError("Invalid or expired queue session token.")

        # Verify seat lock belongs to this user
        lock_holder = await self.lock_repo.get_seat_lock(show_id, seat_id)
        if lock_holder != user_id:
            raise BookingConflictError("Seat lock expired or assigned to another user.")

        booking_id = uuid.uuid4()
        expires_at = datetime.now(UTC) + timedelta(minutes=BOOKING_EXPIRY_MINUTES)

        try:
            # CRITICAL: Single Atomic Transaction
            async with self.session.begin():
                # 1. Transition Seat
                await self.seat_repo.transition_seat_to_pending(show_id, seat_id)

                # 2. FR-10: Verify Price & Create Booking (Prevents Price Tampering)
                seat_price = await self.seat_repo.get_seat_price(show_id, seat_id)

                await self.booking_repo.create_pending_booking(
                    booking_id=booking_id,
                    user_id=user_id,
                    show_id=show_id,
                    seat_id=seat_id,
                    idempotency_key=idempotency_key,
                    amount=seat_price,
                    expires_at=expires_at,
                    correlation_id=request_id,
                )

                # 3. Outbox event for async notification service
                await self.booking_repo.add_outbox_event(
                    aggregate_type="Booking",
                    aggregate_id=booking_id,
                    event_type="BOOKING_INITIALIZED",
                    payload={
                        "booking_id": str(booking_id),
                        "show_id": str(show_id),
                        "seat_id": seat_id,
                    },
                )

        except (BookingConflictError, SeatUnavailableError, InvalidTokenError):
            # §6: expected domain conflicts release holds and propagate unchanged
            await self.lock_repo.release_seat_lock_safe(show_id, seat_id, user_id)
            await self.lock_repo.release_user_hold_limit(show_id, user_id)
            raise

        except Exception as e:
            # §6: unexpected failures are no longer rebranded as booking conflicts
            await self.lock_repo.release_seat_lock_safe(show_id, seat_id, user_id)
            await self.lock_repo.release_user_hold_limit(show_id, user_id)
            logger.exception(
                "unexpected_persistence_failure", error=str(e), booking_id=str(booking_id)
            )
            raise PersistenceError(f"Checkout failed unexpectedly: {e}") from e

        # CRITICAL: Cache invalidation MUST happen AFTER DB commit.
        try:
            await self.cache_repo.invalidate(f"seatmap:{show_id}")
        except Exception as cache_err:
            logger.error(
                "cache_invalidation_failed",
                show_id=str(show_id),
                error=str(cache_err),
            )

        # Consume queue session after successful checkout
        try:
            await self.lock_repo.consume_queue_session(queue_token)
        except Exception:
            logger.warning("queue_session_consume_failed", queue_token=queue_token[:8])

        logger.info(
            "booking_initialized",
            booking_id=str(booking_id),
            show_id=str(show_id),
            seat_id=seat_id,
            user_id=str(user_id),
        )

        return BookResponse(
            booking_id=booking_id,
            status=BookingStatus.PENDING.value,
            expires_at=expires_at,
        )
