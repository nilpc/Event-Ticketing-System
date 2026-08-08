from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import SeatStatus
from core.ids import generate_event_id
from services.booking.models.event import Event
from services.booking.models.showtime import Showtime
from services.booking.models.venue import Venue
from services.booking.repositories.admin_repo import AdminRepository
from services.booking.repositories.cache_repo import CacheRepository
from services.booking.schemas.admin import (
    EventCreate,
    EventUpdate,
    ShowtimeBatchCreate,
    ShowtimeCreate,
    ShowtimeUpdate,
    VenueCreate,
    VenueUpdate,
)
from services.identity.models.user import User

logger = structlog.get_logger()

class AdminService:

    def __init__(self, session: AsyncSession, cache_repo: CacheRepository | None=None) -> None:
        self.session = session
        self.repo = AdminRepository(session)
        self.cache_repo = cache_repo

    async def create_event(self, data: EventCreate, created_by: uuid.UUID | None=None) -> Event:
        event_id = await generate_event_id(self.session, data.event_type)
        event = Event(event_id=event_id, event_type=data.event_type, name=data.name, description=data.description, created_by=created_by)
        result = await self.repo.create_event(event)
        await self._invalidate_catalog(['events:all'])
        return result

    async def get_event(self, event_id: str) -> Event | None:
        return await self.repo.get_event(event_id)

    async def list_events(self, created_by: uuid.UUID | None=None) -> list[Event]:
        return await self.repo.list_events(created_by=created_by)

    async def update_event(self, event_id: str, data: EventUpdate) -> Event:
        event = await self.repo.get_event(event_id)
        if event is None:
            raise LookupError(f'Event {event_id} not found')
        result = await self.repo.update_event(event, name=data.name, description=data.description, event_type=data.event_type)
        await self._invalidate_catalog(['events:all'])
        return result

    async def delete_event(self, event_id: str) -> None:
        event = await self.repo.get_event(event_id)
        if event is None:
            raise LookupError(f'Event {event_id} not found')
        showtimes = await self.repo.list_showtimes_by_event(event_id)
        for s in showtimes:
            await self.delete_showtime(str(s.show_id))
        await self.repo.delete_event(event_id)
        await self._invalidate_catalog(['events:all', 'showtimes:all', f'showtimes:event:{event_id}'])

    async def create_venue(self, data: VenueCreate, created_by: uuid.UUID | None=None) -> Venue:
        venue = Venue(venue_id=uuid.uuid4(), name=data.name, capacity=data.capacity, created_by=created_by)
        result = await self.repo.create_venue(venue)
        await self._invalidate_catalog(['venues:all'])
        return result

    async def list_venues(self, created_by: uuid.UUID | None=None) -> list[Venue]:
        return await self.repo.list_venues(created_by=created_by)

    async def get_venue(self, venue_id: str) -> Venue | None:
        return await self.repo.get_venue(uuid.UUID(venue_id))

    async def update_venue(self, venue_id: str, data: VenueUpdate) -> Venue:
        venue = await self.repo.get_venue(uuid.UUID(venue_id))
        if venue is None:
            raise LookupError(f'Venue {venue_id} not found')
        result = await self.repo.update_venue(venue, name=data.name, capacity=data.capacity)
        await self._invalidate_catalog(['venues:all'])
        return result

    async def delete_venue(self, venue_id: str) -> None:
        venue = await self.repo.get_venue(uuid.UUID(venue_id))
        if venue is None:
            raise LookupError(f'Venue {venue_id} not found')
        showtimes = await self.repo.list_showtimes_by_venue(uuid.UUID(venue_id))
        for s in showtimes:
            await self.delete_showtime(str(s.show_id))
        await self.repo.delete_venue(uuid.UUID(venue_id))
        await self._invalidate_catalog(['venues:all', 'showtimes:all'])

    async def list_showtimes(self, created_by: uuid.UUID | None=None) -> list[Showtime]:
        return await self.repo.list_showtimes(created_by=created_by)

    async def create_showtime(self, data: ShowtimeCreate) -> Showtime:
        showtime = Showtime(show_id=uuid.uuid4(), event_id=data.event_id, venue_id=uuid.UUID(data.venue_id), front_price=data.front_price, middle_price=data.middle_price, back_price=data.back_price, start_time=data.start_time, end_time=data.end_time)
        result = await self.repo.create_showtime(showtime)
        if data.auto_seats:
            venue = await self.repo.get_venue(uuid.UUID(data.venue_id))
            if venue:
                for chunk in _seat_chunks(result.show_id, venue.capacity, float(data.front_price), float(data.middle_price), float(data.back_price)):
                    await self.repo.create_seats(chunk)
        await self._invalidate_catalog(['showtimes:all', 'events:all', 'venues:all', f'showtimes:event:{data.event_id}'])
        return result

    async def get_showtime(self, show_id: str) -> Showtime | None:
        return await self.repo.get_showtime(uuid.UUID(show_id))

    async def create_showtimes_batch(self, data: ShowtimeBatchCreate) -> list[Showtime]:
        created: list[Showtime] = []
        for slot in data.slots:
            showtime = Showtime(show_id=uuid.uuid4(), event_id=data.event_id, venue_id=uuid.UUID(data.venue_id), front_price=data.front_price, middle_price=data.middle_price, back_price=data.back_price, start_time=slot.start_time, end_time=slot.end_time)
            result = await self.repo.create_showtime(showtime)
            created.append(result)
            if data.auto_seats:
                venue = await self.repo.get_venue(uuid.UUID(data.venue_id))
                if venue:
                    for chunk in _seat_chunks(result.show_id, venue.capacity, float(data.front_price), float(data.middle_price), float(data.back_price)):
                        await self.repo.create_seats(chunk)
        await self._invalidate_catalog(['showtimes:all', 'events:all', 'venues:all', f'showtimes:event:{data.event_id}'])
        return created

    async def update_showtime(self, show_id: str, data: ShowtimeUpdate) -> Showtime:
        showtime = await self.repo.get_showtime(uuid.UUID(show_id))
        if showtime is None:
            raise LookupError(f'Showtime {show_id} not found')
        update_kwargs: dict[str, Any] = {}
        if data.front_price is not None:
            update_kwargs['front_price'] = data.front_price
        if data.middle_price is not None:
            update_kwargs['middle_price'] = data.middle_price
        if data.back_price is not None:
            update_kwargs['back_price'] = data.back_price
        if data.start_time is not None:
            update_kwargs['start_time'] = data.start_time
        if data.end_time is not None:
            update_kwargs['end_time'] = data.end_time
        result = await self.repo.update_showtime(showtime, **update_kwargs)
        await self._invalidate_catalog(['showtimes:all', 'events:all', 'venues:all', f'showtime:{show_id}', f'showtimes:event:{showtime.event_id}'])
        return result

    async def delete_showtime(self, show_id: str) -> None:
        showtime = await self.repo.get_showtime(uuid.UUID(show_id))
        if showtime is None:
            raise LookupError(f'Showtime {show_id} not found')
        await self.repo.delete_showtime(uuid.UUID(show_id))
        await self._invalidate_catalog(['showtimes:all', 'events:all', 'venues:all', f'showtime:{show_id}', f'seatmap:{show_id}', f'showtimes:event:{showtime.event_id}'])

    async def _invalidate_catalog(self, keys: list[str]) -> None:
        if self.cache_repo is None:
            return
        for key in set(keys):
            try:
                await self.cache_repo.invalidate(key)
            except Exception:
                logger.warning('catalog_invalidation_failed', key=key)

    async def promote_user(self, user_id: str) -> User:
        result = await self.session.execute(select(User).where(User.user_id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()
        if user is None:
            raise LookupError(f'User {user_id} not found')
        user.is_admin = True
        self.session.add(user)
        return user

    async def get_event_owner(self, event_id: str) -> uuid.UUID | None:
        return await self.repo.get_event_owner(event_id)

    async def get_venue_owner(self, venue_id: str) -> uuid.UUID | None:
        return await self.repo.get_venue_owner(uuid.UUID(venue_id))
_SEAT_CHUNK = 100

def _seat_chunks(show_id: uuid.UUID, capacity: int, front_price: float, middle_price: float, back_price: float) -> Iterator[list[dict]]:
    vip_count = max(1, int(capacity * 0.1))
    premium_count = max(1, int(capacity * 0.3))
    standard_count = max(0, capacity - vip_count - premium_count)

    tiers_info = [
        ('vip', front_price, 'SEC-1', vip_count),
        ('premium', middle_price, 'SEC-2', premium_count),
        ('standard', back_price, 'SEC-3', standard_count),
    ]

    chunk: list[dict] = []
    global_seat_idx = 0

    for tier_name, price, base_sec, count in tiers_info:
        if count <= 0:
            continue
        num_subsections = (count + 99) // 100
        for sub_i in range(num_subsections):
            if num_subsections == 1:
                sec_name = base_sec
            else:
                suffix = ""
                n = sub_i
                while True:
                    suffix = chr(ord('A') + (n % 26)) + suffix
                    n = n // 26 - 1
                    if n < 0:
                        break
                sec_name = f"{base_sec}{suffix}"

            sub_count = min(100, count - sub_i * 100)
            for j in range(sub_count):
                global_seat_idx += 1
                row = chr(ord('A') + ((global_seat_idx - 1) % 26))
                seat_num = j + 1
                seat_id = f"{sec_name}-{row}{seat_num}"

                chunk.append({
                    'show_id': show_id,
                    'seat_id': seat_id,
                    'section': sec_name,
                    'tier': tier_name,
                    'price': price,
                    'status': SeatStatus.AVAILABLE
                })

                if len(chunk) >= _SEAT_CHUNK:
                    yield chunk
                    chunk = []

    if chunk:
        yield chunk

