from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.db.session import get_db_session
from core.redis import get_redis
from core.security.auth import get_current_user_id
from services.booking.repositories.cache_repo import CacheRepository
from services.booking.schemas.admin import AdminEventResponse, AdminVenueResponse, EventCreate, EventUpdate, ShowtimeBatchCreate, ShowtimeCreate, ShowtimeUpdate, UserPromoteResponse, VenueCreate, VenueUpdate
from services.booking.schemas.catalog import ShowtimeResponse, VenueResponse
from services.booking.services.admin_service import AdminService
from services.identity.models.user import User
router = APIRouter(prefix='/v1/admin', tags=['admin'])

async def _require_merchant(user_id: UUID=Depends(get_current_user_id), session: AsyncSession=Depends(get_db_session)) -> User:
    result = await session.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_admin:
        raise HTTPException(status_code=403, detail='Merchant access required.')
    return user

async def _require_master_admin(user_id: UUID=Depends(get_current_user_id), session: AsyncSession=Depends(get_db_session)) -> User:
    result = await session.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_master_admin:
        raise HTTPException(status_code=403, detail='Master admin access required.')
    return user

def _get_admin_service(session: AsyncSession=Depends(get_db_session)) -> AdminService:
    return AdminService(session, cache_repo=CacheRepository(redis_client=get_redis()))

async def _assert_can_manage_event(event_id: str, merchant: User, svc: AdminService) -> None:
    event = await svc.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f'Event {event_id} not found.')
    if event.created_by != merchant.user_id:
        raise HTTPException(status_code=403, detail='Cannot modify events created by others.')

async def _assert_can_schedule(event_id: str, venue_id: str, merchant: User, svc: AdminService) -> None:
    event = await svc.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f'Event {event_id} not found.')
    venue = await svc.get_venue(venue_id)
    if venue is None:
        raise HTTPException(status_code=404, detail=f'Venue {venue_id} not found.')
    if merchant.is_master_admin:
        return
    if event.created_by != merchant.user_id:
        raise HTTPException(status_code=403, detail='Cannot schedule showtimes for events created by others.')
    if venue.created_by != merchant.user_id:
        raise HTTPException(status_code=403, detail='Cannot schedule showtimes at venues created by others.')

@router.get('/events', response_model=list[AdminEventResponse])
async def list_events(merchant: User=Depends(_require_merchant), svc: AdminService=Depends(_get_admin_service)) -> list[AdminEventResponse]:
    events = await svc.list_events(created_by=merchant.user_id if not merchant.is_master_admin else None)
    return [AdminEventResponse.model_validate(e) for e in events]

@router.post('/events', response_model=AdminEventResponse, status_code=201)
async def create_event(data: EventCreate, merchant: User=Depends(_require_merchant), svc: AdminService=Depends(_get_admin_service)) -> AdminEventResponse:
    event = await svc.create_event(data, created_by=merchant.user_id)
    return AdminEventResponse.model_validate(event)

@router.put('/events/{event_id}', response_model=AdminEventResponse)
async def update_event(event_id: str, data: EventUpdate, merchant: User=Depends(_require_merchant), svc: AdminService=Depends(_get_admin_service)) -> AdminEventResponse:
    if not merchant.is_master_admin:
        await _assert_can_manage_event(event_id, merchant, svc)
    try:
        event = await svc.update_event(event_id, data)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return AdminEventResponse.model_validate(event)

