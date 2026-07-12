"""FR-1, FR-8, FR-9, FR-10, NFR-1: booking.bookings ORM model."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base
from core.enums import BookingStatus

if TYPE_CHECKING:
    from .booking_event import BookingEvent
    from .payment import Payment
    from .seat import Seat


class Booking(Base):
    """booking.bookings — FR-8 atomic init, FR-9 sweeper, NFR-1 unique constraint."""

    __tablename__ = "bookings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["show_id", "seat_id"],
            ["booking.seats.show_id", "booking.seats.seat_id"],
            ondelete="RESTRICT",
        ),
        {"schema": "booking"},
    )

    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # FR-1: cross-schema FK to identity.users
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("identity.users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    show_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    seat_id: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name="booking_status", create_type=False),
        nullable=False,
        default=BookingStatus.PENDING,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    seat: Mapped[Seat] = relationship()
    payments: Mapped[list[Payment]] = relationship(back_populates="booking")
    events: Mapped[list[BookingEvent]] = relationship(back_populates="booking")
