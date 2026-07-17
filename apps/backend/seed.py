"""Seed script — populate catalog with 10 events for manual testing."""
import asyncio
import hashlib
import os
from typing import TypedDict
from uuid import uuid4

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

load_dotenv()


ADMIN_EMAIL = "admin@event-ticketing.dev"
ADMIN_PASSWORD = "Admin123!"


def _hash_password(password: str) -> str:
    """Hash password using the same algorithm as auth_service.

    Tries bcrypt first (production dependency), falls back to PBKDF2.
    """
    try:
        import bcrypt
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    except ImportError:
        salt = b"event-ticketing-fallback-salt"
        return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations=600_000).hex()


def _next_event_id(event_type: str, counter: dict[str, int]) -> str:
    """Generate a prefixed event ID (STE01/STM01) using an in-memory counter.

    The seed script is idempotent: it clears all rows before inserting,
    so in-memory counters reset each run.  The DB sequences are bumped
    but that's harmless for seed data.
    """
    counter[event_type] = counter.get(event_type, 0) + 1
    prefix = "STM" if event_type == "MOVIE" else "STE"
    return f"{prefix}{counter[event_type]:02d}"

VENUES: list[tuple[str, int]] = [
    ("Madison Square Garden", 20789),
    ("The O2 Arena", 20000),
    ("Red Rocks Amphitheatre", 9525),
    ("Hollywood Bowl", 17500),
    ("Sydney Opera House", 2679),
    ("Wembley Stadium", 90000),
    ("Ryman Auditorium", 2362),
    ("Bridgestone Arena", 19395),
]


class _EventDef(TypedDict):
    name: str
    description: str
    event_type: str
    venue_idx: int
    base_price: float
    hours_from_now: int
    duration_hours: int


EVENTS: list[_EventDef] = [
    {
        "name": "Dune: Part Three — World Premiere",
        "description": (
            "The epic conclusion to Denis Villeneuve's sci-fi saga. "
            "Red carpet premiere with cast Q&A."
        ),
        "event_type": "MOVIE",
        "venue_idx": 0,
        "base_price": 120.00,
        "hours_from_now": 24,
        "duration_hours": 3,
    },
    {
        "name": "Interstellar: 10th Anniversary Screening",
        "description": (
            "Christopher Nolan's masterpiece returns to the big screen "
            "in IMAX with a live orchestral score."
        ),
        "event_type": "MOVIE",
        "venue_idx": 1,
        "base_price": 85.00,
        "hours_from_now": 48,
        "duration_hours": 3,
    },
    {
        "name": "Beyoncé — Renaissance World Tour",
        "description": (
            "The global superstar performs her chart-topping hits "
            "live in a spectacular production."
        ),
        "event_type": "EVENT",
        "venue_idx": 5,
        "base_price": 150.00,
        "hours_from_now": 72,
        "duration_hours": 3,
    },
    {
        "name": "NBA Finals — Game 5",
        "description": (
            "The championship showdown. "
            "Can the underdogs force a Game 6?"
        ),
        "event_type": "EVENT",
        "venue_idx": 7,
        "base_price": 95.00,
        "hours_from_now": 36,
        "duration_hours": 3,
    },
    {
        "name": "Coldplay — Music of the Spheres Tour",
        "description": (
            "An immersive, sustainable concert experience with "
            "stunning visuals and fan-favorite anthems."
        ),
        "event_type": "EVENT",
        "venue_idx": 3,
        "base_price": 110.00,
        "hours_from_now": 96,
        "duration_hours": 3,
    },
    {
        "name": "The Beatles Tribute — Let It Be",
        "description": (
            "A multi-award-winning West End show recreating "
            "the magic of The Beatles' final years."
        ),
        "event_type": "EVENT",
        "venue_idx": 6,
        "base_price": 65.00,
        "hours_from_now": 12,
        "duration_hours": 2,
    },
    {
        "name": "Marvel Studios: Avengers Secret Wars Premiere",
        "description": (
            "The biggest crossover event in cinema history. "
            "First screening with surprise guest appearances."
        ),
        "event_type": "MOVIE",
        "venue_idx": 0,
        "base_price": 130.00,
        "hours_from_now": 168,
        "duration_hours": 3,
    },
    {
        "name": "Formula 1 — Monaco Grand Prix Viewing Party",
        "description": (
            "Watch the world's most prestigious race on the big "
            "screen with live commentary and food trucks."
        ),
        "event_type": "EVENT",
        "venue_idx": 2,
        "base_price": 45.00,
        "hours_from_now": 60,
        "duration_hours": 5,
    },
    {
        "name": "Hamilton — Broadway Revival",
        "description": (
            "Lin-Manuel Miranda's revolutionary musical "
            "returns with a star-studded new cast."
        ),
        "event_type": "EVENT",
        "venue_idx": 4,
        "base_price": 175.00,
        "hours_from_now": 120,
        "duration_hours": 3,
    },
    {
        "name": "Stand-Up Comedy Night — Dave Chappelle",
        "description": (
            "An evening of sharp, unfiltered comedy from "
            "one of the greatest of all time."
        ),
        "event_type": "EVENT",
        "venue_idx": 1,
        "base_price": 90.00,
        "hours_from_now": 10,
        "duration_hours": 2,
    },
]

