"""Admin CRUD service — business logic for catalog management."""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.ids import generate_event_id
from services.booking.models.event import Event
from services.booking.models.seat import Seat
from services.booking.models.showtime import Showtime
from services.booking.models.venue import Venue
from services.booking.repositories.admin_repo import AdminRepository
from services.booking.repositories.cache_repo import CacheRepository
from services.booking.schemas.admin import (
    EventCreate,
    EventUpdate,
    ShowtimeCreate,
    ShowtimeUpdate,
    VenueCreate,
    VenueUpdate,
)
from services.identity.models.user import User

logger = structlog.get_logger()


class AdminService:
    """Admin catalog management — FR-4, NFR-6, NFR-1."""

    def __init__(self, session: AsyncSession, cache_repo: CacheRepository | None = None) -> None:
        self.session = session
        self.repo = AdminRepository(session)
        self.cache_repo = cache_repo

    # ── Events ─────────────────────────────────────────────────────
    async def create_event(self, data: EventCreate, created_by: uuid.UUID | None = None) -> Event:
        event_id = await generate_event_id(self.session, data.event_type)
        event = Event(
            event_id=event_id,
            event_type=data.event_type,
            name=data.name,
            description=data.description,
            created_by=created_by,
        )
        return await self.repo.create_event(event)

    async def get_event(self, event_id: str) -> Event | None:
        return await self.repo.get_event(event_id)

    async def list_events(self) -> list[Event]:
        return await self.repo.list_events()

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
        showtimes = await self.repo.list_showtimes_by_event(event_id)
        await self.repo.delete_event(event_id)
        await self._invalidate_catalog(
            ["events:all", "showtimes:all", f"showtimes:event:{event_id}"]
            + [f"showtime:{s.show_id}" for s in showtimes]
            + [f"seatmap:{s.show_id}" for s in showtimes]
        )

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
        showtimes = await self.repo.list_showtimes_by_venue(uuid.UUID(venue_id))
        await self.repo.delete_venue(uuid.UUID(venue_id))
        await self._invalidate_catalog(
            ["venues:all", "showtimes:all"]
            + [f"showtime:{s.show_id}" for s in showtimes]
            + [f"showtimes:event:{s.event_id}" for s in showtimes]
            + [f"seatmap:{s.show_id}" for s in showtimes]
        )

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
                seats = _generate_seats(result.show_id, venue.capacity, float(data.base_price))
                await self.repo.create_seats(seats)

        await self._invalidate_catalog(
            ["showtimes:all", f"showtimes:event:{data.event_id}"]
        )

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
        await self._invalidate_catalog(
            [
                "showtimes:all",
                f"showtime:{show_id}",
                f"seatmap:{show_id}",
                f"showtimes:event:{showtime.event_id}",
            ]
        )

    async def _invalidate_catalog(self, keys: list[str]) -> None:
        """FR-4: Post-mutation cache invalidation — failure-tolerant.

        Redis outages never break admin responses (AGENTS.md).
        """
        if self.cache_repo is None:
            return
        for key in set(keys):
            try:
                await self.cache_repo.invalidate(key)
            except Exception:
                logger.warning("catalog_invalidation_failed", key=key)

    # ── User Promotion ────────────────────────────────────────────────
    async def promote_user(self, user_id: str) -> User:
        result = await self.session.execute(
            select(User).where(User.user_id == uuid.UUID(user_id))
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise LookupError(f"User {user_id} not found")
        user.is_admin = True
        self.session.add(user)
        return user

    async def get_event_owner(self, event_id: str) -> uuid.UUID | None:
        return await self.repo.get_event_owner(event_id)


def _generate_seats(show_id: uuid.UUID, capacity: int, base_price: float) -> list[Seat]:
    """Generate seat rows/tiers based on venue capacity and base price.

    Tiers: VIP (10%), Premium (30%), Standard (60%).
    Rows: A-Z, seats per row based on capacity.
    Prices derived from showtime base_price.
    """
    vip_count = max(1, int(capacity * 0.10))
    premium_count = max(1, int(capacity * 0.30))
    standard_count = capacity - vip_count - premium_count

    seats: list[Seat] = []
    seat_num = 0
    row_idx = 0

    for tier, count, multiplier in [
        ("vip", vip_count, 1.5),
        ("premium", premium_count, 1.0),
        ("standard", standard_count, 0.75),
    ]:
        tier_price = round(base_price * multiplier, 2)
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
