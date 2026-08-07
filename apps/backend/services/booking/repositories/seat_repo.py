from __future__ import annotations

from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import SeatStatus
from core.exceptions import SeatUnavailableError
from services.booking.models.seat import Seat


class SeatRepository:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def transition_seats_to_pending(self, show_id: UUID, seat_ids: list[str]) -> dict[str, str]:
        results: dict[str, str] = {}
        for seat_id in seat_ids:
            result = await self.session.execute(update(Seat).where(Seat.show_id == show_id, Seat.seat_id == seat_id, Seat.status == SeatStatus.AVAILABLE).values(status=SeatStatus.PENDING_PAYMENT))
            results[seat_id] = 'ok' if cast(CursorResult, result).rowcount else 'unavailable'
        return results

    async def get_seat_prices(self, show_id: UUID, seat_ids: list[str]) -> dict[str, Decimal]:
        result = await self.session.execute(select(Seat.seat_id, Seat.price, Seat.tier).where(Seat.show_id == show_id, Seat.seat_id.in_(seat_ids)))
        rows = result.all()
        if len(rows) != len(seat_ids):
            found = {r.seat_id for r in rows}
            missing = set(seat_ids) - found
            raise SeatUnavailableError(f"Seats not found: {', '.join(missing)}")
        return {r.seat_id: r.price for r in rows}

    async def verify_seat_available(self, show_id: UUID, seat_id: str) -> None:
        result = await self.session.execute(select(Seat.price).where(Seat.show_id == show_id, Seat.seat_id == seat_id, Seat.status == SeatStatus.AVAILABLE))
        if result.scalar_one_or_none() is None:
            raise SeatUnavailableError(f'Seat {seat_id} for show {show_id} is not available.')

    async def finalize_sold_seat(self, show_id: UUID, seat_id: str) -> None:
        await self.session.execute(update(Seat).where(Seat.show_id == show_id, Seat.seat_id == seat_id, Seat.status == SeatStatus.PENDING_PAYMENT).values(status=SeatStatus.SOLD))

    async def finalize_sold_seats(self, show_id: UUID, seat_ids: list[str]) -> None:
        for seat_id in seat_ids:
            await self.finalize_sold_seat(show_id, seat_id)

    async def revert_seat_to_available(self, show_id: UUID, seat_id: str) -> None:
        await self.session.execute(update(Seat).where(Seat.show_id == show_id, Seat.seat_id == seat_id).values(status=SeatStatus.AVAILABLE))

    async def transition_seat_available(self, show_id: UUID, seat_id: str) -> None:
        await self.session.execute(update(Seat).where(Seat.show_id == show_id, Seat.seat_id == seat_id, Seat.status == SeatStatus.PENDING_PAYMENT).values(status=SeatStatus.AVAILABLE))

    async def transition_seats_available(self, show_id: UUID, seat_ids: list[str]) -> None:
        for seat_id in seat_ids:
            await self.transition_seat_available(show_id, seat_id)
