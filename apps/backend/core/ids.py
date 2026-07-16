"""ID generation for prefixed entity identifiers.

Events use STE prefix (e.g. STE01, STE02).
Movies use STM prefix (e.g. STM01, STM02).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import EventType

# PostgreSQL sequences for auto-incrementing serial numbers
_EVENT_SEQ = "booking.event_serial_seq"
_MOVIE_SEQ = "booking.movie_serial_seq"


def _prefix_for_type(event_type: EventType) -> str:
    """Return the ID prefix for an event type."""
    return "STM" if event_type == EventType.MOVIE else "STE"


def format_event_id(event_type: EventType, serial: int) -> str:
    """Format a prefixed ID: STE01, STM02, etc."""
    prefix = _prefix_for_type(event_type)
    return f"{prefix}{serial:02d}"


async def generate_event_id(
    session: AsyncSession, event_type: EventType
) -> str:
    """Generate the next prefixed ID using a PostgreSQL sequence.

    Sequences are created in the migration and guarantee uniqueness
    even under concurrent inserts.
    """
    seq_name = _MOVIE_SEQ if event_type == EventType.MOVIE else _EVENT_SEQ
    result = await session.execute(text(f"SELECT nextval('{seq_name}')"))
    serial = result.scalar_one()
    return format_event_id(event_type, int(serial))


def parse_event_id_prefix(event_id: str) -> tuple[EventType | None, int | None]:
    """Parse an event ID into (event_type, serial_number).

    Returns (None, None) if the ID doesn't match the expected format.
    """
    if len(event_id) < 5:
        return None, None
    prefix = event_id[:3]
    serial_str = event_id[3:]
    try:
        serial = int(serial_str)
    except ValueError:
        return None, None
    if prefix == "STE":
        return EventType.EVENT, serial
    if prefix == "STM":
        return EventType.MOVIE, serial
    return None, None
