from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class QueueJoinRequest(BaseModel):
    show_id: UUID

class QueueJoinResponse(BaseModel):
    queue_token: str | None = None
    position: int
    status: str

class QueueStatusResponse(BaseModel):
    position: int | None
    status: str
    retry_after: int | None = None
    queue_token: str | None = None

class QueueRecoverResponse(BaseModel):
    queue_token: str | None = None
    status: str
