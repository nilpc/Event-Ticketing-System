"""FR-7: Seat locking router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.session import get_db_session
from core.exceptions import BookingConflictError
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
async def lock_seat(
    payload: SeatLockRequest,
    request: Request,
    svc: SeatLockService = Depends(_get_seat_lock_service),
) -> SeatLockResponse:
    """FR-7: Lock a seat. Server generates the idempotency key."""
    user_id_str = request.headers.get("X-User-Id")
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Authentication required.")
    from uuid import UUID

    user_id = UUID(user_id_str)
    try:
        return await svc.lock_seat(payload.show_id, payload.seat_id, user_id)
    except BookingConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
