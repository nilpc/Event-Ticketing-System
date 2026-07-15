"""FR-6: Pydantic schemas for queue endpoints."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class QueueJoinRequest(BaseModel):
    """FR-6: Request to join the queue for a showtime."""

    show_id: UUID


class QueueJoinResponse(BaseModel):
    """FR-6: Queue join confirmation with position."""

    queue_token: str | None = None
    position: int
    status: str  # "waiting" | "admitted"


class QueueStatusResponse(BaseModel):
    """FR-6: Current queue position and estimated wait."""

    position: int | None
    status: str  # "waiting" | "admitted" | "expired"
    retry_after: int | None = None  # seconds
    queue_token: str | None = None


class QueueRecoverResponse(BaseModel):
    """FR-6: Crash recovery — returns active session token if one exists."""

    queue_token: str | None = None
    status: str  # "admitted" | "none"
