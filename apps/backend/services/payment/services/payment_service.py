from __future__ import annotations
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4
import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from core.enums import BookingStatus, PaymentStatus
from core.exceptions import BookingConflictError, NotFoundError
from services.booking.repositories.booking_repo import BookingRepository
from services.booking.repositories.seat_repo import SeatRepository
from services.payment.providers.stripe_client import PaymentIntentProvider
from services.payment.repositories.payment_repo import PaymentRepository
from services.payment.schemas.payment import PaymentIntentResponse, PaymentSyncResponse
logger = structlog.get_logger()
EXPIRY_GUARD_MINUTES = 2

class PaymentService:

    def __init__(self, session: AsyncSession, provider: PaymentIntentProvider) -> None:
        self.session = session
        self.provider = provider
        self.booking_repo = BookingRepository(session)
        self.seat_repo = SeatRepository(session)
        self.payment_repo = PaymentRepository(session)

    async def create_intent(self, booking_id: UUID, user_id: UUID) -> PaymentIntentResponse:
        booking = await self.booking_repo.get_booking_by_id(booking_id)
        if booking is None:
            raise NotFoundError('Booking not found.')
        if booking.user_id != user_id:
            raise NotFoundError('Booking not found.')
        guard_time = datetime.now(UTC) + timedelta(minutes=EXPIRY_GUARD_MINUTES)
        if booking.expires_at < guard_time:
            raise BookingConflictError('Booking is about to expire. Please start a new booking.')
        existing = await self.payment_repo.get_active_payment_for_booking(booking_id)
        if existing is not None and existing.provider_payment_id:
            logger.info('reusing_existing_intent', payment_id=existing.payment_id)
            intent = await self.provider.retrieve_payment_intent(existing.provider_payment_id)
            return PaymentIntentResponse(payment_id=existing.payment_id, client_secret=intent.client_secret or '', status=existing.status)
        payment_id = uuid4()
        amount_cents = int(booking.amount * 100)
        try:
            await self.payment_repo.create_payment_record(payment_id=payment_id, booking_id=booking_id, amount=booking.amount, status=PaymentStatus.INITIATED)
            await self.session.flush()
        except IntegrityError:
            existing = await self.payment_repo.get_active_payment_for_booking(booking_id)
            if existing is not None and existing.provider_payment_id:
                intent = await self.provider.retrieve_payment_intent(existing.provider_payment_id)
                return PaymentIntentResponse(payment_id=existing.payment_id, client_secret=intent.client_secret or '', status=existing.status)
            raise
        new_intent = None
        try:
            booking_seats = await self.booking_repo.get_booking_seats(booking_id)
            seat_ids = [bs.seat_id for bs in booking_seats]
            new_intent = await self.provider.create_payment_intent(amount_cents=amount_cents, currency=booking.currency, payment_method_types=['card'], metadata={'booking_id': str(booking_id), 'payment_id': str(payment_id), 'show_id': str(booking.show_id), 'user_id': str(booking.user_id), 'seat_ids': ','.join(seat_ids)})
            await self.payment_repo.update_payment_record(payment_id=payment_id, provider_payment_id=new_intent.id, status=PaymentStatus.REQUIRES_ACTION)
            return PaymentIntentResponse(payment_id=payment_id, client_secret=new_intent.client_secret or '', status=PaymentStatus.REQUIRES_ACTION)
        except Exception:
            if new_intent is not None:
                try:
                    await self.provider.cancel_payment_intent(new_intent.id)
                except Exception:
                    logger.warning('stripe_orphan_cancel_failed', intent_id=new_intent.id, payment_id=str(payment_id))
            await self.payment_repo.update_payment_record(payment_id=payment_id, status=PaymentStatus.FAILED)
            raise

    async def sync_payment(self, payment_id: UUID, user_id: UUID) -> PaymentSyncResponse:
        payment = await self.payment_repo.get_payment_by_id(payment_id)
        if payment is None:
            raise NotFoundError('Payment not found.')
        booking = await self.booking_repo.get_booking_by_id(payment.booking_id)
        if booking is None:
            raise NotFoundError('Booking not found.')
        if booking.user_id != user_id:
            raise NotFoundError('Booking not found.')
        if not payment.provider_payment_id:
            raise BookingConflictError('Payment has no associated Stripe intent.')
        intent = await self.provider.retrieve_payment_intent(payment.provider_payment_id)
        if intent.status == 'succeeded' and booking.status == BookingStatus.PENDING:
            async with self.session.begin_nested():
                await self.payment_repo.update_payment_record(payment_id=payment_id, status=PaymentStatus.SUCCEEDED)
                booking_seats = await self.booking_repo.get_booking_seats(booking.booking_id)
                seat_ids = [bs.seat_id for bs in booking_seats]
                await self.seat_repo.finalize_sold_seats(booking.show_id, seat_ids)
                await self.booking_repo.update_booking_status(booking.booking_id, BookingStatus.CONFIRMED, source='payment-sync')
                for seat_id in seat_ids:
                    await self.booking_repo.add_outbox_event(aggregate_type='Booking', aggregate_id=booking.booking_id, event_type='BOOKING_CONFIRMED', payload={'booking_id': str(booking.booking_id), 'show_id': str(booking.show_id), 'seat_id': seat_id})
            return PaymentSyncResponse(payment_id=payment_id, payment_status=PaymentStatus.SUCCEEDED, booking_id=booking.booking_id, booking_status=BookingStatus.CONFIRMED.value)
        return PaymentSyncResponse(payment_id=payment_id, payment_status=intent.status or payment.status, booking_id=booking.booking_id, booking_status=booking.status.value)
