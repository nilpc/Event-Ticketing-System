"""FR-6: Queue router — join, status, and crash recovery."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.session import get_db_session
from core.redis import get_redis
from services.booking.repositories.lock_repo import LockRepository
from services.booking.schemas.queue import (
    QueueJoinRequest,
    QueueJoinResponse,
    QueueRecoverResponse,
    QueueStatusResponse,
)
from services.booking.services.queue_service import QueueService

router = APIRouter(prefix="/v1/queue", tags=["queue"])


def _get_queue_service(
    session: AsyncSession = Depends(get_db_session),
) -> QueueService:
    lock_repo = LockRepository(session, redis_client=get_redis())
    return QueueService(session, lock_repo)


@router.post("/join", response_model=QueueJoinResponse)
async def join_queue(
    payload: QueueJoinRequest,
    request: Request,
    svc: QueueService = Depends(_get_queue_service),
) -> QueueJoinResponse:
    """FR-6: Join the queue for a showtime. Returns position."""
    from uuid import UUID

    user_id = UUID(request.state.user_id)
    return await svc.join(payload.show_id, user_id)


@router.get("/status", response_model=QueueStatusResponse)
async def queue_status(
    show_id: str,
    request: Request,
    svc: QueueService = Depends(_get_queue_service),
) -> QueueStatusResponse:
    """FR-6: Get queue position. Response includes Retry-After header."""
    from uuid import UUID

    user_id = UUID(request.state.user_id)
    result = await svc.status(UUID(show_id), user_id)
    return result


@router.get("/recover", response_model=QueueRecoverResponse)
async def recover_queue(
    show_id: str,
    request: Request,
    svc: QueueService = Depends(_get_queue_service),
) -> QueueRecoverResponse:
    """FR-6: Crash recovery — returns active session token if one exists."""
    from uuid import UUID

    user_id = UUID(request.state.user_id)
    return await svc.recover(UUID(show_id), user_id)
