from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SeatLockRequest(BaseModel):
    show_id: UUID
    seat_ids: list[str]

class SeatLockResponse(BaseModel):
    idempotency_key: str
    expires_at: datetime
    locked_seat_ids: list[str]
