"""FR-4: Public catalog router."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.session import get_db_session
from core.redis import get_redis
from services.booking.repositories.cache_repo import CacheRepository
from services.booking.schemas.catalog import (
    EventResponse,
    SeatMapResponse,
    ShowtimeResponse,
    VenueResponse,
)
from services.booking.services.catalog_service import CatalogService

router = APIRouter(prefix="/v1", tags=["catalog"])


def _get_catalog_service(session: AsyncSession = Depends(get_db_session)) -> CatalogService:
    cache_repo = CacheRepository(redis_client=get_redis())
    return CatalogService(session, cache_repo)


@router.get("/venues", response_model=list[VenueResponse])
async def list_venues(
    svc: CatalogService = Depends(_get_catalog_service),
) -> list[VenueResponse]:
    """FR-4: List all venues."""
    return await svc.list_venues()


@router.get("/events", response_model=list[EventResponse])
async def list_events(
    svc: CatalogService = Depends(_get_catalog_service),
) -> list[EventResponse]:
    """FR-4: List all events."""
    return await svc.list_events()


@router.get("/showtimes/{show_id}", response_model=ShowtimeResponse)
async def get_showtime(
    show_id: UUID,
    svc: CatalogService = Depends(_get_catalog_service),
) -> ShowtimeResponse:
    """FR-4: Get showtime by ID."""
    result = await svc.get_showtime(show_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Showtime not found.")
    return result


@router.get("/showtimes/{show_id}/seats", response_model=SeatMapResponse)
async def get_seat_map(
    show_id: UUID,
    svc: CatalogService = Depends(_get_catalog_service),
) -> SeatMapResponse:
    """FR-4: Get seat map for a showtime."""
    return await svc.get_seat_map(show_id)
