from __future__ import annotations
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import pytest_asyncio
from core.db.session import async_session_factory
from core.enums import EventType, SeatStatus
from services.booking.models.booking import Booking
from services.booking.models.booking_seat import BookingSeat
from services.booking.models.event import Event
from services.booking.models.seat import Seat
from services.booking.models.showtime import Showtime
from services.booking.models.venue import Venue
from services.identity.models.user import User

@pytest_asyncio.fixture
async def booking_fixture() -> AsyncGenerator[dict, None]:
    async with async_session_factory() as session:
        user = User(email=f'pay_{uuid.uuid4().hex[:8]}@test.com', password_hash='x', is_active=True)
        session.add(user)
        await session.flush()
        venue = Venue(name='Pay Arena', capacity=10)
        session.add(venue)
        await session.flush()
        event = Event(event_id=f'STE{uuid.uuid4().hex[:6].upper()}', event_type=EventType.EVENT, name='Pay Test')
        session.add(event)
        await session.flush()
        start = datetime.now(UTC) + timedelta(hours=1)
        show = Showtime(event_id=event.event_id, venue_id=venue.venue_id, front_price=Decimal('50.00'), middle_price=Decimal('50.00'), back_price=Decimal('50.00'), start_time=start, end_time=start + timedelta(hours=2))
        session.add(show)
        await session.flush()
        seat1 = Seat(show_id=show.show_id, seat_id='A1', tier='standard', price=Decimal('50.00'), status=SeatStatus.PENDING_PAYMENT)
        seat2 = Seat(show_id=show.show_id, seat_id='A2', tier='standard', price=Decimal('50.00'), status=SeatStatus.PENDING_PAYMENT)
        session.add_all([seat1, seat2])
        await session.flush()
        booking = Booking(user_id=user.user_id, show_id=show.show_id, idempotency_key=uuid.uuid4().hex, amount=Decimal('100.00'), currency='usd', expires_at=datetime.now(UTC) + timedelta(minutes=30))
        session.add(booking)
        await session.flush()
        session.add_all([BookingSeat(booking_id=booking.booking_id, show_id=show.show_id, seat_id='A1', price=Decimal('50.00')), BookingSeat(booking_id=booking.booking_id, show_id=show.show_id, seat_id='A2', price=Decimal('50.00'))])
        await session.commit()
        yield {'user_id': user.user_id, 'booking_id': booking.booking_id, 'show_id': show.show_id, 'seat_ids': ['A1', 'A2']}
