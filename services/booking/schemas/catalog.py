"""FR-4: Pydantic schemas for catalog responses."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from core.enums import SeatStatus


class VenueResponse(BaseModel):
    venue_id: UUID
    name: str
    capacity: int

    model_config = {"from_attributes": True}


class EventResponse(BaseModel):
    event_id: UUID
    name: str
    description: str | None = None

    model_config = {"from_attributes": True}


class SeatResponse(BaseModel):
    seat_id: str
    tier: str
    price: Decimal
    status: SeatStatus

    model_config = {"from_attributes": True}


class ShowtimeResponse(BaseModel):
    show_id: UUID
    event_id: UUID
    venue_id: UUID
    base_price: Decimal
    start_time: datetime
    end_time: datetime

    model_config = {"from_attributes": True}


class SeatMapResponse(BaseModel):
    show_id: UUID
    seats: list[SeatResponse]
