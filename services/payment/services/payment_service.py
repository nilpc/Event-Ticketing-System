"""FR-5: PaymentService — PCI-compliant payment intent creation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import PaymentStatus
from core.exceptions import BookingConflictError, NotFoundError
from services.booking.repositories.booking_repo import BookingRepository
from services.payment.providers.stripe_client import StripeClient
from services.payment.repositories.payment_repo import PaymentRepository
from services.payment.schemas.payment import PaymentIntentResponse

logger = structlog.get_logger()

EXPIRY_GUARD_MINUTES = 2


class PaymentService:
    """FR-5: Mirrors §6 CSR example — write-before-call, cancel-on-failure."""

    def __init__(self, session: AsyncSession, provider: StripeClient) -> None:
        self.session = session
        self.provider = provider
        self.booking_repo = BookingRepository(session)
        self.payment_repo = PaymentRepository(session)

    async def create_intent(
        self,
        booking_id: UUID,
        user_id: UUID,
    ) -> PaymentIntentResponse:
        """FR-5: Create payment intent with orphan prevention."""
        booking = await self.booking_repo.get_booking_by_id(booking_id)
        if booking is None:
            raise NotFoundError("Booking not found.")

        if booking.user_id != user_id:
            raise NotFoundError("Booking not found.")

        guard_time = datetime.now(UTC) + timedelta(minutes=EXPIRY_GUARD_MINUTES)
        if booking.expires_at < guard_time:
            raise BookingConflictError(
                "Booking is about to expire. Please start a new booking."
            )

        # FR-5: Check for existing non-terminal intent
        existing = await self.payment_repo.get_active_payment_for_booking(booking_id)
        if existing is not None and existing.provider_payment_id:
            logger.info("reusing_existing_intent", payment_id=existing.payment_id)
            # FR-5: Retrieve the real client_secret from Stripe for reuse
            intent = await self.provider.retrieve_payment_intent(existing.provider_payment_id)
            return PaymentIntentResponse(
                payment_id=existing.payment_id,
                client_secret=intent.client_secret or "",
                status=existing.status,
            )

        payment_id = uuid4()
        amount_cents = int(booking.amount * 100)

        # FR-5: Write initiated record BEFORE calling Stripe
        await self.payment_repo.create_payment_record(
            payment_id=payment_id,
            booking_id=booking_id,
            amount=booking.amount,
            status=PaymentStatus.INITIATED,
        )
        await self.session.flush()

        try:
            intent = await self.provider.create_payment_intent(
                amount_cents=amount_cents,
                currency=booking.currency,
                metadata={
                    "booking_id": str(booking_id),
                    "payment_id": str(payment_id),
                },
            )
            await self.payment_repo.update_payment_record(
                payment_id=payment_id,
                provider_payment_id=intent.id,
                status=PaymentStatus.REQUIRES_ACTION,
            )
            return PaymentIntentResponse(
                payment_id=payment_id,
                client_secret=intent.client_secret or "",
                status=PaymentStatus.REQUIRES_ACTION,
            )
        except Exception:
            # FR-5: Mark as failed — no orphaned Stripe intents
            await self.payment_repo.update_payment_record(
                payment_id=payment_id,
                status=PaymentStatus.FAILED,
            )
            raise
