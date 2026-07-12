"""FR-4, FR-10: booking.showtimes ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base

if TYPE_CHECKING:
    from .event import Event
    from .seat import Seat
    from .venue import Venue


class Showtime(Base):
    """booking.showtimes — FR-4 catalog, FR-10 server-side price source."""

    __tablename__ = "showtimes"
    __table_args__ = {"schema": "booking"}

    show_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("booking.events.event_id", ondelete="CASCADE"),
        nullable=False,
    )
    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("booking.venues.venue_id", ondelete="CASCADE"),
        nullable=False,
    )
    base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Relationships
    event: Mapped[Event] = relationship()
    venue: Mapped[Venue] = relationship()
    seats: Mapped[list[Seat]] = relationship(back_populates="showtime")
