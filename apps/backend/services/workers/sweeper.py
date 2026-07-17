"""FR-9: Background sweeper — revert zombie PENDING bookings."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import structlog

from core.db.session import async_session_factory
from core.redis import get_redis
from services.booking.repositories.booking_repo import BookingRepository
from services.booking.repositories.lock_repo import LockRepository
from services.booking.repositories.seat_repo import SeatRepository

logger = structlog.get_logger()

# FR-9: Sweep every 60 seconds; bookings expire at 10 min, sweep at 15 min (5-min grace)
SWEEP_INTERVAL_SECONDS = 60
GRACE_PERIOD_MINUTES = 15


async def sweep_zombie_bookings() -> None:
    """FR-9: Find and revert expired PENDING bookings (multi-seat)."""
    cutoff = datetime.now(UTC) - timedelta(minutes=GRACE_PERIOD_MINUTES)

    async with async_session_factory() as session:
        booking_repo = BookingRepository(session)
        zombies = await booking_repo.get_zombie_bookings(cutoff)

    for booking in zombies:
        try:
            async with async_session_factory() as session:
                seat_repo = SeatRepository(session)
                booking_repo = BookingRepository(session)

                async with session.begin():
                    # Get all seats from junction table
                    booking_seats = await booking_repo.get_booking_seats(booking.booking_id)
                    seat_ids = [bs.seat_id for bs in booking_seats]

                    for seat_id in seat_ids:
                        await seat_repo.revert_seat_to_available(booking.show_id, seat_id)

                    await booking_repo.revert_booking_to_failed(booking.booking_id)
                    await booking_repo.add_outbox_event(
                        aggregate_type="Booking",
                        aggregate_id=booking.booking_id,
                        event_type="BOOKING_FAILED",
                        payload={
                            "booking_id": str(booking.booking_id),
                            "reason": "sweeper_zombie_revert",
                        },
                    )

            async with async_session_factory() as session:
                lock_repo = LockRepository(session, redis_client=get_redis())
                for seat_id in seat_ids:
                    await lock_repo.release_seat_lock_safe(
                        booking.show_id, seat_id, booking.user_id
                    )
                await lock_repo.release_user_hold_limit(booking.show_id, booking.user_id)

            logger.info(
                "zombie_booking_reverted",
                booking_id=str(booking.booking_id),
                show_id=str(booking.show_id),
            )
        except Exception as exc:
            logger.error(
                "sweeper_revert_failed",
                booking_id=str(booking.booking_id),
                error=str(exc),
            )


async def run_sweeper() -> None:
    """FR-9: Background loop — sweep every 60 seconds."""
    logger.info("sweeper_started", interval=SWEEP_INTERVAL_SECONDS)
    while True:
        try:
            await sweep_zombie_bookings()
        except Exception as exc:
            logger.error("sweeper_iteration_failed", error=str(exc))
        await asyncio.sleep(SWEEP_INTERVAL_SECONDS)
