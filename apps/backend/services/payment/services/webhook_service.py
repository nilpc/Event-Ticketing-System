from __future__ import annotations

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import BookingStatus
from services.booking.repositories.booking_repo import BookingRepository
from services.booking.repositories.lock_repo import LockRepository
from services.booking.repositories.seat_repo import SeatRepository
from services.payment.providers.stripe_client import StripeClient, WebhookEventProvider
from services.payment.repositories.payment_repo import PaymentRepository

logger = structlog.get_logger()


class WebhookService:
    def __init__(
        self,
        session: AsyncSession,
        booking_repo: BookingRepository,
        seat_repo: SeatRepository,
        lock_repo: LockRepository,
        payment_repo: PaymentRepository | None = None,
    ) -> None:
        self.session = session
        self.booking_repo = booking_repo
        self.seat_repo = seat_repo
        self.lock_repo = lock_repo
        self.payment_repo = payment_repo or PaymentRepository(session)
        self.provider: WebhookEventProvider = StripeClient()

    def _parse_seat_ids(self, metadata: dict) -> list[str] | None:
        seat_ids_str = metadata.get("seat_ids")
        if seat_ids_str:
            parts = [s.strip() for s in seat_ids_str.split(",") if s.strip()]
            return parts if parts else None
        seat_id_val = metadata.get("seat_id")
        return [seat_id_val] if seat_id_val else None

    async def process_webhook(self, payload: bytes, signature: str) -> None:
        try:
            event = self.provider.construct_webhook_event(payload, signature)
        except Exception as exc:
            logger.warning("webhook_signature_invalid", error=str(exc))
            raise ValueError("Invalid webhook signature.") from exc
        show_id = user_id = None
        seat_ids: list[str] | None = None
        terminal = False
        try:
            async with self.session.begin_nested():
                try:
                    await self.booking_repo.log_webhook_event(
                        event.id, event.type, payload.decode()
                    )
                except IntegrityError:
                    return
                metadata = getattr(event.data.object, "metadata", {}) or {}
                if hasattr(metadata, "to_dict"):
                    metadata = metadata.to_dict()
                booking_id_str = metadata.get("booking_id")
                if not booking_id_str:
                    return
                from uuid import UUID

                try:
                    booking_id = UUID(booking_id_str)
                except (ValueError, TypeError):
                    return
                show_id_str = metadata.get("show_id")
                user_id_str = metadata.get("user_id")
                if show_id_str:
                    show_id = UUID(show_id_str)
                if user_id_str:
                    user_id = UUID(user_id_str)
                seat_ids = self._parse_seat_ids(metadata)
                booking = await self.booking_repo.get_booking_by_id(booking_id)
                if not booking:
                    return
                if event.type == "payment_intent.succeeded":
                    await self.payment_repo.update_payment_status_by_intent(
                        event.data.object.id, "succeeded"
                    )
                    if booking.status == BookingStatus.FAILED:
                        await self.booking_repo.add_outbox_event(
                            aggregate_type="Payment",
                            aggregate_id=booking_id,
                            event_type="REFUND_REQUIRED",
                            payload={
                                "reason": "Late webhook on failed booking",
                                "booking_id": str(booking_id),
                            },
                        )
                    elif booking.status == BookingStatus.PENDING:
                        if show_id is None or not seat_ids:
                            return
                        await self.seat_repo.finalize_sold_seats(show_id, seat_ids)
                        await self.booking_repo.update_booking_status(
                            booking_id, BookingStatus.CONFIRMED, source="webhook"
                        )
                        for seat_id in seat_ids:
                            await self.booking_repo.add_outbox_event(
                                aggregate_type="Booking",
                                aggregate_id=booking_id,
                                event_type="BOOKING_CONFIRMED",
                                payload={
                                    "booking_id": str(booking_id),
                                    "show_id": str(show_id),
                                    "seat_id": seat_id,
                                },
                            )
                        terminal = True
                elif event.type in ("payment_intent.payment_failed", "payment_intent.canceled"):
                    await self.payment_repo.update_payment_status_by_intent(
                        event.data.object.id, "failed"
                    )
                    if booking.status == BookingStatus.PENDING:
                        if show_id is None or not seat_ids:
                            return
                        for seat_id in seat_ids:
                            await self.seat_repo.revert_seat_to_available(show_id, seat_id)
                        await self.booking_repo.update_booking_status(
                            booking_id, BookingStatus.FAILED, source="webhook"
                        )
                        terminal = True
        except IntegrityError:
            return
        if terminal and show_id is not None and seat_ids and (user_id is not None):
            for seat_id in seat_ids:
                await self.lock_repo.release_seat_lock_safe(show_id, seat_id, user_id)
            await self.lock_repo.release_user_hold_limit(show_id, user_id)
