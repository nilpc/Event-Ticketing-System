"""FR-7, FR-10: booking.seats ORM model."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base
from core.enums import SeatStatus

if TYPE_CHECKING:
    from .showtime import Showtime


class Seat(Base):
    """booking.seats — FR-7 seat locking, FR-10 price lookup."""

    __tablename__ = "seats"
    __table_args__ = {"schema": "booking"}

    show_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("booking.showtimes.show_id", ondelete="CASCADE"),
        primary_key=True,
    )
    seat_id: Mapped[str] = mapped_column(String(10), primary_key=True)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[SeatStatus] = mapped_column(
        Enum(SeatStatus, name="seat_status", create_type=False),
        nullable=False,
        default=SeatStatus.AVAILABLE,
    )

    # Relationships
    showtime: Mapped[Showtime] = relationship(back_populates="seats")
