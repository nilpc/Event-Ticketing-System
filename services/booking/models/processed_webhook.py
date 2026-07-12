"""FR-9: booking.processed_webhook_events ORM model."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base


class ProcessedWebhookEvent(Base):
    """booking.processed_webhook_events — idempotency guard for Stripe webhooks."""

    __tablename__ = "processed_webhook_events"
    __table_args__ = {"schema": "booking"}

    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
