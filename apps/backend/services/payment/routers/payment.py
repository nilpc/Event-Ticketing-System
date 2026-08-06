from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from core.db.session import get_db_session
from core.security.auth import get_current_user_id
from services.payment.providers.stripe_client import StripeClient
from services.payment.schemas.payment import PaymentIntentRequest, PaymentIntentResponse, PaymentSyncResponse
from services.payment.services.payment_service import PaymentService
router = APIRouter(prefix='/v1/payments', tags=['payments'])

def _get_payment_service(session: AsyncSession=Depends(get_db_session)) -> PaymentService:
    return PaymentService(session, StripeClient())

@router.post('/intent', response_model=PaymentIntentResponse)
async def create_intent(payload: PaymentIntentRequest, user_id: UUID=Depends(get_current_user_id), svc: PaymentService=Depends(_get_payment_service)) -> PaymentIntentResponse:
    return await svc.create_intent(booking_id=payload.booking_id, user_id=user_id)

@router.post('/{payment_id}/sync', response_model=PaymentSyncResponse)
async def sync_payment(payment_id: UUID, user_id: UUID=Depends(get_current_user_id), svc: PaymentService=Depends(_get_payment_service)) -> PaymentSyncResponse:
    return await svc.sync_payment(payment_id=payment_id, user_id=user_id)
