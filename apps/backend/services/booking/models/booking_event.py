"""NFR-6: booking.booking_events audit log ORM model."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base
from core.enums import BookingStatus

if TYPE_CHECKING:
    from .booking import Booking


class BookingEvent(Base):
    """booking.booking_events — immutable state transition audit trail."""

    __tablename__ = "booking_events"
    __table_args__ = {"schema": "booking"}

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("booking.bookings.booking_id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status: Mapped[BookingStatus | None] = mapped_column(
        Enum(BookingStatus, name="booking_status", create_type=False),
        nullable=True,
    )
    to_status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name="booking_status", create_type=False),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    # Relationships
    booking: Mapped[Booking] = relationship(back_populates="events")
