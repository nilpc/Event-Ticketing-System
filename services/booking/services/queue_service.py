"""FR-6: QueueService — join, status, and crash recovery."""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from services.booking.repositories.lock_repo import LockRepository
from services.booking.schemas.queue import (
    QueueJoinResponse,
    QueueRecoverResponse,
    QueueStatusResponse,
)

logger = structlog.get_logger()

# FR-6: Fixed admission rate (users per second)
ADMISSION_RATE = 10


class QueueService:
    """FR-6: Queue business logic — join, status, recover."""

    def __init__(self, session: AsyncSession, lock_repo: LockRepository) -> None:
        self.lock_repo = lock_repo

    async def join(self, show_id: UUID, user_id: UUID) -> QueueJoinResponse:
        """FR-6: Add user to queue. If already admitted, return existing token."""
        # Check if already admitted
        existing_token = await self.lock_repo.get_admitted_token(show_id, user_id)
        if existing_token is not None:
            return QueueJoinResponse(
                queue_token=existing_token, position=0, status="admitted"
            )

        # Check if already in queue
        position = await self.lock_repo.get_queue_position(show_id, user_id)
        if position is not None:
            return QueueJoinResponse(position=position, status="waiting")

        # Enqueue
        position = await self.lock_repo.enqueue_user(show_id, user_id)
        return QueueJoinResponse(position=position, status="waiting")

    async def status(self, show_id: UUID, user_id: UUID) -> QueueStatusResponse:
        """FR-6: Get queue position with Retry-After header."""
        # Check if admitted
        if await self.lock_repo.is_user_admitted(show_id, user_id):
            return QueueStatusResponse(position=0, status="admitted")

        position = await self.lock_repo.get_queue_position(show_id, user_id)
        if position is None:
            return QueueStatusResponse(position=None, status="expired")

        # FR-6: Calculate Retry-After based on position and admission rate
        retry_after = max(1, position // ADMISSION_RATE)
        return QueueStatusResponse(
            position=position, status="waiting", retry_after=retry_after
        )

    async def recover(self, show_id: UUID, user_id: UUID) -> QueueRecoverResponse:
        """FR-6: Crash recovery — return active session token if exists."""
        token = await self.lock_repo.get_admitted_token(show_id, user_id)
        if token is not None:
            return QueueRecoverResponse(queue_token=token, status="admitted")
        return QueueRecoverResponse(status="none")
