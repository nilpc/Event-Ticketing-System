"""Admin CRUD repository — write operations for events, venues, showtimes."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.booking.models.event import Event
from services.booking.models.seat import Seat
from services.booking.models.showtime import Showtime
from services.booking.models.venue import Venue


class AdminRepository:
    """Write-only admin queries — SRP, NFR-6."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── Events ─────────────────────────────────────────────────────
    async def create_event(self, event: Event) -> Event:
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_event(self, event_id: str) -> Event | None:
        result = await self.session.execute(select(Event).where(Event.event_id == event_id))
        return result.scalar_one_or_none()

    async def update_event(self, event: Event, **kwargs: object) -> Event:
        for key, value in kwargs.items():
            if value is not None:
                setattr(event, key, value)
        await self.session.flush()
        return event

    async def delete_event(self, event_id: str) -> None:
        await self.session.execute(delete(Event).where(Event.event_id == event_id))

    # ── Venues ─────────────────────────────────────────────────────
    async def create_venue(self, venue: Venue) -> Venue:
        self.session.add(venue)
        await self.session.flush()
        return venue

    async def get_venue(self, venue_id: UUID) -> Venue | None:
        result = await self.session.execute(select(Venue).where(Venue.venue_id == venue_id))
        return result.scalar_one_or_none()

    async def update_venue(self, venue: Venue, **kwargs: object) -> Venue:
        for key, value in kwargs.items():
            if value is not None:
                setattr(venue, key, value)
        await self.session.flush()
        return venue

    async def delete_venue(self, venue_id: UUID) -> None:
        await self.session.execute(delete(Venue).where(Venue.venue_id == venue_id))

    # ── Showtimes ──────────────────────────────────────────────────
    async def create_showtime(self, showtime: Showtime) -> Showtime:
        self.session.add(showtime)
        await self.session.flush()
        return showtime

    async def get_showtime(self, show_id: UUID) -> Showtime | None:
        result = await self.session.execute(select(Showtime).where(Showtime.show_id == show_id))
        return result.scalar_one_or_none()

    async def update_showtime(self, showtime: Showtime, **kwargs: object) -> Showtime:
        for key, value in kwargs.items():
            if value is not None:
                setattr(showtime, key, value)
        await self.session.flush()
        return showtime

    async def delete_showtime(self, show_id: UUID) -> None:
        await self.session.execute(delete(Seat).where(Seat.show_id == show_id))
        await self.session.execute(delete(Showtime).where(Showtime.show_id == show_id))

    # ── Seats ──────────────────────────────────────────────────────
    async def create_seats(self, seats: list[Seat]) -> None:
        self.session.add_all(seats)
        await self.session.flush()
