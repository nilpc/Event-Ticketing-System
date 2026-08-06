from __future__ import annotations

import uuid
from types import SimpleNamespace


class FakeStripeClient:
    def __init__(self, intent_status: str = "requires_action") -> None:
        self.intent_status = intent_status
        self.created: list = []
        self.retrieved: list = []
        self.cancelled: list[str] = []
        self.create_error: Exception | None = None
        self.created_pm_types: list[list[str] | None] = []

    def make_intent(self, intent_id: str) -> SimpleNamespace:
        return SimpleNamespace(
            id=intent_id, client_secret=f"{intent_id}_secret", status=self.intent_status
        )

    async def create_payment_intent(
        self,
        amount_cents: int,
        currency: str,
        metadata: dict | None = None,
        payment_method_types: list[str] | None = None,
    ) -> SimpleNamespace:
        if self.create_error is not None:
            raise self.create_error
        intent = self.make_intent(f"pi_created_{len(self.created) + 1}")
        self.created.append(intent)
        self.created_pm_types.append(payment_method_types)
        return intent

    async def retrieve_payment_intent(self, intent_id: str) -> SimpleNamespace:
        intent = self.make_intent(intent_id)
        self.retrieved.append(intent)
        return intent

    async def cancel_payment_intent(self, intent_id: str) -> None:
        self.cancelled.append(intent_id)


class FakeWebhookProvider:
    def __init__(self, event: object, error: Exception | None = None) -> None:
        self.event = event
        self.error = error

    def construct_webhook_event(self, payload: bytes, sig_header: str) -> object:
        if self.error is not None:
            raise self.error
        return self.event


def make_stripe_event(
    event_type: str, metadata: dict, event_id: str | None = None, intent_id: str = "pi_test_123"
) -> SimpleNamespace:
    return SimpleNamespace(
        id=event_id or f"evt_{uuid.uuid4().hex}",
        type=event_type,
        data=SimpleNamespace(object=SimpleNamespace(id=intent_id, metadata=metadata)),
    )