@router.delete('/events/{event_id}', status_code=204)
async def delete_event(event_id: str, merchant: User=Depends(_require_merchant), svc: AdminService=Depends(_get_admin_service)) -> None:
    if not merchant.is_master_admin:
        await _assert_can_manage_event(event_id, merchant, svc)
    try:
        await svc.delete_event(event_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

@router.get('/venues', response_model=list[AdminVenueResponse])
async def list_venues(merchant: User=Depends(_require_merchant), svc: AdminService=Depends(_get_admin_service)) -> list[AdminVenueResponse]:
    venues = await svc.list_venues(created_by=merchant.user_id if not merchant.is_master_admin else None)
    return [AdminVenueResponse.model_validate(v) for v in venues]

@router.post('/venues', response_model=AdminVenueResponse, status_code=201)
async def create_venue(data: VenueCreate, merchant: User=Depends(_require_merchant), svc: AdminService=Depends(_get_admin_service)) -> AdminVenueResponse:
    venue = await svc.create_venue(data, created_by=merchant.user_id)
    return AdminVenueResponse.model_validate(venue)

@router.put('/venues/{venue_id}', response_model=VenueResponse)
async def update_venue(venue_id: str, data: VenueUpdate, _master: User=Depends(_require_master_admin), svc: AdminService=Depends(_get_admin_service)) -> VenueResponse:
    try:
        venue = await svc.update_venue(venue_id, data)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return VenueResponse.model_validate(venue)

@router.delete('/venues/{venue_id}', status_code=204)
async def delete_venue(venue_id: str, _master: User=Depends(_require_master_admin), svc: AdminService=Depends(_get_admin_service)) -> None:
    try:
        await svc.delete_venue(venue_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

@router.get('/showtimes', response_model=list[ShowtimeResponse])
async def list_showtimes(merchant: User=Depends(_require_merchant), svc: AdminService=Depends(_get_admin_service)) -> list[ShowtimeResponse]:
    showtimes = await svc.list_showtimes(created_by=merchant.user_id if not merchant.is_master_admin else None)
    return [ShowtimeResponse.model_validate(s) for s in showtimes]

@router.post('/showtimes', response_model=ShowtimeResponse, status_code=201)
async def create_showtime(data: ShowtimeCreate, merchant: User=Depends(_require_merchant), svc: AdminService=Depends(_get_admin_service)) -> ShowtimeResponse:
    await _assert_can_schedule(data.event_id, data.venue_id, merchant, svc)
    showtime = await svc.create_showtime(data)
    return ShowtimeResponse.model_validate(showtime)

@router.post('/showtimes/batch', response_model=list[ShowtimeResponse], status_code=201)
async def create_showtimes_batch(data: ShowtimeBatchCreate, merchant: User=Depends(_require_merchant), svc: AdminService=Depends(_get_admin_service)) -> list[ShowtimeResponse]:
    await _assert_can_schedule(data.event_id, data.venue_id, merchant, svc)
    showtimes = await svc.create_showtimes_batch(data)
    return [ShowtimeResponse.model_validate(s) for s in showtimes]

@router.put('/showtimes/{show_id}', response_model=ShowtimeResponse)
async def update_showtime(show_id: str, data: ShowtimeUpdate, merchant: User=Depends(_require_merchant), svc: AdminService=Depends(_get_admin_service)) -> ShowtimeResponse:
    if not merchant.is_master_admin:
        showtime = await svc.get_showtime(show_id)
        if showtime is None:
            raise HTTPException(status_code=404, detail=f'Showtime {show_id} not found.')
        owner = await svc.get_event_owner(showtime.event_id)
        if owner != merchant.user_id:
            raise HTTPException(status_code=403, detail='Cannot modify showtimes for events created by others.')
    try:
        showtime = await svc.update_showtime(show_id, data)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return ShowtimeResponse.model_validate(showtime)

@router.delete('/showtimes/{show_id}', status_code=204)
async def delete_showtime(show_id: str, merchant: User=Depends(_require_merchant), svc: AdminService=Depends(_get_admin_service)) -> None:
    if not merchant.is_master_admin:
        showtime = await svc.get_showtime(show_id)
        if showtime is None:
            raise HTTPException(status_code=404, detail=f'Showtime {show_id} not found.')
        owner = await svc.get_event_owner(showtime.event_id)
        if owner != merchant.user_id:
            raise HTTPException(status_code=403, detail='Cannot delete showtimes for events created by others.')
    try:
        await svc.delete_showtime(show_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

@router.post('/users/{user_id}/promote', response_model=UserPromoteResponse)
async def promote_user(user_id: str, _master: User=Depends(_require_master_admin), svc: AdminService=Depends(_get_admin_service)) -> UserPromoteResponse:
    try:
        user = await svc.promote_user(user_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return UserPromoteResponse(user_id=str(user.user_id), email=user.email, is_admin=user.is_admin, is_master_admin=user.is_master_admin)
