"""FR-4: CatalogService — Redis-cached catalog reads."""

from __future__ import annotations

import json
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from services.booking.repositories.cache_repo import CacheRepository
from services.booking.repositories.catalog_repo import CatalogRepository
from services.booking.schemas.catalog import (
    EventResponse,
    SeatMapResponse,
    SeatResponse,
    ShowtimeResponse,
    VenueResponse,
)

logger = structlog.get_logger()

VENUE_CACHE_TTL = 60
EVENT_CACHE_TTL = 60
SHOWTIME_CACHE_TTL = 60
SEATMAP_CACHE_TTL = 30


class _DecimalEncoder(json.JSONEncoder):
    """C6: Serialize Decimal as str to avoid float precision loss in cache."""

    def default(self, o: object) -> object:
        if isinstance(o, Decimal):
            return str(o)
        return super().default(o)


class CatalogService:
    """FR-4: Public catalog endpoints with Redis caching."""

    def __init__(self, session: AsyncSession, cache_repo: CacheRepository) -> None:
        self.catalog_repo = CatalogRepository(session)
        self.cache = cache_repo

    async def list_venues(self) -> list[VenueResponse]:
        """FR-4: Read-through cache for venues."""
        try:
            cached = await self.cache.get("venues:all")
            if cached is not None:
                return [VenueResponse.model_validate(v) for v in json.loads(cached)]
        except Exception:
            logger.warning("cache_read_failed", key="venues:all")

        venues = await self.catalog_repo.list_venues()
        responses = [VenueResponse.model_validate(v) for v in venues]

        try:
            await self.cache.set(
                "venues:all",
                json.dumps([r.model_dump(mode="json") for r in responses], cls=_DecimalEncoder),
                ttl=VENUE_CACHE_TTL,
            )
        except Exception:
            logger.warning("cache_write_failed", key="venues:all")

        return responses

    async def list_events(self) -> list[EventResponse]:
        """FR-4: Read-through cache for events."""
        try:
            cached = await self.cache.get("events:all")
            if cached is not None:
                return [EventResponse.model_validate(v) for v in json.loads(cached)]
        except Exception:
            logger.warning("cache_read_failed", key="events:all")

        events = await self.catalog_repo.list_events()
        responses = [EventResponse.model_validate(e) for e in events]

        try:
            await self.cache.set(
                "events:all",
                json.dumps([r.model_dump(mode="json") for r in responses], cls=_DecimalEncoder),
                ttl=EVENT_CACHE_TTL,
            )
        except Exception:
            logger.warning("cache_write_failed", key="events:all")

        return responses

    async def get_showtime(self, show_id: UUID) -> ShowtimeResponse | None:
        """FR-4: Read-through cache for showtimes."""
        cache_key = f"showtime:{show_id}"
        try:
            cached = await self.cache.get(cache_key)
            if cached is not None:
                return ShowtimeResponse.model_validate(json.loads(cached))
        except Exception:
            logger.warning("cache_read_failed", key=cache_key)

        showtime = await self.catalog_repo.get_showtime(show_id)
        if showtime is None:
            return None

        response = ShowtimeResponse.model_validate(showtime)

        try:
            await self.cache.set(
                cache_key,
                json.dumps(response.model_dump(mode="json"), cls=_DecimalEncoder),
                ttl=SHOWTIME_CACHE_TTL,
            )
        except Exception:
            logger.warning("cache_write_failed", key=cache_key)

        return response

    async def get_seat_map(self, show_id: UUID) -> SeatMapResponse:
        """FR-4: Read-through cache for seat maps."""
        cache_key = f"seatmap:{show_id}"
        try:
            cached = await self.cache.get(cache_key)
            if cached is not None:
                data = json.loads(cached)
                return SeatMapResponse(
                    show_id=UUID(data["show_id"]),
                    seats=[SeatResponse.model_validate(s) for s in data["seats"]],
                )
        except Exception:
            logger.warning("cache_read_failed", key=cache_key)

        seats = await self.catalog_repo.get_seat_map(show_id)
        responses = [SeatResponse.model_validate(s) for s in seats]
        result = SeatMapResponse(show_id=show_id, seats=responses)

        try:
            await self.cache.set(
                cache_key,
                json.dumps(result.model_dump(mode="json"), cls=_DecimalEncoder),
                ttl=SEATMAP_CACHE_TTL,
            )
        except Exception:
            logger.warning("cache_write_failed", key=cache_key)

        return result

    async def invalidate_seat_map(self, show_id: UUID) -> None:
        """FR-4: Post-commit invalidation, failure-tolerant."""
        try:
            await self.cache.invalidate(f"seatmap:{show_id}")
        except Exception:
            logger.warning("cache_invalidation_failed", key=f"seatmap:{show_id}")
