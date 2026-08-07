from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class PaymentIntentRequest(BaseModel):
    booking_id: UUID

class PaymentIntentResponse(BaseModel):
    payment_id: UUID
    client_secret: str
    status: str

class PaymentSyncResponse(BaseModel):
    payment_id: UUID
    payment_status: str
    booking_id: UUID
    booking_status: str
