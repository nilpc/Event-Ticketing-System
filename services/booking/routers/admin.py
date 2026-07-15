"""Admin CRUD router — protected endpoints for catalog management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import settings
from core.db.session import get_db_session
from core.security.auth import get_current_user_id
from services.booking.schemas.admin import (
    EventCreate,
    EventUpdate,
    ShowtimeCreate,
    ShowtimeUpdate,
    VenueCreate,
    VenueUpdate,
)
from services.booking.schemas.catalog import (
    EventResponse,
    ShowtimeResponse,
    VenueResponse,
)
from services.booking.services.admin_service import AdminService

router = APIRouter(prefix="/v1/admin", tags=["admin"])


def _require_admin(x_admin_token: str = Header(...)) -> None:
    """Simple admin gate — FR-4: only holders of the admin secret can mutate."""
    if not settings.ADMIN_TOKEN or x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid admin token.")


def _get_admin_service(session: AsyncSession = Depends(get_db_session)) -> AdminService:
    return AdminService(session)


# ── Events ─────────────────────────────────────────────────────────────


@router.post("/events", response_model=EventResponse, status_code=201)
async def create_event(
    data: EventCreate,
    request: Request,
    _admin: None = Depends(_require_admin),
    svc: AdminService = Depends(_get_admin_service),
) -> EventResponse:
    get_current_user_id(request)
    event = await svc.create_event(data)
    return EventResponse.model_validate(event)


@router.put("/events/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: str,
    data: EventUpdate,
    request: Request,
    _admin: None = Depends(_require_admin),
    svc: AdminService = Depends(_get_admin_service),
) -> EventResponse:
    get_current_user_id(request)
    try:
        event = await svc.update_event(event_id, data)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return EventResponse.model_validate(event)


@router.delete("/events/{event_id}", status_code=204)
async def delete_event(
    event_id: str,
    request: Request,
    _admin: None = Depends(_require_admin),
    svc: AdminService = Depends(_get_admin_service),
) -> None:
    get_current_user_id(request)
    try:
        await svc.delete_event(event_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ── Venues ─────────────────────────────────────────────────────────────


@router.post("/venues", response_model=VenueResponse, status_code=201)
async def create_venue(
    data: VenueCreate,
    request: Request,
    _admin: None = Depends(_require_admin),
    svc: AdminService = Depends(_get_admin_service),
) -> VenueResponse:
    get_current_user_id(request)
    venue = await svc.create_venue(data)
    return VenueResponse.model_validate(venue)


@router.put("/venues/{venue_id}", response_model=VenueResponse)
async def update_venue(
    venue_id: str,
    data: VenueUpdate,
    request: Request,
    _admin: None = Depends(_require_admin),
    svc: AdminService = Depends(_get_admin_service),
) -> VenueResponse:
    get_current_user_id(request)
    try:
        venue = await svc.update_venue(venue_id, data)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return VenueResponse.model_validate(venue)


@router.delete("/venues/{venue_id}", status_code=204)
async def delete_venue(
    venue_id: str,
    request: Request,
    _admin: None = Depends(_require_admin),
    svc: AdminService = Depends(_get_admin_service),
) -> None:
    get_current_user_id(request)
    try:
        await svc.delete_venue(venue_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ── Showtimes ──────────────────────────────────────────────────────────


@router.post("/showtimes", response_model=ShowtimeResponse, status_code=201)
async def create_showtime(
    data: ShowtimeCreate,
    request: Request,
    _admin: None = Depends(_require_admin),
    svc: AdminService = Depends(_get_admin_service),
) -> ShowtimeResponse:
    get_current_user_id(request)
    showtime = await svc.create_showtime(data)
    return ShowtimeResponse.model_validate(showtime)


@router.put("/showtimes/{show_id}", response_model=ShowtimeResponse)
async def update_showtime(
    show_id: str,
    data: ShowtimeUpdate,
    request: Request,
    _admin: None = Depends(_require_admin),
    svc: AdminService = Depends(_get_admin_service),
) -> ShowtimeResponse:
    get_current_user_id(request)
    try:
        showtime = await svc.update_showtime(show_id, data)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return ShowtimeResponse.model_validate(showtime)


@router.delete("/showtimes/{show_id}", status_code=204)
async def delete_showtime(
    show_id: str,
    request: Request,
    _admin: None = Depends(_require_admin),
    svc: AdminService = Depends(_get_admin_service),
) -> None:
    get_current_user_id(request)
    try:
        await svc.delete_showtime(show_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
