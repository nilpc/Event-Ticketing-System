"""FR-7, FR-8, FR-10: Repository for seat state transitions and price lookups."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import SeatStatus
from core.exceptions import SeatUnavailableError
from services.booking.models.seat import Seat


class SeatRepository:
    """Handles booking.seats queries — SRP, NFR-6."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def transition_seats_to_pending(
        self, show_id: UUID, seat_ids: list[str]
    ) -> dict[str, str]:
        """Bulk: transition multiple seats from AVAILABLE to PENDING_PAYMENT.

        Returns dict mapping seat_id -> 'ok' | 'unavailable'.
        """
        results: dict[str, str] = {}
        for seat_id in seat_ids:
            result = await self.session.execute(
                update(Seat)
                .where(
                    Seat.show_id == show_id,
                    Seat.seat_id == seat_id,
                    Seat.status == SeatStatus.AVAILABLE,
                )
                .values(status=SeatStatus.PENDING_PAYMENT)
            )
            results[seat_id] = "ok" if result.rowcount else "unavailable"  # type: ignore[attr-defined]
        return results

    async def get_seat_prices(self, show_id: UUID, seat_ids: list[str]) -> dict[str, Decimal]:
        """Bulk: get prices for multiple seats."""
        result = await self.session.execute(
            select(Seat.seat_id, Seat.price, Seat.tier).where(
                Seat.show_id == show_id,
                Seat.seat_id.in_(seat_ids),
            )
        )
        rows = result.all()
        if len(rows) != len(seat_ids):
            found = {r.seat_id for r in rows}
            missing = set(seat_ids) - found
            raise SeatUnavailableError(f"Seats not found: {', '.join(missing)}")
        return {r.seat_id: r.price for r in rows}

    async def verify_seat_available(self, show_id: UUID, seat_id: str) -> None:
        """FR-7: Verify seat exists and is AVAILABLE — used by seat lock Layer 3."""
        result = await self.session.execute(
            select(Seat.price).where(
                Seat.show_id == show_id,
                Seat.seat_id == seat_id,
                Seat.status == SeatStatus.AVAILABLE,
            )
        )
        if result.scalar_one_or_none() is None:
            raise SeatUnavailableError(
                f"Seat {seat_id} for show {show_id} is not available."
            )

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

    async def finalize_sold_seats(self, show_id: UUID, seat_ids: list[str]) -> None:
        """Bulk: finalize multiple seats to SOLD."""
        for seat_id in seat_ids:
            await self.finalize_sold_seat(show_id, seat_id)

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

    async def transition_seat_available(self, show_id: UUID, seat_id: str) -> None:
        """NFR-1: Release a PENDING_PAYMENT seat back to AVAILABLE."""
        await self.session.execute(
            update(Seat)
            .where(
                Seat.show_id == show_id,
                Seat.seat_id == seat_id,
                Seat.status == SeatStatus.PENDING_PAYMENT,
            )
            .values(status=SeatStatus.AVAILABLE)
        )

    async def transition_seats_available(self, show_id: UUID, seat_ids: list[str]) -> None:
        """Bulk: release PENDING_PAYMENT seats back to AVAILABLE."""
        for seat_id in seat_ids:
            await self.transition_seat_available(show_id, seat_id)
