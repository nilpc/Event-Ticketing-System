from __future__ import annotations

import json
import time
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
import stripe
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import BookingStatus, SeatStatus
from services.booking.models.booking import Booking
from services.booking.models.outbox_event import OutboxEvent
from services.booking.models.payment import Payment
from services.booking.models.processed_webhook import ProcessedWebhookEvent
from services.booking.models.seat import Seat
from services.booking.repositories.booking_repo import BookingRepository
from services.booking.repositories.lock_repo import LockRepository
from services.booking.repositories.seat_repo import SeatRepository
from services.payment.repositories.payment_repo import PaymentRepository
from services.payment.services.webhook_service import WebhookService
from tests.payment.fakes import FakeWebhookProvider, make_stripe_event


async def _create_payment(session: AsyncSession, booking_id: UUID, provider_payment_id: str, status: str='requires_action') -> UUID:
    repo = PaymentRepository(session)
    payment_id = uuid4()
    await repo.create_payment_record(payment_id=payment_id, booking_id=booking_id, amount=Decimal('100.00'), status=status)
    await repo.update_payment_record(payment_id=payment_id, provider_payment_id=provider_payment_id, status=status)
    await session.flush()
    return payment_id

def _webhook_service(session: AsyncSession) -> WebhookService:
    return WebhookService(session, BookingRepository(session), SeatRepository(session), LockRepository(session=None), PaymentRepository(session))

def _real_stripe_event(event_type: str, metadata: dict, intent_id: str='pi_test_123', event_id: str | None=None) -> stripe.Event:
    payload_obj = {'id': event_id or f'evt_{uuid4().hex}', 'object': 'event', 'api_version': '2024-06-20', 'created': int(time.time()), 'livemode': False, 'pending_webhooks': 1, 'request': {'id': 'req_test', 'idempotency_key': 'x'}, 'type': event_type, 'data': {'object': {'id': intent_id, 'metadata': metadata}}}
    payload = json.dumps(payload_obj)
    secret = 'whsec_test'
    ts = int(time.time())
    sig = 't={},v1={}'.format(ts, stripe.WebhookSignature._compute_signature(f'{ts}.{payload}', secret))
    return stripe.Webhook.construct_event(payload.encode(), sig, secret)

def _metadata(booking_fixture: dict) -> dict:
    return {'booking_id': str(booking_fixture['booking_id']), 'show_id': str(booking_fixture['show_id']), 'user_id': str(booking_fixture['user_id']), 'seat_ids': ','.join(booking_fixture['seat_ids'])}

async def test_webhook_succeeded(db_session, booking_fixture) -> None:
    intent_id = 'pi_success_123'
    await _create_payment(db_session, booking_fixture['booking_id'], intent_id)
    event = make_stripe_event('payment_intent.succeeded', _metadata(booking_fixture), intent_id=intent_id)
    svc = _webhook_service(db_session)
    svc.provider = FakeWebhookProvider(event)
    await svc.process_webhook(b'{}', 't=1,v1=deadbeef')
    payment = (await db_session.execute(select(Payment).where(Payment.provider_payment_id == intent_id))).scalar_one()
    assert payment.status == 'succeeded'
    booking = (await db_session.execute(select(Booking).where(Booking.booking_id == booking_fixture['booking_id']))).scalar_one()
    assert booking.status == BookingStatus.CONFIRMED
    seats = (await db_session.execute(select(Seat).where(Seat.show_id == booking_fixture['show_id']))).scalars().all()
    assert all(s.status == SeatStatus.SOLD for s in seats)
    outbox = (await db_session.execute(select(OutboxEvent).where(OutboxEvent.aggregate_id == booking_fixture['booking_id']))).scalars().all()
    assert {e.event_type for e in outbox} == {'BOOKING_CONFIRMED'}
    assert len(outbox) == len(booking_fixture['seat_ids'])
    logged = (await db_session.execute(select(ProcessedWebhookEvent).where(ProcessedWebhookEvent.event_id == event.id))).scalar_one_or_none()
    assert logged is not None
    assert logged.event_type == 'payment_intent.succeeded'

