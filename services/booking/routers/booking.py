"""FR-8, FR-10: Booking router — atomic checkout."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.session import get_db_session
from core.exceptions import (
    BookingConflictError,
    InvalidTokenError,
    PersistenceError,
    SeatUnavailableError,
)
from core.redis import get_redis
from services.booking.repositories.booking_repo import BookingRepository
from services.booking.repositories.cache_repo import CacheRepository
from services.booking.repositories.lock_repo import LockRepository
from services.booking.repositories.seat_repo import SeatRepository
from services.booking.schemas.booking import BookRequest, BookResponse
from services.booking.services.booking_service import BookingService

router = APIRouter(prefix="/v1", tags=["booking"])


def _get_booking_service(
    session: AsyncSession = Depends(get_db_session),
) -> BookingService:
    lock_repo = LockRepository(session, redis_client=get_redis())
    seat_repo = SeatRepository(session)
    booking_repo = BookingRepository(session)
    cache_repo = CacheRepository(redis_client=get_redis())
    return BookingService(session, seat_repo, booking_repo, lock_repo, cache_repo)


@router.post(
    "/book",
    response_model=BookResponse,
    responses={
        409: {"model": dict},
        422: {"model": dict},
    },
)
async def book_seat(
    payload: BookRequest,
    request: Request,
    svc: BookingService = Depends(_get_booking_service),
) -> BookResponse:
    """FR-8, FR-10: Atomic booking initialization.

    Single transaction: seat transition, server-side price lookup,
    booking insert, outbox event — §6 Layer 1.
    """
    user_id_str = request.headers.get("X-User-Id")
    queue_token = request.headers.get("X-Queue-Token", "")
    request_id = request.headers.get("X-Request-ID", "")

    if not user_id_str:
        raise HTTPException(status_code=401, detail="Authentication required.")
    from uuid import UUID

    user_id = UUID(user_id_str)
    try:
        return await svc.initialize_checkout(
            show_id=payload.show_id,
            seat_id=payload.seat_id,
            user_id=user_id,
            idempotency_key=payload.idempotency_key,
            queue_token=queue_token,
            request_id=request_id,
        )
    except BookingConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except SeatUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except InvalidTokenError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except PersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
