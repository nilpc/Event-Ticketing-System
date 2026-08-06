from __future__ import annotations
from uuid import UUID
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from services.booking.models.event import Event
from services.booking.models.seat import Seat
from services.booking.models.showtime import Showtime
from services.booking.models.venue import Venue

class AdminRepository:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_event(self, event: Event) -> Event:
        self.session.add(event)
        await self.session.commit()
        return event

    async def get_event(self, event_id: str) -> Event | None:
        result = await self.session.execute(select(Event).where(Event.event_id == event_id))
        return result.scalar_one_or_none()

    async def list_events(self, created_by: UUID | None=None) -> list[Event]:
        query = select(Event)
        if created_by is not None:
            query = query.where(Event.created_by == created_by)
        result = await self.session.execute(query.order_by(Event.name))
        return list(result.scalars().all())

    async def get_event_owner(self, event_id: str) -> UUID | None:
        event = await self.get_event(event_id)
        return event.created_by if event else None

    async def update_event(self, event: Event, **kwargs: object) -> Event:
        for key, value in kwargs.items():
            if value is not None:
                setattr(event, key, value)
        await self.session.commit()
        return event

    async def delete_event(self, event_id: str) -> None:
        await self.session.execute(delete(Event).where(Event.event_id == event_id))
        await self.session.commit()

    async def create_venue(self, venue: Venue) -> Venue:
        self.session.add(venue)
        await self.session.commit()
        return venue

    async def get_venue(self, venue_id: UUID) -> Venue | None:
        result = await self.session.execute(select(Venue).where(Venue.venue_id == venue_id))
        return result.scalar_one_or_none()

    async def list_venues(self, created_by: UUID | None=None) -> list[Venue]:
        query = select(Venue)
        if created_by is not None:
            query = query.where(Venue.created_by == created_by)
        result = await self.session.execute(query.order_by(Venue.name))
        return list(result.scalars().all())

    async def get_venue_owner(self, venue_id: UUID) -> UUID | None:
        venue = await self.get_venue(venue_id)
        return venue.created_by if venue else None

    async def update_venue(self, venue: Venue, **kwargs: object) -> Venue:
        for key, value in kwargs.items():
            if value is not None:
                setattr(venue, key, value)
        await self.session.commit()
        return venue

    async def delete_venue(self, venue_id: UUID) -> None:
        await self.session.execute(delete(Venue).where(Venue.venue_id == venue_id))
        await self.session.commit()

    async def list_showtimes(self, created_by: UUID | None=None) -> list[Showtime]:
        query = select(Showtime)
        if created_by is not None:
            query = query.join(Event).where(Event.created_by == created_by)
        result = await self.session.execute(query.order_by(Showtime.start_time))
        return list(result.scalars().all())

    async def list_showtimes_by_event(self, event_id: str) -> list[Showtime]:
        result = await self.session.execute(select(Showtime).where(Showtime.event_id == event_id))
        return list(result.scalars().all())

    async def list_showtimes_by_venue(self, venue_id: UUID) -> list[Showtime]:
        result = await self.session.execute(select(Showtime).where(Showtime.venue_id == venue_id))
        return list(result.scalars().all())

    async def create_showtime(self, showtime: Showtime) -> Showtime:
        self.session.add(showtime)
        await self.session.commit()
        return showtime

    async def get_showtime(self, show_id: UUID) -> Showtime | None:
        result = await self.session.execute(select(Showtime).where(Showtime.show_id == show_id))
        return result.scalar_one_or_none()

    async def update_showtime(self, showtime: Showtime, **kwargs: object) -> Showtime:
        for key, value in kwargs.items():
            if value is not None:
                setattr(showtime, key, value)
        await self.session.commit()
        return showtime

    async def delete_showtime(self, show_id: UUID) -> None:
        await self.session.execute(delete(Seat).where(Seat.show_id == show_id))
        await self.session.execute(delete(Showtime).where(Showtime.show_id == show_id))
        await self.session.commit()

    async def create_seats(self, rows: list[dict]) -> None:
        if not rows:
            return
        await self.session.execute(insert(Seat), rows)
        await self.session.commit()
