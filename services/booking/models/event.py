"""NFR-6: booking.events ORM model."""

from sqlalchemy import Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base
from core.enums import EventType


class Event(Base):
    """booking.events — event catalog with STE/STM prefixed IDs."""

    __tablename__ = "events"
    __table_args__ = {"schema": "booking"}

    event_id: Mapped[str] = mapped_column(
        String(10), primary_key=True
    )
    event_type: Mapped[EventType] = mapped_column(
        Enum(EventType, name="event_type", create_type=False),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
