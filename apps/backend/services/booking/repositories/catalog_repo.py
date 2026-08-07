from __future__ import annotations
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from services.booking.models.event import Event
from services.booking.models.seat import Seat
from services.booking.models.showtime import Showtime
from services.booking.models.venue import Venue

class CatalogRepository:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_venues(self) -> list[Venue]:
        result = await self.session.execute(select(Venue).where(Venue.venue_id.in_(select(Showtime.venue_id))))
        return list(result.scalars().all())

    async def list_events(self) -> list[Event]:
        result = await self.session.execute(select(Event).where(Event.event_id.in_(select(Showtime.event_id))))
        return list(result.scalars().all())

    async def get_showtime(self, show_id: UUID) -> Showtime | None:
        result = await self.session.execute(select(Showtime).where(Showtime.show_id == show_id))
        return result.scalar_one_or_none()

    async def get_seat_map(self, show_id: UUID, section: str | None=None) -> list[Seat]:
        stmt = select(Seat).where(Seat.show_id == show_id).order_by(Seat.seat_id)
        if section:
            stmt = stmt.where(Seat.section == section)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_sections(self, show_id: UUID) -> list[dict]:
        from sqlalchemy import func, case
        from core.enums import SeatStatus
        stmt = select(Seat.section, func.max(Seat.tier).label('tier'), func.count(Seat.seat_id).label('total_seats'), func.sum(case((Seat.status == SeatStatus.AVAILABLE, 1), else_=0)).label('available_seats')).where(Seat.show_id == show_id).group_by(Seat.section).order_by(Seat.section)
        result = await self.session.execute(stmt)
        return [{'section': row.section, 'tier': row.tier, 'total_seats': row.total_seats, 'available_seats': int(row.available_seats) if row.available_seats else 0} for row in result.all()]

    async def get_showtimes_by_event(self, event_id: str) -> list[Showtime]:
        result = await self.session.execute(select(Showtime).where(Showtime.event_id == event_id))
        return list(result.scalars().all())

    async def list_showtimes(self) -> list[Showtime]:
        result = await self.session.execute(select(Showtime).order_by(Showtime.start_time))
        return list(result.scalars().all())
