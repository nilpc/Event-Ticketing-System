"""NFR-1: Concurrency verification — zero double-bookings under interleaved requests.

Launches multiple concurrent booking attempts against the same set of seats
using the ORM and asserts that no two PENDING bookings exist for the same seat.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.enums import BookingStatus, EventType, SeatStatus
from services.booking.models.booking import Booking
from services.booking.models.booking_seat import BookingSeat
from services.booking.models.event import Event
from services.booking.models.seat import Seat
from services.booking.models.showtime import Showtime
from services.booking.models.venue import Venue
from services.identity.models.user import User


async def _seed_user(session: AsyncSession) -> uuid.UUID:
    """Create a test user in identity.users to satisfy FK constraints."""
    user_id = uuid.uuid4()
    user = User(
        user_id=user_id,
        email=f"concurrency_{user_id.hex[:8]}@test.com",
        password_hash="dummy-hash",
    )
    session.add(user)
    await session.flush()
    return user_id


async def _seed_show(session: AsyncSession, seat_ids: list[str]) -> uuid.UUID:
    """Seed venue, event, showtime, and seats via ORM. Returns the show_id."""
    venue = Venue(name="Concurrency Test Venue", capacity=100)
    session.add(venue)
    await session.flush()

    event = Event(
        event_id=f"STE{uuid.uuid4().hex[:6].upper()}",
        event_type=EventType.EVENT,
        name="Concurrency Test Event",
        description="Test",
    )
    session.add(event)
    await session.flush()

    show_id = uuid.uuid4()
    showtime = Showtime(
        show_id=show_id,
        event_id=event.event_id,
        venue_id=venue.venue_id,
        base_price=Decimal("50.00"),
        start_time=datetime.now(UTC) + timedelta(hours=1),
        end_time=datetime.now(UTC) + timedelta(hours=3),
    )
    session.add(showtime)
    await session.flush()

    for sid in seat_ids:
        seat = Seat(
            show_id=show_id,
            seat_id=sid,
            tier="standard",
            price=Decimal("50.00"),
            status=SeatStatus.AVAILABLE,
        )
        session.add(seat)
    await session.flush()

    return show_id


async def _attempt_booking(
    session_factory: async_sessionmaker,
    show_id: uuid.UUID,
    seat_id: str,
    user_id: uuid.UUID,
) -> bool:
    """Attempt to book a single seat using ORM.

    Returns True if the booking was created (PENDING), False if the seat was
    already taken or the transaction failed.
    """
    async with session_factory() as session:
        async with session.begin():
            # NFR-1: Atomic seat transition — only succeeds if status is AVAILABLE.
            result = await session.execute(
                update(Seat)
                .where(
                    Seat.show_id == show_id,
                    Seat.seat_id == seat_id,
                    Seat.status == SeatStatus.AVAILABLE,
                )
                .values(status=SeatStatus.PENDING_PAYMENT)
            )
            if result.rowcount > 0:
                booking = Booking(
                    user_id=user_id,
                    show_id=show_id,
                    seat_id=seat_id,
                    status=BookingStatus.PENDING,
                    idempotency_key=str(uuid.uuid4()),
                    amount=Decimal("50.00"),
                    currency="USD",
                    expires_at=datetime.now(UTC) + timedelta(minutes=10),
                )
                session.add(booking)
                await session.flush()

                junction = BookingSeat(
                    booking_id=booking.booking_id,
                    seat_id=seat_id,
                    show_id=show_id,
                    price=Decimal("50.00"),
                )
                session.add(junction)

        return result.rowcount > 0


async def test_zero_double_bookings_under_concurrency() -> None:
    """NFR-1: Under concurrent booking attempts, no seat is double-booked."""
    from core.db.session import async_session_factory

    seat_ids = [f"S{i}" for i in range(5)]
    num_users = 20

    async with async_session_factory() as session:
        show_id = await _seed_show(session, seat_ids)
        user_ids = [await _seed_user(session) for _ in range(num_users)]
        await session.commit()

    # Launch 20 concurrent booking attempts across 5 seats (4 users per seat).
    tasks = [
        _attempt_booking(
            async_session_factory,
            show_id,
            seat_ids[i % len(seat_ids)],
            user_ids[i],
        )
        for i in range(num_users)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Every task must complete without raising an exception.
    for i, r in enumerate(results):
        assert not isinstance(r, Exception), f"Task {i} raised an exception: {r}"

    successes = sum(1 for r in results if r is True)
    # With 5 seats, at most 5 bookings should succeed.
    assert successes <= 5, f"Expected at most 5 bookings, got {successes}"

    # NFR-1: Verify no double-bookings in DB — each seat has at most 1 PENDING booking.
    async with async_session_factory() as session:
        dupes = await session.execute(
            select(Booking.seat_id, func.count())
            .where(Booking.show_id == show_id, Booking.status == BookingStatus.PENDING)
            .group_by(Booking.seat_id)
            .having(func.count() > 1)
        )
        rows = dupes.fetchall()
        assert len(rows) == 0, f"Double-booked seats: {rows}"


async def test_seat_status_consistency() -> None:
    """NFR-1: After concurrent attempts, seat statuses are consistent."""
    from core.db.session import async_session_factory

    seat_ids = [f"C{i}" for i in range(3)]
    num_users = 10

    async with async_session_factory() as session:
        show_id = await _seed_show(session, seat_ids)
        user_ids = [await _seed_user(session) for _ in range(num_users)]
        await session.commit()

    tasks = [
        _attempt_booking(
            async_session_factory,
            show_id,
            seat_ids[i % len(seat_ids)],
            user_ids[i],
        )
        for i in range(num_users)
    ]
    await asyncio.gather(*tasks, return_exceptions=True)

    async with async_session_factory() as session:
        result = await session.execute(
            select(Seat.seat_id, Seat.status)
            .where(Seat.show_id == show_id)
            .order_by(Seat.seat_id)
        )
        rows = result.fetchall()
        for seat_id, status in rows:
            assert status in (SeatStatus.AVAILABLE, SeatStatus.PENDING_PAYMENT, SeatStatus.SOLD), (
                f"Unexpected status {status} for seat {seat_id}"
            )

    # Cross-check: number of PENDING bookings must equal the number of PENDING_PAYMENT seats.
    async with async_session_factory() as session:
        booked_count = await session.scalar(
            select(func.count())
            .select_from(Booking)
            .where(Booking.show_id == show_id, Booking.status == BookingStatus.PENDING)
        )
        pending_seats = await session.scalar(
            select(func.count())
            .select_from(Seat)
            .where(Seat.show_id == show_id, Seat.status == SeatStatus.PENDING_PAYMENT)
        )
        assert booked_count == pending_seats, (
            f"Mismatch: {booked_count} bookings vs {pending_seats} pending seats"
        )
