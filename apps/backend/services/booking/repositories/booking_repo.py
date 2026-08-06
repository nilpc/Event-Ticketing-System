from __future__ import annotations
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from core.enums import BookingStatus
from services.booking.models.booking import Booking
from services.booking.models.booking_event import BookingEvent
from services.booking.models.booking_seat import BookingSeat
from services.booking.models.outbox_event import OutboxEvent
from services.booking.models.processed_webhook import ProcessedWebhookEvent
from services.booking.models.seat import Seat

class BookingRepository:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_booking_by_id(self, booking_id: UUID) -> Booking | None:
        result = await self.session.execute(select(Booking).where(Booking.booking_id == booking_id))
        return result.scalar_one_or_none()

    async def get_booking_seats(self, booking_id: UUID) -> list[BookingSeat]:
        result = await self.session.execute(select(BookingSeat).where(BookingSeat.booking_id == booking_id))
        return list(result.scalars().all())

    async def create_pending_booking(self, booking_id: UUID, user_id: UUID, show_id: UUID, seat_prices: list[tuple[str, Decimal]], idempotency_key: str, amount: object, expires_at: datetime, correlation_id: str | None=None) -> None:
        booking = Booking(booking_id=booking_id, user_id=user_id, show_id=show_id, status=BookingStatus.PENDING, idempotency_key=idempotency_key, amount=amount, currency='inr', expires_at=expires_at)
        self.session.add(booking)
        for seat_id, price in seat_prices:
            self.session.add(BookingSeat(booking_id=booking_id, show_id=show_id, seat_id=seat_id, price=price))

    async def get_booking_by_idempotency(self, idempotency_key: str) -> Booking | None:
        result = await self.session.execute(select(Booking).where(Booking.idempotency_key == idempotency_key))
        return result.scalar_one_or_none()

    async def get_active_booking_for_user_show(self, user_id: UUID, show_id: UUID) -> Booking | None:
        result = await self.session.execute(select(Booking).where(Booking.user_id == user_id, Booking.show_id == show_id, Booking.status == BookingStatus.PENDING))
        return result.scalar_one_or_none()

    async def cancel_active_booking_for_user_show(self, user_id: UUID, show_id: UUID) -> tuple[list[str], str]:
        booking = await self.get_active_booking_for_user_show(user_id, show_id)
        if booking is None:
            return ([], 'none')
        seats = await self.get_booking_seats(booking.booking_id)
        seat_ids = [s.seat_id for s in seats]
        await self.update_booking_status(booking.booking_id, BookingStatus.FAILED, source='checkout-replace')
        return (seat_ids, 'replaced')

    async def list_bookings_for_user(self, user_id: UUID) -> list[dict]:
        from services.booking.models.event import Event
        from services.booking.models.showtime import Showtime
        from services.booking.models.venue import Venue
        result = await self.session.execute(select(Booking.booking_id, Booking.status, Booking.amount, Booking.currency, Booking.created_at, Showtime.show_id, Showtime.start_time, Showtime.end_time, Event.name.label('event_name'), Venue.name.label('venue_name')).join(Showtime, Booking.show_id == Showtime.show_id).join(Event, Showtime.event_id == Event.event_id).join(Venue, Showtime.venue_id == Venue.venue_id).where(Booking.user_id == user_id).order_by(Booking.created_at.desc()))
        rows = result.all()
        if not rows:
            return []
        booking_ids = [row.booking_id for row in rows]
        seats_result = await self.session.execute(select(BookingSeat.booking_id, BookingSeat.seat_id, BookingSeat.price, Seat.tier).join(Seat, (BookingSeat.show_id == Seat.show_id) & (BookingSeat.seat_id == Seat.seat_id)).where(BookingSeat.booking_id.in_(booking_ids)))
        all_seat_rows = seats_result.all()
        seats_by_booking: dict[UUID, list[dict]] = {}
        for s in all_seat_rows:
            seats_by_booking.setdefault(s.booking_id, []).append({'seat_id': s.seat_id, 'price': str(s.price), 'tier': s.tier})
        bookings = []
        for row in rows:
            seats = seats_by_booking.get(row.booking_id, [])
            bookings.append({'booking_id': str(row.booking_id), 'status': row.status.value if hasattr(row.status, 'value') else row.status, 'seats': seats, 'amount': str(row.amount), 'currency': row.currency, 'created_at': row.created_at.isoformat() if row.created_at else None, 'show_id': str(row.show_id), 'start_time': row.start_time.isoformat() if row.start_time else None, 'end_time': row.end_time.isoformat() if row.end_time else None, 'event_name': row.event_name, 'venue_name': row.venue_name})
        return bookings

    async def update_booking_status(self, booking_id: UUID, new_status: BookingStatus, correlation_id: str | None=None, source: str='system') -> None:
        result = await self.session.execute(select(Booking.status).where(Booking.booking_id == booking_id))
        current_status = result.scalar_one_or_none()
        await self.session.execute(update(Booking).where(Booking.booking_id == booking_id).values(status=new_status))
        event = BookingEvent(booking_id=booking_id, from_status=current_status, to_status=new_status, source=source, correlation_id=self._safe_uuid(correlation_id))
        self.session.add(event)

    @staticmethod
    def _safe_uuid(value: str | None) -> UUID | None:
        if not value:
            return None
        try:
            return UUID(value)
        except (ValueError, TypeError):
            return None

    async def get_zombie_bookings(self, cutoff: datetime) -> list[Booking]:
        result = await self.session.execute(select(Booking).where(Booking.status == BookingStatus.PENDING, Booking.expires_at < cutoff))
        return list(result.scalars().all())

    async def revert_booking_to_failed(self, booking_id: UUID) -> None:
        await self.update_booking_status(booking_id, BookingStatus.FAILED, source='sweeper')

    async def add_outbox_event(self, aggregate_type: str, aggregate_id: UUID, event_type: str, payload: dict) -> None:
        event = OutboxEvent(aggregate_type=aggregate_type, aggregate_id=aggregate_id, event_type=event_type, payload=payload)
        self.session.add(event)

    async def get_unpublished_outbox_events_for_update_skip_locked(self) -> list[OutboxEvent]:
        result = await self.session.execute(select(OutboxEvent).where(OutboxEvent.published_at.is_(None)).order_by(OutboxEvent.created_at).limit(10).with_for_update(skip_locked=True))
        return list(result.scalars().all())

    async def mark_outbox_published(self, event_id: UUID) -> None:
        await self.session.execute(update(OutboxEvent).where(OutboxEvent.event_id == event_id).values(published_at=datetime.now(UTC)))

    async def log_webhook_event(self, event_id: str, event_type: str, payload: str) -> bool:
        event = ProcessedWebhookEvent(event_id=event_id, event_type=event_type, payload={'raw': payload})
        self.session.add(event)
        await self.session.flush()
        return True
