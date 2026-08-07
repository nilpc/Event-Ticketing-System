from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import BookingStatus, PaymentStatus, SeatStatus
from core.exceptions import BookingConflictError, NotFoundError, PaymentProviderError
from services.booking.models.booking import Booking
from services.booking.models.outbox_event import OutboxEvent
from services.booking.models.payment import Payment
from services.booking.models.seat import Seat
from services.identity.models.user import User
from services.payment.repositories.payment_repo import PaymentRepository
from services.payment.services.payment_service import PaymentService
from tests.payment.fakes import FakeStripeClient


async def _create_payment(session: AsyncSession, booking_id: UUID, provider_payment_id: str, status: str='requires_action') -> UUID:
    repo = PaymentRepository(session)
    payment_id = uuid4()
    await repo.create_payment_record(payment_id=payment_id, booking_id=booking_id, amount=Decimal('100.00'), status=status)
    await repo.update_payment_record(payment_id=payment_id, provider_payment_id=provider_payment_id, status=status)
    await session.flush()
    return payment_id

async def test_create_intent_happy_path(db_session, booking_fixture) -> None:
    provider = FakeStripeClient()
    svc = PaymentService(db_session, provider)
    response = await svc.create_intent(booking_id=booking_fixture['booking_id'], user_id=booking_fixture['user_id'])
    assert response.status == PaymentStatus.REQUIRES_ACTION
    assert response.client_secret == 'pi_created_1_secret'
    assert len(provider.created) == 1
    assert provider.created[0].id == 'pi_created_1'
    assert provider.created_pm_types == [['card']]
    result = await db_session.execute(select(Payment).where(Payment.payment_id == response.payment_id))
    payment = result.scalar_one()
    assert payment.provider_payment_id == 'pi_created_1'
    assert payment.status == 'requires_action'
    assert payment.amount == Decimal('100.00')

async def test_create_intent_booking_not_found(db_session, booking_fixture) -> None:
    provider = FakeStripeClient()
    svc = PaymentService(db_session, provider)
    with pytest.raises(NotFoundError):
        await svc.create_intent(booking_id=uuid4(), user_id=booking_fixture['user_id'])
    assert provider.created == []

async def test_create_intent_wrong_owner(db_session, booking_fixture) -> None:
    provider = FakeStripeClient()
    svc = PaymentService(db_session, provider)
    other = User(email=f'other_{uuid4().hex[:8]}@test.com', password_hash='x', is_active=True)
    db_session.add(other)
    await db_session.flush()
    with pytest.raises(NotFoundError):
        await svc.create_intent(booking_id=booking_fixture['booking_id'], user_id=other.user_id)
    assert provider.created == []

async def test_create_intent_expiring_booking(db_session, booking_fixture) -> None:
    provider = FakeStripeClient()
    svc = PaymentService(db_session, provider)
    await db_session.execute(update(Booking).where(Booking.booking_id == booking_fixture['booking_id']).values(expires_at=datetime.now(UTC) + timedelta(minutes=1)))
    with pytest.raises(BookingConflictError):
        await svc.create_intent(booking_id=booking_fixture['booking_id'], user_id=booking_fixture['user_id'])
    assert provider.created == []

async def test_create_intent_reuses_existing_intent(db_session, booking_fixture) -> None:
    existing_payment_id = await _create_payment(db_session, booking_fixture['booking_id'], 'pi_existing')
    provider = FakeStripeClient()
    svc = PaymentService(db_session, provider)
    response = await svc.create_intent(booking_id=booking_fixture['booking_id'], user_id=booking_fixture['user_id'])
    assert response.payment_id == existing_payment_id
    assert response.client_secret == 'pi_existing_secret'
    assert [r.id for r in provider.retrieved] == ['pi_existing']
    assert provider.created == []

async def test_create_intent_provider_failure(db_session, booking_fixture) -> None:
    provider = FakeStripeClient()
    provider.create_error = PaymentProviderError('Stripe error: card_declined')
    svc = PaymentService(db_session, provider)
    with pytest.raises(PaymentProviderError):
        await svc.create_intent(booking_id=booking_fixture['booking_id'], user_id=booking_fixture['user_id'])
    result = await db_session.execute(select(Payment))
    payment = result.scalars().one()
    assert payment.status == 'failed'
    assert payment.provider_payment_id is None
    assert provider.cancelled == []

async def test_sync_payment_succeeded(db_session, booking_fixture) -> None:
    payment_id = await _create_payment(db_session, booking_fixture['booking_id'], 'pi_ok')
    provider = FakeStripeClient(intent_status='succeeded')
    svc = PaymentService(db_session, provider)
    response = await svc.sync_payment(payment_id=payment_id, user_id=booking_fixture['user_id'])
    assert response.payment_status == 'succeeded'
    assert response.booking_status == BookingStatus.CONFIRMED.value
    payment = (await db_session.execute(select(Payment).where(Payment.payment_id == payment_id))).scalar_one()
    assert payment.status == 'succeeded'
    booking = (await db_session.execute(select(Booking).where(Booking.booking_id == booking_fixture['booking_id']))).scalar_one()
    assert booking.status == BookingStatus.CONFIRMED
    seats = (await db_session.execute(select(Seat).where(Seat.show_id == booking_fixture['show_id']))).scalars().all()
    assert {s.seat_id for s in seats} == set(booking_fixture['seat_ids'])
    assert all(s.status == SeatStatus.SOLD for s in seats)
    outbox = (await db_session.execute(select(OutboxEvent).where(OutboxEvent.aggregate_id == booking_fixture['booking_id']))).scalars().all()
    assert {e.event_type for e in outbox} == {'BOOKING_CONFIRMED'}
    assert len(outbox) == len(booking_fixture['seat_ids'])

async def test_sync_payment_pending(db_session, booking_fixture) -> None:
    payment_id = await _create_payment(db_session, booking_fixture['booking_id'], 'pi_waiting')
    provider = FakeStripeClient(intent_status='requires_payment_method')
    svc = PaymentService(db_session, provider)
    response = await svc.sync_payment(payment_id=payment_id, user_id=booking_fixture['user_id'])
    assert response.payment_status == 'requires_payment_method'
    assert response.booking_status == BookingStatus.PENDING.value
    payment = (await db_session.execute(select(Payment).where(Payment.payment_id == payment_id))).scalar_one()
    assert payment.status == 'requires_action'
    booking = (await db_session.execute(select(Booking).where(Booking.booking_id == booking_fixture['booking_id']))).scalar_one()
    assert booking.status == BookingStatus.PENDING
    seats = (await db_session.execute(select(Seat).where(Seat.show_id == booking_fixture['show_id']))).scalars().all()
    assert all(s.status == SeatStatus.PENDING_PAYMENT for s in seats)

async def test_sync_payment_not_found(db_session, booking_fixture) -> None:
    svc = PaymentService(db_session, FakeStripeClient())
    with pytest.raises(NotFoundError):
        await svc.sync_payment(payment_id=uuid4(), user_id=booking_fixture['user_id'])

async def test_sync_payment_wrong_owner(db_session, booking_fixture) -> None:
    payment_id = await _create_payment(db_session, booking_fixture['booking_id'], 'pi_mine')
    provider = FakeStripeClient(intent_status='succeeded')
    svc = PaymentService(db_session, provider)
    other = User(email=f'other_{uuid4().hex[:8]}@test.com', password_hash='x', is_active=True)
    db_session.add(other)
    await db_session.flush()
    with pytest.raises(NotFoundError):
        await svc.sync_payment(payment_id=payment_id, user_id=other.user_id)
