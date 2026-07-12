"""FR-4: Repository for catalog read queries."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.booking.models.event import Event
from services.booking.models.seat import Seat
from services.booking.models.showtime import Showtime
from services.booking.models.venue import Venue


class CatalogRepository:
    """FR-4: Read-only catalog queries — SRP, NFR-6."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_venues(self) -> list[Venue]:
        result = await self.session.execute(select(Venue))
        return list(result.scalars().all())

    async def list_events(self) -> list[Event]:
        result = await self.session.execute(select(Event))
        return list(result.scalars().all())

    async def get_showtime(self, show_id: UUID) -> Showtime | None:
        result = await self.session.execute(
            select(Showtime).where(Showtime.show_id == show_id)
        )
        return result.scalar_one_or_none()

    async def get_seat_map(self, show_id: UUID) -> list[Seat]:
        result = await self.session.execute(
            select(Seat).where(Seat.show_id == show_id).order_by(Seat.seat_id)
        )
        return list(result.scalars().all())

    async def get_showtimes_by_event(self, event_id: UUID) -> list[Showtime]:
        result = await self.session.execute(
            select(Showtime).where(Showtime.event_id == event_id)
        )
        return list(result.scalars().all())