async def test_webhook_succeeded_with_real_stripe_metadata(db_session, booking_fixture) -> None:
    intent_id = 'pi_real_meta_123'
    await _create_payment(db_session, booking_fixture['booking_id'], intent_id)
    event = _real_stripe_event('payment_intent.succeeded', _metadata(booking_fixture), intent_id=intent_id)
    svc = _webhook_service(db_session)
    svc.provider = FakeWebhookProvider(event)
    await svc.process_webhook(b'{}', 't=1,v1=deadbeef')
    booking = (await db_session.execute(select(Booking).where(Booking.booking_id == booking_fixture['booking_id']))).scalar_one()
    assert booking.status == BookingStatus.CONFIRMED
    payment = (await db_session.execute(select(Payment).where(Payment.provider_payment_id == intent_id))).scalar_one()
    assert payment.status == 'succeeded'

async def test_webhook_payment_failed(db_session, booking_fixture) -> None:
    intent_id = 'pi_failed_123'
    await _create_payment(db_session, booking_fixture['booking_id'], intent_id)
    event = make_stripe_event('payment_intent.payment_failed', _metadata(booking_fixture), intent_id=intent_id)
    svc = _webhook_service(db_session)
    svc.provider = FakeWebhookProvider(event)
    await svc.process_webhook(b'{}', 't=1,v1=deadbeef')
    payment = (await db_session.execute(select(Payment).where(Payment.provider_payment_id == intent_id))).scalar_one()
    assert payment.status == 'failed'
    booking = (await db_session.execute(select(Booking).where(Booking.booking_id == booking_fixture['booking_id']))).scalar_one()
    assert booking.status == BookingStatus.FAILED
    seats = (await db_session.execute(select(Seat).where(Seat.show_id == booking_fixture['show_id']))).scalars().all()
    assert all(s.status == SeatStatus.AVAILABLE for s in seats)

async def test_webhook_invalid_signature(db_session, booking_fixture) -> None:
    svc = _webhook_service(db_session)
    svc.provider = FakeWebhookProvider(event=None, error=ValueError('Invalid webhook signature.'))
    with pytest.raises(ValueError):
        await svc.process_webhook(b'{}', 't=1,v1=bad')

async def test_webhook_missing_booking_id(db_session, booking_fixture) -> None:
    event = make_stripe_event('payment_intent.succeeded', {'seat_ids': 'A1'})
    svc = _webhook_service(db_session)
    svc.provider = FakeWebhookProvider(event)
    await svc.process_webhook(b'{}', 't=1,v1=deadbeef')
    booking = (await db_session.execute(select(Booking).where(Booking.booking_id == booking_fixture['booking_id']))).scalar_one()
    assert booking.status == BookingStatus.PENDING

async def test_webhook_duplicate_event_is_dropped(db_session, booking_fixture) -> None:
    intent_id = 'pi_dup_123'
    await _create_payment(db_session, booking_fixture['booking_id'], intent_id)
    event = make_stripe_event('payment_intent.succeeded', _metadata(booking_fixture), event_id='evt_duplicate', intent_id=intent_id)
    svc = _webhook_service(db_session)
    svc.provider = FakeWebhookProvider(event)
    await svc.process_webhook(b'{}', 't=1,v1=deadbeef')
    await svc.process_webhook(b'{}', 't=1,v1=deadbeef')
    count = (await db_session.execute(select(func.count()).select_from(ProcessedWebhookEvent).where(ProcessedWebhookEvent.event_id == event.id))).scalar_one()
    assert count == 1
    booking = (await db_session.execute(select(Booking).where(Booking.booking_id == booking_fixture['booking_id']))).scalar_one()
    assert booking.status == BookingStatus.CONFIRMED
