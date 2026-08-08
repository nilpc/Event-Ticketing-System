from __future__ import annotations

import asyncio
from typing import Any, Protocol
from uuid import uuid4

import stripe
import structlog

from core.config import settings
from core.exceptions import PaymentProviderError

logger = structlog.get_logger()

class PaymentIntentProvider(Protocol):

    async def create_payment_intent(self, amount_cents: int, currency: str, metadata: dict | None=None, payment_method_types: list[str] | None=None) -> Any:
        ...

    async def retrieve_payment_intent(self, intent_id: str) -> Any:
        ...

    async def cancel_payment_intent(self, intent_id: str) -> None:
        ...

class WebhookEventProvider(Protocol):

    def construct_webhook_event(self, payload: bytes, sig_header: str) -> Any:
        ...

class StripeClient:

    def __init__(self) -> None:
        stripe.api_key = settings.STRIPE_SECRET_KEY

    async def create_payment_intent(self, amount_cents: int, currency: str, metadata: dict | None=None, payment_method_types: list[str] | None=None) -> stripe.PaymentIntent:
        if not settings.STRIPE_SECRET_KEY or settings.STRIPE_SECRET_KEY.startswith('sk_test_mock'):
            mock_id = f"pi_mock_{uuid4().hex[:12]}"
            intent_dict = {
                "id": mock_id,
                "client_secret": f"{mock_id}_secret",
                "status": "requires_payment_method",
                "amount": amount_cents,
                "currency": currency,
            }
            logger.info('mock_stripe_intent_created', intent_id=mock_id, amount=amount_cents, currency=currency)
            return stripe.PaymentIntent.construct_from(intent_dict, key=None)
        try:
            intent = await asyncio.to_thread(stripe.PaymentIntent.create, amount=amount_cents, currency=currency, metadata=metadata or {}, payment_method_types=payment_method_types or ['card'])
            logger.info('stripe_intent_created', intent_id=intent.id, amount=amount_cents, currency=currency)
            return intent
        except stripe.StripeError as exc:
            logger.error('stripe_intent_creation_failed', error=str(exc))
            raise PaymentProviderError(f'Stripe error: {exc.user_message or str(exc)}') from exc

    async def cancel_payment_intent(self, intent_id: str) -> None:
        if intent_id.startswith('pi_mock_'):
            logger.info('mock_stripe_intent_cancelled', intent_id=intent_id)
            return
        try:
            await asyncio.to_thread(stripe.PaymentIntent.cancel, intent_id)
            logger.info('stripe_intent_cancelled', intent_id=intent_id)
        except stripe.StripeError as exc:
            logger.error('stripe_intent_cancel_failed', intent_id=intent_id, error=str(exc))
            err_msg = exc.user_message or str(exc)
            raise PaymentProviderError(f'Stripe cancel error: {err_msg}') from exc

    async def retrieve_payment_intent(self, intent_id: str) -> stripe.PaymentIntent:
        if intent_id.startswith('pi_mock_'):
            return stripe.PaymentIntent.construct_from({
                "id": intent_id,
                "client_secret": f"{intent_id}_secret",
                "status": "succeeded",
                "amount": 1000,
                "currency": "inr",
            }, key=None)
        try:
            intent = await asyncio.to_thread(stripe.PaymentIntent.retrieve, intent_id)
            return intent
        except stripe.StripeError as exc:
            logger.error('stripe_intent_retrieve_failed', intent_id=intent_id, error=str(exc))
            err_msg = exc.user_message or str(exc)
            raise PaymentProviderError(f'Stripe retrieve error: {err_msg}') from exc

    def construct_webhook_event(self, payload: bytes, sig_header: str) -> stripe.Event:
        if not settings.STRIPE_WEBHOOK_SECRET:
            raise ValueError('STRIPE_WEBHOOK_SECRET is not configured. Set it in your environment or .env file.')
        return stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)

