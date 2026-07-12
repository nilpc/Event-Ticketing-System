"""FR-8, FR-9: Repository for bookings, outbox, and webhook event persistence."""

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


class BookingRepository:
    """Handles booking.bookings + outbox + webhook idempotency — SRP, NFR-6."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Bookings ---

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
        ...

    async def get_booking_by_id(self, booking_id: UUID) -> object | None:
        """FR-9: Fetch booking by PK for webhook processing."""
        ...

    async def get_booking_by_idempotency(self, idempotency_key: str) -> object | None:
        """FR-8: Idempotency replay — fetch existing booking by key."""
        ...

    async def update_booking_status(
        self,
        booking_id: UUID,
        new_status: object,
        correlation_id: str | None = None,
        source: str = "system",
    ) -> None:
        """FR-8, FR-9: State machine transition with audit event."""
        ...

    async def get_zombie_bookings(self, cutoff: datetime) -> list[object]:
        """FR-9: Sweeper query — PENDING bookings older than cutoff."""
        ...

    async def revert_booking_to_failed(self, booking_id: UUID) -> None:
        """FR-9: Sweeper marks zombie booking as FAILED."""
        ...

    # --- Outbox ---

    async def add_outbox_event(
        self,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        payload: dict,
    ) -> None:
        """FR-8: Append outbox event inside same transaction as booking."""
        ...

    async def get_unpublished_outbox_events_for_update_skip_locked(
        self,
    ) -> list[object]:
        """Outbox relay: SELECT ... FOR UPDATE SKIP LOCKED."""
        ...

    async def mark_outbox_published(self, event_id: UUID) -> None:
        """Outbox relay: stamp published_at."""
        ...

    # --- Webhook idempotency ---

    async def log_webhook_event(
        self, event_id: str, event_type: str, payload: str
    ) -> bool:
        """FR-9: Insert processed_webhook_events; returns False if duplicate."""
        ...
