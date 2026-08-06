from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
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
CDN_CACHE_HEADER = "public, max-age=15, s-maxage=60, stale-while-revalidate=30"


def _get_catalog_service(session: AsyncSession = Depends(get_db_session)) -> CatalogService:
    cache_repo = CacheRepository(redis_client=get_redis())
    return CatalogService(session, cache_repo)


@router.get("/venues", response_model=list[VenueResponse])
async def list_venues(
    response: Response, svc: CatalogService = Depends(_get_catalog_service)
) -> list[VenueResponse]:
    response.headers["Cache-Control"] = CDN_CACHE_HEADER
    return await svc.list_venues()


@router.get("/events", response_model=list[EventResponse])
async def list_events(
    response: Response, svc: CatalogService = Depends(_get_catalog_service)
) -> list[EventResponse]:
    response.headers["Cache-Control"] = CDN_CACHE_HEADER
    return await svc.list_events()


@router.get("/events/{event_id}/showtimes", response_model=list[ShowtimeResponse])
async def list_showtimes_for_event(
    event_id: str, response: Response, svc: CatalogService = Depends(_get_catalog_service)
) -> list[ShowtimeResponse]:
    response.headers["Cache-Control"] = CDN_CACHE_HEADER
    return await svc.list_showtimes_by_event(event_id)


@router.get("/showtimes", response_model=list[ShowtimeResponse])
async def list_showtimes(
    response: Response, svc: CatalogService = Depends(_get_catalog_service)
) -> list[ShowtimeResponse]:
    response.headers["Cache-Control"] = CDN_CACHE_HEADER
    return await svc.list_showtimes()


@router.get("/showtimes/{show_id}", response_model=ShowtimeResponse)
async def get_showtime(
    show_id: UUID, response: Response, svc: CatalogService = Depends(_get_catalog_service)
) -> ShowtimeResponse:
    response.headers["Cache-Control"] = CDN_CACHE_HEADER
    result = await svc.get_showtime(show_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Showtime not found.")
    return result


@router.get("/showtimes/{show_id}/seats", response_model=SeatMapResponse)
async def get_seat_map(
    show_id: UUID, svc: CatalogService = Depends(_get_catalog_service)
) -> SeatMapResponse:
    return await svc.get_seat_map(show_id)
