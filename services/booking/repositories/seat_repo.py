"""FR-7, FR-8, FR-10: Repository for seat state transitions and price lookups."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import SeatStatus
from core.exceptions import SeatUnavailableError
from services.booking.models.seat import Seat


class SeatRepository:
    """Handles booking.seats queries — SRP, NFR-6."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def transition_seat_to_pending(self, show_id: UUID, seat_id: str) -> None:
        """FR-8: Atomically transition seat from AVAILABLE to PENDING_PAYMENT.

        Raises SeatUnavailableError if seat is not AVAILABLE.
        """
        result = await self.session.execute(
            update(Seat)
            .where(
                Seat.show_id == show_id,
                Seat.seat_id == seat_id,
                Seat.status == SeatStatus.AVAILABLE,
            )
            .values(status=SeatStatus.PENDING_PAYMENT)
        )
        if result.rowcount == 0:  # type: ignore[attr-defined]
            raise SeatUnavailableError(f"Seat {seat_id} for show {show_id} is not available.")

    async def get_seat_price(self, show_id: UUID, seat_id: str) -> Decimal:
        """FR-10: Read true seat price for server-side amount calculation."""
        from sqlalchemy import select

        result = await self.session.execute(
            select(Seat.price).where(
                Seat.show_id == show_id,
                Seat.seat_id == seat_id,
            )
        )
        price = result.scalar_one_or_none()
        if price is None:
            raise SeatUnavailableError(f"Seat {seat_id} for show {show_id} not found.")
        return price

    async def finalize_sold_seat(self, show_id: UUID, seat_id: str) -> None:
        """FR-8: Transition PENDING_PAYMENT to SOLD after payment confirmation."""
        await self.session.execute(
            update(Seat)
            .where(
                Seat.show_id == show_id,
                Seat.seat_id == seat_id,
                Seat.status == SeatStatus.PENDING_PAYMENT,
            )
            .values(status=SeatStatus.SOLD)
        )

    async def revert_seat_to_available(self, show_id: UUID, seat_id: str) -> None:
        """FR-9: Revert seat to AVAILABLE on payment failure or sweeper."""
        await self.session.execute(
            update(Seat)
            .where(
                Seat.show_id == show_id,
                Seat.seat_id == seat_id,
            )
            .values(status=SeatStatus.AVAILABLE)
        )
