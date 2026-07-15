"""Admin CRUD service — business logic for catalog management."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.ids import generate_event_id
from services.booking.models.event import Event
from services.booking.models.seat import Seat
from services.booking.models.showtime import Showtime
from services.booking.models.venue import Venue
from services.booking.repositories.admin_repo import AdminRepository
from services.booking.schemas.admin import (
    EventCreate,
    EventUpdate,
    ShowtimeCreate,
    ShowtimeUpdate,
    VenueCreate,
    VenueUpdate,
)


class AdminService:
    """Admin catalog management — FR-4, NFR-6, NFR-1."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = AdminRepository(session)

    # ── Events ─────────────────────────────────────────────────────
    async def create_event(self, data: EventCreate) -> Event:
        event_id = await generate_event_id(self.session, data.event_type)
        event = Event(
            event_id=event_id,
            event_type=data.event_type,
            name=data.name,
            description=data.description,
        )
        return await self.repo.create_event(event)

    async def get_event(self, event_id: str) -> Event | None:
        return await self.repo.get_event(event_id)

    async def update_event(self, event_id: str, data: EventUpdate) -> Event:
        event = await self.repo.get_event(event_id)
        if event is None:
            raise LookupError(f"Event {event_id} not found")
        return await self.repo.update_event(
            event,
            name=data.name,
            description=data.description,
            event_type=data.event_type,
        )

    async def delete_event(self, event_id: str) -> None:
        event = await self.repo.get_event(event_id)
        if event is None:
            raise LookupError(f"Event {event_id} not found")
        await self.repo.delete_event(event_id)

    # ── Venues ─────────────────────────────────────────────────────
    async def create_venue(self, data: VenueCreate) -> Venue:
        venue = Venue(
            venue_id=uuid.uuid4(),
            name=data.name,
            capacity=data.capacity,
        )
        return await self.repo.create_venue(venue)

    async def get_venue(self, venue_id: str) -> Venue | None:
        return await self.repo.get_venue(uuid.UUID(venue_id))

    async def update_venue(self, venue_id: str, data: VenueUpdate) -> Venue:
        venue = await self.repo.get_venue(uuid.UUID(venue_id))
        if venue is None:
            raise LookupError(f"Venue {venue_id} not found")
        return await self.repo.update_venue(
            venue,
            name=data.name,
            capacity=data.capacity,
        )

    async def delete_venue(self, venue_id: str) -> None:
        venue = await self.repo.get_venue(uuid.UUID(venue_id))
        if venue is None:
            raise LookupError(f"Venue {venue_id} not found")
        await self.repo.delete_venue(uuid.UUID(venue_id))

    # ── Showtimes ──────────────────────────────────────────────────
    async def list_showtimes(self) -> list[Showtime]:
        return await self.repo.list_showtimes()

    async def create_showtime(self, data: ShowtimeCreate) -> Showtime:
        showtime = Showtime(
            show_id=uuid.uuid4(),
            event_id=data.event_id,
            venue_id=uuid.UUID(data.venue_id),
            base_price=data.base_price,
            start_time=data.start_time,
            end_time=data.end_time,
        )
        result = await self.repo.create_showtime(showtime)

        if data.auto_seats:
            venue = await self.repo.get_venue(uuid.UUID(data.venue_id))
            if venue:
                seats = _generate_seats(result.show_id, venue.capacity)
                await self.repo.create_seats(seats)

        return result

    async def get_showtime(self, show_id: str) -> Showtime | None:
        return await self.repo.get_showtime(uuid.UUID(show_id))

    async def update_showtime(self, show_id: str, data: ShowtimeUpdate) -> Showtime:
        showtime = await self.repo.get_showtime(uuid.UUID(show_id))
        if showtime is None:
            raise LookupError(f"Showtime {show_id} not found")
        return await self.repo.update_showtime(
            showtime,
            base_price=data.base_price,
            start_time=data.start_time,
            end_time=data.end_time,
        )

    async def delete_showtime(self, show_id: str) -> None:
        showtime = await self.repo.get_showtime(uuid.UUID(show_id))
        if showtime is None:
            raise LookupError(f"Showtime {show_id} not found")
        await self.repo.delete_showtime(uuid.UUID(show_id))


def _generate_seats(show_id: uuid.UUID, capacity: int) -> list[Seat]:
    """Generate seat rows/tiers based on venue capacity.

    Tiers: VIP (10%), Premium (30%), Standard (60%).
    Rows: A-Z, seats per row based on capacity.
    """
    vip_count = max(1, int(capacity * 0.10))
    premium_count = max(1, int(capacity * 0.30))
    standard_count = capacity - vip_count - premium_count

    seats: list[Seat] = []
    seat_num = 0
    row_idx = 0

    for tier, count, tier_price in [
        ("vip", vip_count, 150.00),
        ("premium", premium_count, 100.00),
        ("standard", standard_count, 75.00),
    ]:
        for _ in range(count):
            row = chr(ord("A") + row_idx % 26)
            seat_num += 1
            seats.append(
                Seat(
                    show_id=show_id,
                    seat_id=f"{row}{seat_num}",
                    tier=tier,
                    price=tier_price,
                    status="AVAILABLE",
                )
            )
            row_idx += 1

    return seats
