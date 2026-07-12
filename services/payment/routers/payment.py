"""FR-5: Payment router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.session import get_db_session
from services.payment.providers.stripe_client import StripeClient
from services.payment.schemas.payment import PaymentIntentRequest, PaymentIntentResponse
from services.payment.services.payment_service import PaymentService

router = APIRouter(prefix="/v1/payments", tags=["payments"])


def _get_payment_service(session: AsyncSession = Depends(get_db_session)) -> PaymentService:
    return PaymentService(session, StripeClient())


@router.post("/intent", response_model=PaymentIntentResponse)
async def create_intent(
    payload: PaymentIntentRequest,
    svc: PaymentService = Depends(_get_payment_service),
) -> PaymentIntentResponse:
    """FR-5: Create a Stripe PaymentIntent for a booking."""
    # TODO: extract user_id from JWT via Depends(get_current_user_id) in Phase 3
    # Placeholder: return 401 until auth is wired
    raise HTTPException(
        status_code=401,
        detail="Authentication required. JWT auth dependency will be added in Phase 3.",
    )
