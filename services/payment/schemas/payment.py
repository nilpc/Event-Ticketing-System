"""FR-5: Pydantic schemas for payment endpoints."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class PaymentIntentRequest(BaseModel):
    """FR-5: Request to create a payment intent for a booking."""

    booking_id: UUID


class PaymentIntentResponse(BaseModel):
    """FR-5: Stripe client secret for frontend confirmation."""

    payment_id: UUID
    client_secret: str
    status: str