SEATS = [
    ("A1", "vip", 150.00),
    ("A2", "vip", 150.00),
    ("A3", "vip", 150.00),
    ("B1", "premium", 100.00),
    ("B2", "premium", 100.00),
    ("B3", "premium", 100.00),
    ("C1", "standard", 75.00),
    ("C2", "standard", 75.00),
    ("C3", "standard", 75.00),
    ("D1", "standard", 75.00),
    ("D2", "standard", 75.00),
    ("D3", "standard", 75.00),
]


async def seed(reset: bool = False):
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set")
    engine = create_async_engine(db_url)
    factory = async_sessionmaker(engine, class_=AsyncSession)

    async with factory() as session:
        async with session.begin():
            existing = await session.execute(
                text("SELECT user_id FROM identity.users WHERE email = :email"),
                {"email": ADMIN_EMAIL},
            )
            admin_id = existing.scalar_one_or_none()
            if admin_id is None:
                admin_id = uuid4()
                await session.execute(
                    text(
                        "INSERT INTO identity.users"
                        " (user_id, email, password_hash, is_active, is_admin)"
                        " VALUES (:uid, :email, :pw, true, true)"
                    ),
                    {"uid": admin_id, "email": ADMIN_EMAIL,
                     "pw": _hash_password(ADMIN_PASSWORD)},
                )

            venue_count_result = await session.execute(text("SELECT COUNT(*) FROM booking.venues"))
            venue_count: int = venue_count_result.scalar() or 0

            if venue_count > 0 and not reset:
                print("Seed data already exists — skipping.")
                return

            if venue_count > 0 and reset:
                print("Resetting catalog data...")
                await session.execute(text("DELETE FROM booking.booking_events"))
                await session.execute(text("DELETE FROM booking.booking_seats"))
                await session.execute(text("DELETE FROM booking.bookings"))
                await session.execute(text("DELETE FROM booking.seats"))
                await session.execute(text("DELETE FROM booking.showtimes"))
                await session.execute(text("DELETE FROM booking.events"))
                await session.execute(text("DELETE FROM booking.venues"))
                await session.execute(text(
                    "ALTER SEQUENCE booking.event_serial_seq RESTART WITH 1"
                ))
                await session.execute(text(
                    "ALTER SEQUENCE booking.movie_serial_seq RESTART WITH 1"
                ))

            venue_ids = []
            for name, capacity in VENUES:
                vid = uuid4()
                venue_ids.append(vid)
                await session.execute(text(
                    "INSERT INTO booking.venues (venue_id, name, capacity) "
                    "VALUES (:vid, :name, :cap)"
                ), {"vid": vid, "name": name, "cap": capacity})

            event_ids = []
            show_ids = []
            id_counters: dict[str, int] = {}
            for ev in EVENTS:
                eid = _next_event_id(ev["event_type"], id_counters)
                event_ids.append(eid)
                await session.execute(text(
                    "INSERT INTO booking.events "
                    "(event_id, event_type, name, description) "
                    "VALUES (:eid, :etype, :name, :desc)"
                ), {
                    "eid": eid,
                    "etype": ev["event_type"],
                    "name": ev["name"],
                    "desc": ev["description"],
                })

                vid = venue_ids[ev["venue_idx"]]
                sid = uuid4()
                show_ids.append(sid)
                await session.execute(text(
                    "INSERT INTO booking.showtimes "
                    "(show_id, event_id, venue_id, base_price, start_time, end_time) "
                    "VALUES (:sid, :eid, :vid, :price, "
                    "NOW() + :hours * INTERVAL '1 hour', "
                    "NOW() + (:hours + :dur) * INTERVAL '1 hour')"
                ), {
                    "sid": sid, "eid": eid, "vid": vid,
                    "price": ev["base_price"],
                    "hours": ev["hours_from_now"],
                    "dur": ev["duration_hours"],
                })

            for sid in show_ids:
                for seat_id, tier, price in SEATS:
                    await session.execute(text(
                        "INSERT INTO booking.seats (show_id, seat_id, tier, price, status) "
                        "VALUES (:sid, :seat_id, :tier, :price, 'AVAILABLE')"
                    ), {"sid": sid, "seat_id": seat_id, "tier": tier, "price": price})

            event_count = sum(1 for e in EVENTS if e["event_type"] == "EVENT")
            movie_count = sum(1 for e in EVENTS if e["event_type"] == "MOVIE")
            if event_count > 0:
                await session.execute(
                    text("SELECT setval('booking.event_serial_seq', :n)"),
                    {"n": event_count},
                )
            if movie_count > 0:
                await session.execute(
                    text("SELECT setval('booking.movie_serial_seq', :n)"),
                    {"n": movie_count},
                )

    await engine.dispose()

    print("=" * 60)
    print("SEED COMPLETE — 10 events created")
    print("=" * 60)
    print(f"  Admin user: {ADMIN_EMAIL}")
    print(f"  Admin pass: {ADMIN_PASSWORD}")
    print("=" * 60)
    for i, ev in enumerate(EVENTS):
        print(f"  {i + 1}. [{ev['event_type']}] {ev['name']}")
        print(f"     venue:    {VENUES[ev['venue_idx']][0]}")
        print(f"     event_id: {event_ids[i]}")
        print(f"     show_id:  {show_ids[i]}")
        print(f"     price:    ${ev['base_price']:.2f}")
    print("=" * 60)


if __name__ == "__main__":
    import sys
    reset_mode = "--reset" in sys.argv
    asyncio.run(seed(reset=reset_mode))
