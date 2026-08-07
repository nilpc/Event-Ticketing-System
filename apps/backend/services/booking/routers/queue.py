from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
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

router = APIRouter(prefix='/v1/queue', tags=['queue'])

def _get_queue_service(session: AsyncSession=Depends(get_db_session)) -> QueueService:
    lock_repo = LockRepository(session, redis_client=get_redis())
    return QueueService(session, lock_repo)

@router.post('/join', response_model=QueueJoinResponse)
async def join_queue(payload: QueueJoinRequest, request: Request, svc: QueueService=Depends(_get_queue_service)) -> QueueJoinResponse:
    from uuid import UUID
    user_id = UUID(request.state.user_id)
    return await svc.join(payload.show_id, user_id)

@router.get('/status', response_model=QueueStatusResponse)
async def queue_status(show_id: str, request: Request, svc: QueueService=Depends(_get_queue_service)) -> QueueStatusResponse:
    from uuid import UUID
    user_id = UUID(request.state.user_id)
    result = await svc.status(UUID(show_id), user_id)
    return result

@router.get('/stream')
async def queue_stream(show_id: str, request: Request, svc: QueueService=Depends(_get_queue_service)) -> StreamingResponse:
    import asyncio
    import json
    from uuid import UUID
    user_id = UUID(request.state.user_id)
    show_uuid = UUID(show_id)

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            res = await svc.status(show_uuid, user_id)
            payload = json.dumps({'status': res.status.value, 'position': res.position, 'estimated_wait_seconds': res.estimated_wait_seconds, 'session_token': res.session_token})
            yield f'data: {payload}\n\n'
            if res.status.value in ('ADMITTED', 'EXPIRED'):
                break
            await asyncio.sleep(min(res.retry_after_seconds, 3))
    return StreamingResponse(event_generator(), media_type='text/event-stream')

@router.get('/recover', response_model=QueueRecoverResponse)
async def recover_queue(show_id: str, request: Request, svc: QueueService=Depends(_get_queue_service)) -> QueueRecoverResponse:
    from uuid import UUID
    user_id = UUID(request.state.user_id)
    return await svc.recover(UUID(show_id), user_id)
