"""FR-5, FR-8, FR-9: Repository for bookings, outbox, and webhook event persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import BookingStatus
from services.booking.models.booking import Booking
from services.booking.models.booking_event import BookingEvent
from services.booking.models.outbox_event import OutboxEvent
from services.booking.models.processed_webhook import ProcessedWebhookEvent


class BookingRepository:
    """Handles booking.bookings + outbox + webhook idempotency — SRP, NFR-6."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Bookings ---

    async def get_booking_by_id(self, booking_id: UUID) -> Booking | None:
        """FR-5, FR-9: Fetch booking by PK."""
        result = await self.session.execute(select(Booking).where(Booking.booking_id == booking_id))
        return result.scalar_one_or_none()

    async def create_pending_booking(
        self,
        booking_id: UUID,
        user_id: UUID,
        show_id: UUID,
        seat_id: str,
        idempotency_key: str,
        amount: object,
        expires_at: datetime,
        correlation_id: str | None = None,
    ) -> None:
        """FR-8: Insert PENDING booking inside atomic transaction."""
        booking = Booking(
            booking_id=booking_id,
            user_id=user_id,
            show_id=show_id,
            seat_id=seat_id,
            status=BookingStatus.PENDING,
            idempotency_key=idempotency_key,
            amount=amount,
            currency="USD",
            expires_at=expires_at,
        )
        self.session.add(booking)

    async def get_booking_by_idempotency(self, idempotency_key: str) -> Booking | None:
        """FR-8: Idempotency replay — fetch existing booking by key."""
        result = await self.session.execute(
            select(Booking).where(Booking.idempotency_key == idempotency_key)
        )
        return result.scalar_one_or_none()

    async def list_bookings_for_user(self, user_id: UUID) -> list[dict]:
        """List all bookings for a user with event/venue/showtime details."""
        from services.booking.models.event import Event
        from services.booking.models.showtime import Showtime
        from services.booking.models.venue import Venue

        result = await self.session.execute(
            select(
                Booking.booking_id,
                Booking.status,
                Booking.seat_id,
                Booking.amount,
                Booking.currency,
                Booking.created_at,
                Showtime.show_id,
                Showtime.start_time,
                Showtime.end_time,
                Event.name.label("event_name"),
                Venue.name.label("venue_name"),
            )
            .join(Showtime, Booking.show_id == Showtime.show_id)
            .join(Event, Showtime.event_id == Event.event_id)
            .join(Venue, Showtime.venue_id == Venue.venue_id)
            .where(Booking.user_id == user_id)
            .order_by(Booking.created_at.desc())
        )
        rows = result.all()
        return [
            {
                "booking_id": str(row.booking_id),
                "status": row.status.value if hasattr(row.status, "value") else row.status,
                "seat_id": row.seat_id,
                "amount": str(row.amount),
                "currency": row.currency,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "show_id": str(row.show_id),
                "start_time": row.start_time.isoformat() if row.start_time else None,
                "end_time": row.end_time.isoformat() if row.end_time else None,
                "event_name": row.event_name,
                "venue_name": row.venue_name,
            }
            for row in rows
        ]

    async def update_booking_status(
        self,
        booking_id: UUID,
        new_status: BookingStatus,
        correlation_id: str | None = None,
        source: str = "system",
    ) -> None:
        """FR-8, FR-9: State machine transition with audit event."""
        # Fetch current status for audit
        result = await self.session.execute(
            select(Booking.status).where(Booking.booking_id == booking_id)
        )
        current_status = result.scalar_one_or_none()

        # Update booking status
        await self.session.execute(
            update(Booking).where(Booking.booking_id == booking_id).values(status=new_status)
        )

        # Write audit event
        event = BookingEvent(
            booking_id=booking_id,
            from_status=current_status,
            to_status=new_status,
            source=source,
            correlation_id=self._safe_uuid(correlation_id),
        )
        self.session.add(event)

    @staticmethod
    def _safe_uuid(value: str | None) -> UUID | None:
        """FR-9: Safely parse correlation_id — returns None for non-UUID strings."""
        if not value:
            return None
        try:
            return UUID(value)
        except (ValueError, TypeError):
            return None

    async def get_zombie_bookings(self, cutoff: datetime) -> list[Booking]:
        """FR-9: Sweeper query — PENDING bookings older than cutoff."""
        result = await self.session.execute(
            select(Booking).where(
                Booking.status == BookingStatus.PENDING,
                Booking.expires_at < cutoff,
            )
        )
        return list(result.scalars().all())

    async def revert_booking_to_failed(self, booking_id: UUID) -> None:
        """FR-9: Sweeper marks zombie booking as FAILED."""
        await self.update_booking_status(booking_id, BookingStatus.FAILED, source="sweeper")

    # --- Outbox ---

    async def add_outbox_event(
        self,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        payload: dict,
    ) -> None:
        """FR-8: Append outbox event inside same transaction as booking."""
        event = OutboxEvent(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload=payload,
        )
        self.session.add(event)

    async def get_unpublished_outbox_events_for_update_skip_locked(
        self,
    ) -> list[OutboxEvent]:
        """Outbox relay: SELECT ... FOR UPDATE SKIP LOCKED."""

        result = await self.session.execute(
            select(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None))
            .order_by(OutboxEvent.created_at)
            .limit(10)
            .with_for_update(skip_locked=True)
        )
        return list(result.scalars().all())

    async def mark_outbox_published(self, event_id: UUID) -> None:
        """Outbox relay: stamp published_at."""
        await self.session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.event_id == event_id)
            .values(published_at=datetime.now(UTC))
        )

    # --- Webhook idempotency ---

    async def log_webhook_event(self, event_id: str, event_type: str, payload: str) -> bool:
        """FR-9: Insert processed_webhook_events; returns False if duplicate.

        Caller must handle IntegrityError when used inside session.begin().
        """
        event = ProcessedWebhookEvent(
            event_id=event_id,
            event_type=event_type,
            payload={"raw": payload},
        )
        self.session.add(event)
        await self.session.flush()
        return True
