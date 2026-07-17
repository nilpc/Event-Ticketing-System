"""FR-8, FR-10: BookingService — atomic checkout (§6 Layer 1)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

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
from services.booking.schemas.booking import (
    BookingListItem,
    BookingSeatInfo,
    BookResponse,
    MockConfirmResponse,
)

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
        seat_ids: list[str],
        user_id: uuid.UUID,
        idempotency_key: str,
        queue_token: str,
        request_id: str,
    ) -> BookResponse:
        """FR-8: Atomic multi-seat booking initialization.

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

        # Verify all seat locks belong to this user
        for seat_id in seat_ids:
            lock_holder = await self.lock_repo.get_seat_lock(show_id, seat_id)
            if lock_holder != user_id:
                raise BookingConflictError(
                    f"Seat {seat_id} lock expired or assigned to another user."
                )

        booking_id = uuid.uuid4()
        expires_at = datetime.now(UTC) + timedelta(minutes=BOOKING_EXPIRY_MINUTES)

        try:
            # CRITICAL: Single Atomic Transaction
            async with self.session.begin():
                # NFR-1: Cancel any stale PENDING booking for this user+show
                old_seat_ids, status = await self.booking_repo.cancel_active_booking_for_user_show(
                    user_id, show_id
                )
                if old_seat_ids:
                    await self.seat_repo.transition_seats_available(show_id, old_seat_ids)

                # 1. Transition all seats to PENDING_PAYMENT
                results = await self.seat_repo.transition_seats_to_pending(show_id, seat_ids)
                failed = [sid for sid, s in results.items() if s == "unavailable"]
                if failed:
                    raise SeatUnavailableError(f"Seats no longer available: {', '.join(failed)}")

                # 2. FR-10: Get all seat prices (server-side amount calculation)
                prices = await self.seat_repo.get_seat_prices(show_id, seat_ids)
                total_amount = Decimal("0.00")
                seat_price_pairs: list[tuple[str, Decimal]] = []
                for seat_id in seat_ids:
                    price = prices[seat_id]
                    total_amount += price
                    seat_price_pairs.append((seat_id, price))

                # 3. Create booking with junction rows
                await self.booking_repo.create_pending_booking(
                    booking_id=booking_id,
                    user_id=user_id,
                    show_id=show_id,
                    seat_prices=seat_price_pairs,
                    idempotency_key=idempotency_key,
                    amount=total_amount,
                    expires_at=expires_at,
                    correlation_id=request_id,
                )

                # 4. Outbox event for async notification service
                await self.booking_repo.add_outbox_event(
                    aggregate_type="Booking",
                    aggregate_id=booking_id,
                    event_type="BOOKING_INITIALIZED",
                    payload={
                        "booking_id": str(booking_id),
                        "show_id": str(show_id),
                        "seat_ids": seat_ids,
                    },
                )

        except (BookingConflictError, SeatUnavailableError, InvalidTokenError):
            # §6: expected domain conflicts release holds and propagate unchanged
            for seat_id in seat_ids:
                await self.lock_repo.release_seat_lock_safe(show_id, seat_id, user_id)
                await self.lock_repo.release_user_hold_limit(show_id, user_id)
            raise

        except Exception as e:
            # §6: unexpected failures are no longer rebranded as booking conflicts
            for seat_id in seat_ids:
                await self.lock_repo.release_seat_lock_safe(show_id, seat_id, user_id)
                await self.lock_repo.release_user_hold_limit(show_id, user_id)
            logger.exception(
                "unexpected_persistence_failure", error=str(e), booking_id=str(booking_id)
            )
            raise PersistenceError(f"Checkout failed unexpectedly: {e}") from e

        # Cache invalidation MUST happen AFTER DB commit
        try:
            await self.cache_repo.invalidate(f"seatmap:{show_id}")
        except Exception as cache_err:
            logger.error("cache_invalidation_failed", show_id=str(show_id), error=str(cache_err))

        # Consume queue session after successful checkout
        try:
            await self.lock_repo.consume_queue_session(
                queue_token, show_id=show_id, user_id=user_id
            )
        except Exception:
            logger.warning("queue_session_consume_failed", queue_token=queue_token[:8])

        logger.info(
            "booking_initialized",
            booking_id=str(booking_id),
            show_id=str(show_id),
            seat_ids=seat_ids,
            user_id=str(user_id),
        )

        return BookResponse(
            booking_id=booking_id,
            status=BookingStatus.PENDING.value,
            expires_at=expires_at,
        )

    async def mock_confirm_booking(self, booking_id: uuid.UUID) -> MockConfirmResponse:
        """Demo-only: flip PENDING→CONFIRMED and PENDING_PAYMENT→SOLD for all seats."""
        booking = await self.booking_repo.get_booking_by_id(booking_id)
        if booking is None:
            raise BookingConflictError("Booking not found.")

        if booking.status != BookingStatus.PENDING:
            raise BookingConflictError(f"Booking is {booking.status.value}, expected PENDING.")

        # Get all seats from junction table
        booking_seats = await self.booking_repo.get_booking_seats(booking_id)
        seat_ids = [bs.seat_id for bs in booking_seats]

        await self.booking_repo.update_booking_status(
            booking_id, BookingStatus.CONFIRMED, source="mock-confirm",
        )
        await self.seat_repo.finalize_sold_seats(booking.show_id, seat_ids)

        try:
            await self.cache_repo.invalidate(f"seatmap:{booking.show_id}")
        except Exception:
            logger.warning("cache_invalidation_failed", show_id=str(booking.show_id))

        return MockConfirmResponse(
            booking_id=booking_id,
            status=BookingStatus.CONFIRMED.value,
            seat_ids=seat_ids,
        )

    async def list_user_bookings(self, user_id: uuid.UUID) -> list[BookingListItem]:
        """List all bookings for a user with joined event/venue details and seats."""
        rows = await self.booking_repo.list_bookings_for_user(user_id)
        results = []
        for row in rows:
            seats = [
                BookingSeatInfo(seat_id=s["seat_id"], tier="", price=s["price"])
                for s in row["seats"]
            ]
            results.append(
                BookingListItem(
                    booking_id=row["booking_id"],
                    status=row["status"],
                    seats=seats,
                    amount=row["amount"],
                    currency=row["currency"],
                    created_at=row["created_at"],
                    show_id=row["show_id"],
                    start_time=row["start_time"],
                    end_time=row["end_time"],
                    event_name=row["event_name"],
                    venue_name=row["venue_name"],
                )
            )
        return results
