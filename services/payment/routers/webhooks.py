"""FR-9: Webhook receiver — Stripe payment callbacks."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.session import get_db_session
from core.redis import get_redis
from services.booking.repositories.booking_repo import BookingRepository
from services.booking.repositories.lock_repo import LockRepository
from services.booking.repositories.seat_repo import SeatRepository
from services.payment.services.webhook_service import WebhookService

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


def _get_webhook_service(
    session: AsyncSession = Depends(get_db_session),
) -> WebhookService:
    lock_repo = LockRepository(session, redis_client=get_redis())
    seat_repo = SeatRepository(session)
    booking_repo = BookingRepository(session)
    return WebhookService(session, booking_repo, seat_repo, lock_repo)


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    svc: WebhookService = Depends(_get_webhook_service),
) -> dict:
    """FR-9: Stripe webhook receiver. No auth — signature verified."""
    body = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        await svc.process_webhook(body, sig_header)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Webhook processing failed")

    return {"status": "ok"}
