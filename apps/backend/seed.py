import asyncio
import hashlib
import os
import secrets
from typing import TypedDict
from uuid import uuid4

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

load_dotenv()
MASTER_ADMIN_EMAIL = 'admin@event-ticketing.dev'
MERCHANT_ADMIN_EMAIL = 'merchant@event-ticketing.dev'
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD') or secrets.token_urlsafe(24)

def _hash_password(password: str) -> str:
    try:
        import bcrypt
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    except ImportError:
        salt = b'event-ticketing-fallback-salt'
        return hashlib.pbkdf2_hmac('sha256', password.encode(), salt, iterations=600000).hex()

def _next_event_id(event_type: str, counter: dict[str, int]) -> str:
    counter[event_type] = counter.get(event_type, 0) + 1
    prefix = 'STM' if event_type == 'MOVIE' else 'STE'
    return f'{prefix}{counter[event_type]:02d}'
VENUES: list[tuple[str, int]] = [('Madison Square Garden', 1000), ('The O2 Arena', 1000), ('Red Rocks Amphitheatre', 1000), ('Hollywood Bowl', 1000), ('Sydney Opera House', 1000), ('Wembley Stadium', 1000), ('Ryman Auditorium', 1000), ('Bridgestone Arena', 1000)]

class _EventDef(TypedDict):
    name: str
    description: str
    event_type: str
    venue_idx: int
    front_price: float
    middle_price: float
    back_price: float
    hours_from_now: int
    duration_hours: int
EVENTS: list[_EventDef] = [{'name': 'Dune: Part Three — World Premiere', 'description': "The epic conclusion to Denis Villeneuve's sci-fi saga. Red carpet premiere with cast Q&A.", 'event_type': 'MOVIE', 'venue_idx': 0, 'front_price': 180.0, 'middle_price': 120.0, 'back_price': 90.0, 'hours_from_now': 24, 'duration_hours': 3}, {'name': 'Interstellar: 10th Anniversary Screening', 'description': "Christopher Nolan's masterpiece returns to the big screen in IMAX with a live orchestral score.", 'event_type': 'MOVIE', 'venue_idx': 1, 'front_price': 127.5, 'middle_price': 85.0, 'back_price': 63.8, 'hours_from_now': 48, 'duration_hours': 3}, {'name': 'Beyoncé — Renaissance World Tour', 'description': 'The global superstar performs her chart-topping hits live in a spectacular production.', 'event_type': 'EVENT', 'venue_idx': 5, 'front_price': 225.0, 'middle_price': 150.0, 'back_price': 112.5, 'hours_from_now': 72, 'duration_hours': 3}, {'name': 'NBA Finals — Game 5', 'description': 'The championship showdown. Can the underdogs force a Game 6?', 'event_type': 'EVENT', 'venue_idx': 7, 'front_price': 142.5, 'middle_price': 95.0, 'back_price': 71.2, 'hours_from_now': 36, 'duration_hours': 3}, {'name': 'Coldplay — Music of the Spheres Tour', 'description': 'An immersive, sustainable concert experience with stunning visuals and fan-favorite anthems.', 'event_type': 'EVENT', 'venue_idx': 3, 'front_price': 165.0, 'middle_price': 110.0, 'back_price': 82.5, 'hours_from_now': 96, 'duration_hours': 3}, {'name': 'The Beatles Tribute — Let It Be', 'description': "A multi-award-winning West End show recreating the magic of The Beatles' final years.", 'event_type': 'EVENT', 'venue_idx': 6, 'front_price': 97.5, 'middle_price': 65.0, 'back_price': 48.8, 'hours_from_now': 12, 'duration_hours': 2}, {'name': 'Marvel Studios: Avengers Secret Wars Premiere', 'description': 'The biggest crossover event in cinema history. First screening with surprise guest appearances.', 'event_type': 'MOVIE', 'venue_idx': 0, 'front_price': 195.0, 'middle_price': 130.0, 'back_price': 97.5, 'hours_from_now': 168, 'duration_hours': 3}, {'name': 'Formula 1 — Monaco Grand Prix Viewing Party', 'description': "Watch the world's most prestigious race on the big screen with live commentary and food trucks.", 'event_type': 'EVENT', 'venue_idx': 2, 'front_price': 67.5, 'middle_price': 45.0, 'back_price': 33.8, 'hours_from_now': 60, 'duration_hours': 5}, {'name': 'Hamilton — Broadway Revival', 'description': "Lin-Manuel Miranda's revolutionary musical returns with a star-studded new cast.", 'event_type': 'EVENT', 'venue_idx': 4, 'front_price': 262.5, 'middle_price': 175.0, 'back_price': 131.2, 'hours_from_now': 120, 'duration_hours': 3}, {'name': 'Stand-Up Comedy Night — Dave Chappelle', 'description': 'An evening of sharp, unfiltered comedy from one of the greatest of all time.', 'event_type': 'EVENT', 'venue_idx': 1, 'front_price': 135.0, 'middle_price': 90.0, 'back_price': 67.5, 'hours_from_now': 10, 'duration_hours': 2}]


