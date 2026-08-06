from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, ForeignKeyConstraint, Numeric, PrimaryKeyConstraint, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base

if TYPE_CHECKING:
    from .booking import Booking


class BookingSeat(Base):
    __tablename__ = "booking_seats"
    __table_args__ = (
        PrimaryKeyConstraint("booking_id", "seat_id"),
        ForeignKeyConstraint(
            ["show_id", "seat_id"],
            ["booking.seats.show_id", "booking.seats.seat_id"],
            ondelete="CASCADE",
        ),
        {"schema": "booking"},
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("booking.bookings.booking_id", ondelete="CASCADE"),
        nullable=False,
    )
    show_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    seat_id: Mapped[str] = mapped_column(String(10), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    booking: Mapped[Booking] = relationship(back_populates="booking_seats")
