from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import EventType

_EVENT_SEQ = "booking.event_serial_seq"
_MOVIE_SEQ = "booking.movie_serial_seq"


def _prefix_for_type(event_type: EventType) -> str:
    return "STM" if event_type == EventType.MOVIE else "STE"


def format_event_id(event_type: EventType, serial: int) -> str:
    prefix = _prefix_for_type(event_type)
    return f"{prefix}{serial:02d}"


async def generate_event_id(session: AsyncSession, event_type: EventType) -> str:
    seq_name = _MOVIE_SEQ if event_type == EventType.MOVIE else _EVENT_SEQ
    result = await session.execute(text(f"SELECT nextval('{seq_name}')"))
    serial = result.scalar_one()
    return format_event_id(event_type, int(serial))