async def seed(reset: bool=False):
    db_url = os.getenv('DATABASE_URL', '')
    if not db_url:
        raise RuntimeError('DATABASE_URL is not set')
    engine = create_async_engine(db_url)
    factory = async_sessionmaker(engine, class_=AsyncSession)
    async with factory() as session:
        async with session.begin():
            existing_master = await session.execute(text('SELECT user_id FROM identity.users WHERE email = :email'), {'email': MASTER_ADMIN_EMAIL})
            master_id = existing_master.scalar_one_or_none()
            if master_id is None:
                master_id = uuid4()
                if os.getenv('ADMIN_PASSWORD') is None:
                    print(f'[seed] No ADMIN_PASSWORD set — generated admin password: {ADMIN_PASSWORD}')
                await session.execute(text('INSERT INTO identity.users (user_id, email, password_hash, is_active, is_admin, is_master_admin) VALUES (:uid, :email, :pw, true, true, true)'), {'uid': master_id, 'email': MASTER_ADMIN_EMAIL, 'pw': _hash_password(ADMIN_PASSWORD)})
            else:
                await session.execute(text('UPDATE identity.users SET is_admin = true, is_master_admin = true WHERE user_id = :uid'), {'uid': master_id})
            existing_merchant = await session.execute(text('SELECT user_id FROM identity.users WHERE email = :email'), {'email': MERCHANT_ADMIN_EMAIL})
            merchant_id = existing_merchant.scalar_one_or_none()
            if merchant_id is None:
                merchant_id = uuid4()
                await session.execute(text('INSERT INTO identity.users (user_id, email, password_hash, is_active, is_admin, is_master_admin) VALUES (:uid, :email, :pw, true, true, false)'), {'uid': merchant_id, 'email': MERCHANT_ADMIN_EMAIL, 'pw': _hash_password(ADMIN_PASSWORD)})
            else:
                await session.execute(text('UPDATE identity.users SET is_admin = true, is_master_admin = false WHERE user_id = :uid'), {'uid': merchant_id})
            venue_count_result = await session.execute(text('SELECT COUNT(*) FROM booking.venues'))
            venue_count: int = venue_count_result.scalar() or 0
            if venue_count > 0 and (not reset):
                print('Seed data already exists — skipping.')
                return
            if venue_count > 0 and reset:
                print('Resetting catalog data...')
                await session.execute(text('DELETE FROM booking.booking_events'))
                await session.execute(text('DELETE FROM booking.booking_seats'))
                await session.execute(text('DELETE FROM booking.bookings'))
                await session.execute(text('DELETE FROM booking.seats'))
                await session.execute(text('DELETE FROM booking.showtimes'))
                await session.execute(text('DELETE FROM booking.events'))
                await session.execute(text('DELETE FROM booking.venues'))
                await session.execute(text('ALTER SEQUENCE booking.event_serial_seq RESTART WITH 1'))
                await session.execute(text('ALTER SEQUENCE booking.movie_serial_seq RESTART WITH 1'))
            venue_ids = []
            for name, capacity in VENUES:
                vid = uuid4()
                venue_ids.append(vid)
                await session.execute(text('INSERT INTO booking.venues (venue_id, name, capacity, created_by) VALUES (:vid, :name, :cap, :created_by)'), {'vid': vid, 'name': name, 'cap': capacity, 'created_by': None})
            event_ids = []
            show_ids = []
            id_counters: dict[str, int] = {}
            for ev in EVENTS:
                eid = _next_event_id(ev['event_type'], id_counters)
                event_ids.append(eid)
                await session.execute(text('INSERT INTO booking.events (event_id, event_type, name, description, created_by) VALUES (:eid, :etype, :name, :desc, :created_by)'), {'eid': eid, 'etype': ev['event_type'], 'name': ev['name'], 'desc': ev['description'], 'created_by': None})
                vid = venue_ids[ev['venue_idx']]
                sid = uuid4()
                show_ids.append((sid, ev['event_type']))
                await session.execute(text("INSERT INTO booking.showtimes (show_id, event_id, venue_id, front_price, middle_price, back_price, start_time, end_time) VALUES (:sid, :eid, :vid, :fp, :mp, :bp, NOW() + :hours * INTERVAL '1 hour', NOW() + (:hours + :dur) * INTERVAL '1 hour')"), {'sid': sid, 'eid': eid, 'vid': vid, 'fp': ev['front_price'], 'mp': ev['middle_price'], 'bp': ev['back_price'], 'hours': ev['hours_from_now'], 'dur': ev['duration_hours']})
            import random
            for sid, etype in show_ids:
                if etype == 'MOVIE':
                    num_seats = random.randint(50, 150)
                else:
                    num_seats = random.randint(500, 8000)
                seat_params = []
                vip_count = max(1, int(num_seats * 0.1))
                premium_count = max(1, int(num_seats * 0.3))
                standard_count = max(0, num_seats - vip_count - premium_count)
                tiers_info = [
                    ('vip', 150.0, 'SEC-1', vip_count),
                    ('premium', 100.0, 'SEC-2', premium_count),
                    ('standard', 75.0, 'SEC-3', standard_count),
                ]
                global_seat_idx = 0
                for tier_name, price, base_sec, count in tiers_info:
                    if count <= 0:
                        continue
                    num_subsections = (count + 99) // 100
                    for sub_i in range(num_subsections):
                        if num_subsections == 1:
                            sec_name = base_sec
                        else:
                            suffix = ""
                            n = sub_i
                            while True:
                                suffix = chr(ord('A') + (n % 26)) + suffix
                                n = n // 26 - 1
                                if n < 0:
                                    break
                            sec_name = f"{base_sec}{suffix}"

                        sub_count = min(100, count - sub_i * 100)
                        for j in range(sub_count):
                            global_seat_idx += 1
                            row = chr(ord('A') + ((global_seat_idx - 1) % 26))
                            seat_num = j + 1
                            seat_id = f"{sec_name}-{row}{seat_num}"
                            seat_params.append({'sid': sid, 'seat_id': seat_id, 'sec': sec_name, 'tier': tier_name, 'price': price})

                if seat_params:
                    # SQLAlchemy uses executemany under the hood for a list of dictionaries
                    await session.execute(
                        text("INSERT INTO booking.seats (show_id, seat_id, section, tier, price, status) VALUES (:sid, :seat_id, :sec, :tier, :price, 'AVAILABLE')"),
                        seat_params
                    )
            event_count = sum(1 for e in EVENTS if e['event_type'] == 'EVENT')
            movie_count = sum(1 for e in EVENTS if e['event_type'] == 'MOVIE')
            if event_count > 0:
                await session.execute(text("SELECT setval('booking.event_serial_seq', :n)"), {'n': event_count})
            if movie_count > 0:
                await session.execute(text("SELECT setval('booking.movie_serial_seq', :n)"), {'n': movie_count})
    await engine.dispose()
    print('=' * 60)
    print('SEED COMPLETE — 10 events created')
    print('=' * 60)
    print(f'  Master admin user: {MASTER_ADMIN_EMAIL}')
    print(f'  Master admin pass: {ADMIN_PASSWORD}')
    print('=' * 60)
    for i, ev in enumerate(EVENTS):
        print(f"  {i + 1}. [{ev['event_type']}] {ev['name']}")
        print(f"     venue:    {VENUES[ev['venue_idx']][0]}")
        print(f'     event_id: {event_ids[i]}')
        print(f'     show_id:  {show_ids[i][0]}')
        print(f"     front price: ${ev['front_price']:.2f}")
    print('=' * 60)
if __name__ == '__main__':
    import sys
    reset_mode = '--reset' in sys.argv
    asyncio.run(seed(reset=reset_mode))
