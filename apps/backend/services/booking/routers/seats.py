"""FR-7: Seat locking router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.session import get_db_session
from core.exceptions import BookingConflictError, SeatUnavailableError
from core.redis import get_redis
from services.booking.repositories.lock_repo import LockRepository
from services.booking.repositories.seat_repo import SeatRepository
from services.booking.schemas.seat_lock import SeatLockRequest, SeatLockResponse
from services.booking.services.seat_lock_service import SeatLockService

router = APIRouter(prefix="/v1/seats", tags=["seats"])


def _get_seat_lock_service(
    session: AsyncSession = Depends(get_db_session),
) -> SeatLockService:
    lock_repo = LockRepository(session, redis_client=get_redis())
    seat_repo = SeatRepository(session)
    return SeatLockService(session, lock_repo, seat_repo)


@router.post(
    "/lock",
    response_model=SeatLockResponse,
    responses={409: {"model": dict}},
)
async def lock_seats(
    payload: SeatLockRequest,
    request: Request,
    svc: SeatLockService = Depends(_get_seat_lock_service),
) -> SeatLockResponse:
    """FR-7: Lock one or more seats. Server generates the idempotency key."""
    from uuid import UUID

    user_id = UUID(request.state.user_id)
    try:
        return await svc.lock_seats(payload.show_id, payload.seat_ids, user_id)
    except BookingConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except SeatUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
