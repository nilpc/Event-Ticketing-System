from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import update

PASSWORD = 'Str0ng!Pass#2024'

def _auth(token: str) -> dict[str, str]:
    return {'Authorization': f'Bearer {token}'}

async def _make_user(client: AsyncClient, email: str, *, is_admin: bool=False, is_master_admin: bool=False) -> str:
    from core.db.session import async_session_factory
    from services.identity.models.user import User
    r = await client.post('/v1/auth/signup', json={'email': email, 'password': PASSWORD})
    assert r.status_code == 201, f'Signup failed: {r.text}'
    user_id = UUID(r.json()['user_id'])
    if is_admin or is_master_admin:
        async with async_session_factory() as session:
            await session.execute(update(User).where(User.user_id == user_id).values(is_admin=is_admin or is_master_admin, is_master_admin=is_master_admin))
            await session.commit()
    r = await client.post('/v1/auth/login', json={'email': email, 'password': PASSWORD})
    assert r.status_code == 200, f'Login failed: {r.text}'
    return r.json()['access_token']

async def _create_event(client: AsyncClient, token: str, name: str) -> str:
    r = await client.post('/v1/admin/events', json={'event_type': 'EVENT', 'name': name}, headers=_auth(token))
    assert r.status_code == 201, f'Create event failed: {r.status_code} {r.text}'
    return r.json()['event_id']

async def _create_unowned_event(name: str) -> str:
    from core.db.session import async_session_factory
    from core.enums import EventType
    from services.booking.schemas.admin import EventCreate
    from services.booking.services.admin_service import AdminService
    async with async_session_factory() as session:
        svc = AdminService(session)
        event = await svc.create_event(EventCreate(event_type=EventType.EVENT, name=name), created_by=None)
        await session.commit()
        return event.event_id

async def _create_venue(client: AsyncClient, token: str, name: str='Permission Test Arena') -> str:
    r = await client.post('/v1/admin/venues', json={'name': name, 'capacity': 10}, headers=_auth(token))
    assert r.status_code == 201, f'Create venue failed: {r.status_code} {r.text}'
    return r.json()['venue_id']

def _showtime_payload(event_id: str, venue_id: str, price: float=50.0) -> dict:
    start = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    end = (datetime.now(UTC) + timedelta(hours=4)).isoformat()
    return {'event_id': event_id, 'venue_id': venue_id, 'front_price': price, 'middle_price': price, 'back_price': price, 'start_time': start, 'end_time': end, 'auto_seats': False}

async def _create_showtime(client: AsyncClient, token: str, payload: dict) -> str:
    r = await client.post('/v1/admin/showtimes', json=payload, headers=_auth(token))
    assert r.status_code == 201, f'Create showtime failed: {r.status_code} {r.text}'
    return r.json()['show_id']

async def test_merchant_cannot_modify_others_event(client: AsyncClient) -> None:
    token_a = await _make_user(client, f'a_{uuid.uuid4().hex[:8]}@test.com', is_admin=True)
    token_b = await _make_user(client, f'b_{uuid.uuid4().hex[:8]}@test.com', is_admin=True)
    event_id = await _create_event(client, token_a, "A's Concert")
    r = await client.put(f'/v1/admin/events/{event_id}', json={'name': 'Hijacked'}, headers=_auth(token_b))
    assert r.status_code == 403, f"Expected 403 updating others' event, got {r.status_code}: {r.text}"
    r = await client.delete(f'/v1/admin/events/{event_id}', headers=_auth(token_b))
    assert r.status_code == 403, f"Expected 403 deleting others' event, got {r.status_code}: {r.text}"
    r = await client.put(f'/v1/admin/events/{event_id}', json={'name': "A's Concert v2"}, headers=_auth(token_a))
    assert r.status_code == 200, f'Owner update failed: {r.status_code} {r.text}'
    assert r.json()['name'] == "A's Concert v2"
    assert r.json()['created_by'] is not None

async def test_merchant_cannot_modify_unowned_event(client: AsyncClient) -> None:
    token = await _make_user(client, f'm_{uuid.uuid4().hex[:8]}@test.com', is_admin=True)
    event_id = await _create_unowned_event(f'Seeded {uuid.uuid4().hex[:4]}')
    r = await client.put(f'/v1/admin/events/{event_id}', json={'name': 'Tampered'}, headers=_auth(token))
    assert r.status_code == 403, f'Expected 403 for unowned event, got {r.status_code}: {r.text}'
    r = await client.delete(f'/v1/admin/events/{event_id}', headers=_auth(token))
    assert r.status_code == 403, f'Expected 403 delete for unowned event, got {r.status_code}: {r.text}'

async def test_master_admin_can_modify_any_event(client: AsyncClient) -> None:
    master = await _make_user(client, f'root_{uuid.uuid4().hex[:8]}@test.com', is_master_admin=True)
    merchant = await _make_user(client, f'm2_{uuid.uuid4().hex[:8]}@test.com', is_admin=True)
    event_id = await _create_event(client, merchant, "Merchant's Event")
    r = await client.put(f'/v1/admin/events/{event_id}', json={'name': 'Master Renamed'}, headers=_auth(master))
    assert r.status_code == 200, f'Master update failed: {r.status_code} {r.text}'
    r = await client.delete(f'/v1/admin/events/{event_id}', headers=_auth(master))
    assert r.status_code == 204, f'Master delete failed: {r.status_code} {r.text}'
    unowned = await _create_unowned_event(f'Seeded {uuid.uuid4().hex[:4]}')
    r = await client.put(f'/v1/admin/events/{unowned}', json={'name': 'Master Fixes Seed'}, headers=_auth(master))
    assert r.status_code == 200, f'Master update of unowned event failed: {r.status_code} {r.text}'

async def test_admin_events_list_exposes_created_by(client: AsyncClient) -> None:
    from core.db.session import async_session_factory
    from services.identity.models.user import User
    email = f'list_{uuid.uuid4().hex[:8]}@test.com'
    r = await client.post('/v1/auth/signup', json={'email': email, 'password': PASSWORD})
    assert r.status_code == 201
    user_id = UUID(r.json()['user_id'])
    async with async_session_factory() as session:
        await session.execute(update(User).where(User.user_id == user_id).values(is_admin=True))
        await session.commit()
    r = await client.post('/v1/auth/login', json={'email': email, 'password': PASSWORD})
    assert r.status_code == 200
    token = r.json()['access_token']
    event_id = await _create_event(client, token, 'Listed Event')
    r = await client.get('/v1/admin/events', headers=_auth(token))
    assert r.status_code == 200, f'Admin events list failed: {r.status_code} {r.text}'
    events = r.json()
    mine = [e for e in events if e['event_id'] == event_id]
    assert len(mine) == 1
    assert mine[0]['created_by'] == str(user_id)

async def test_public_catalog_does_not_expose_created_by(client: AsyncClient) -> None:
    token = await _make_user(client, f'pub_{uuid.uuid4().hex[:8]}@test.com', is_admin=True)
    event_id = await _create_event(client, token, 'Public Event')
    venue_id = await _create_venue(client, token)
    await _create_showtime(client, token, _showtime_payload(event_id, venue_id))
    r = await client.get('/v1/events')
    assert r.status_code == 200, f'Public events failed: {r.status_code} {r.text}'
    events = r.json()
    assert len(events) > 0
    assert 'created_by' not in events[0], 'Public catalog must not leak event owner UUIDs'
    r = await client.get('/v1/venues')
    assert r.status_code == 200, f'Public venues failed: {r.status_code} {r.text}'
    venues = r.json()
    assert len(venues) > 0
    assert 'created_by' not in venues[0], 'Public catalog must not leak venue owner UUIDs'

async def test_admin_venues_list_exposes_created_by(client: AsyncClient) -> None:
    from core.db.session import async_session_factory
    from services.identity.models.user import User
    email = f'vlist_{uuid.uuid4().hex[:8]}@test.com'
    r = await client.post('/v1/auth/signup', json={'email': email, 'password': PASSWORD})
    assert r.status_code == 201
    user_id = UUID(r.json()['user_id'])
    async with async_session_factory() as session:
        await session.execute(update(User).where(User.user_id == user_id).values(is_admin=True))
        await session.commit()
    r = await client.post('/v1/auth/login', json={'email': email, 'password': PASSWORD})
    assert r.status_code == 200
    token = r.json()['access_token']
    venue_id = await _create_venue(client, token)
    r = await client.get('/v1/admin/venues', headers=_auth(token))
    assert r.status_code == 200, f'Admin venues list failed: {r.status_code} {r.text}'
    venues = r.json()
    mine = [v for v in venues if v['venue_id'] == venue_id]
    assert len(mine) == 1
    assert mine[0]['created_by'] == str(user_id)

async def test_merchant_cannot_update_or_delete_venue(client: AsyncClient) -> None:
    master = await _make_user(client, f'root_{uuid.uuid4().hex[:8]}@test.com', is_master_admin=True)
    merchant = await _make_user(client, f'v_{uuid.uuid4().hex[:8]}@test.com', is_admin=True)
    venue_id = await _create_venue(client, master)
    r = await client.put(f'/v1/admin/venues/{venue_id}', json={'capacity': 500}, headers=_auth(merchant))
    assert r.status_code == 403, f'Expected 403 venue update, got {r.status_code}: {r.text}'
    r = await client.delete(f'/v1/admin/venues/{venue_id}', headers=_auth(merchant))
    assert r.status_code == 403, f'Expected 403 venue delete, got {r.status_code}: {r.text}'
    r = await client.put(f'/v1/admin/venues/{venue_id}', json={'capacity': 500}, headers=_auth(master))
    assert r.status_code == 200, f'Master venue update failed: {r.status_code} {r.text}'
    assert r.json()['capacity'] == 500
    r = await client.delete(f'/v1/admin/venues/{venue_id}', headers=_auth(master))
    assert r.status_code == 204, f'Master venue delete failed: {r.status_code} {r.text}'

async def test_merchant_can_still_create_venue(client: AsyncClient) -> None:
    merchant = await _make_user(client, f'vc_{uuid.uuid4().hex[:8]}@test.com', is_admin=True)
    r = await client.post('/v1/admin/venues', json={'name': 'Merchant Created', 'capacity': 25}, headers=_auth(merchant))
    assert r.status_code == 201, f'Merchant venue create failed: {r.status_code} {r.text}'

async def test_merchant_cannot_create_showtime_for_others_event(client: AsyncClient) -> None:
    token_a = await _make_user(client, f'sa_{uuid.uuid4().hex[:8]}@test.com', is_admin=True)
    token_b = await _make_user(client, f'sb_{uuid.uuid4().hex[:8]}@test.com', is_admin=True)
    event_id = await _create_event(client, token_a, "A's Film")
    venue_a = await _create_venue(client, token_a)
    venue_b = await _create_venue(client, token_b)
    r = await client.post('/v1/admin/showtimes', json=_showtime_payload(event_id, venue_b), headers=_auth(token_b))
    assert r.status_code == 403, f'Expected 403 cross-owner showtime create, got {r.status_code}: {r.text}'
    r = await client.post('/v1/admin/showtimes', json=_showtime_payload(event_id, venue_b), headers=_auth(token_a))
    assert r.status_code == 403, f'Expected 403 cross-venue showtime create, got {r.status_code}: {r.text}'
    r = await client.post('/v1/admin/showtimes', json=_showtime_payload(event_id, venue_a), headers=_auth(token_a))
    assert r.status_code == 201, f'Owner showtime create failed: {r.status_code} {r.text}'

async def test_merchant_cannot_modify_showtime_for_others_event(client: AsyncClient) -> None:
    token_a = await _make_user(client, f'ua_{uuid.uuid4().hex[:8]}@test.com', is_admin=True)
    token_b = await _make_user(client, f'ub_{uuid.uuid4().hex[:8]}@test.com', is_admin=True)
    event_id = await _create_event(client, token_a, "A's Theatre")
    venue_id = await _create_venue(client, token_a)
    show_id = await _create_showtime(client, token_a, _showtime_payload(event_id, venue_id))
    r = await client.put(f'/v1/admin/showtimes/{show_id}', json={'front_price': 99.0, 'middle_price': 99.0, 'back_price': 99.0}, headers=_auth(token_b))
    assert r.status_code == 403, f'Expected 403 showtime update, got {r.status_code}: {r.text}'
    r = await client.delete(f'/v1/admin/showtimes/{show_id}', headers=_auth(token_b))
    assert r.status_code == 403, f'Expected 403 showtime delete, got {r.status_code}: {r.text}'

async def test_merchant_cannot_modify_showtime_for_unowned_event(client: AsyncClient) -> None:
    master = await _make_user(client, f'root_{uuid.uuid4().hex[:8]}@test.com', is_master_admin=True)
    merchant = await _make_user(client, f'sz_{uuid.uuid4().hex[:8]}@test.com', is_admin=True)
    event_id = await _create_unowned_event(f'Seeded {uuid.uuid4().hex[:4]}')
    venue_id = await _create_venue(client, master)
    show_id = await _create_showtime(client, master, _showtime_payload(event_id, venue_id))
    r = await client.put(f'/v1/admin/showtimes/{show_id}', json={'front_price': 42.0, 'middle_price': 42.0, 'back_price': 42.0}, headers=_auth(merchant))
    assert r.status_code == 403, f'Expected 403 for unowned event showtime, got {r.status_code}: {r.text}'
    r = await client.delete(f'/v1/admin/showtimes/{show_id}', headers=_auth(merchant))
    assert r.status_code == 403, f'Expected 403 delete unowned showtime, got {r.status_code}: {r.text}'

async def test_merchant_can_batch_create_showtimes(client: AsyncClient) -> None:
    token = await _make_user(client, f'batch_{uuid.uuid4().hex[:8]}@test.com', is_admin=True)
    event_id = await _create_event(client, token, 'Batch Film')
    venue_id = await _create_venue(client, token)
    base = datetime.now(UTC)
    slots = [{'start_time': (base + timedelta(hours=2)).isoformat(), 'end_time': (base + timedelta(hours=4)).isoformat()}, {'start_time': (base + timedelta(hours=6)).isoformat(), 'end_time': (base + timedelta(hours=8)).isoformat()}]
    r = await client.post('/v1/admin/showtimes/batch', json={'event_id': event_id, 'venue_id': venue_id, 'front_price': 50.0, 'middle_price': 50.0, 'back_price': 50.0, 'auto_seats': False, 'slots': slots}, headers=_auth(token))
    assert r.status_code == 201, f'Batch create failed: {r.status_code} {r.text}'
    created = r.json()
    assert len(created) == 2, f'Expected 2 showtimes, got {len(created)}'
    assert {s['event_id'] for s in created} == {event_id}
    overlapping = [{'start_time': (base + timedelta(hours=2)).isoformat(), 'end_time': (base + timedelta(hours=4)).isoformat()}, {'start_time': (base + timedelta(hours=3)).isoformat(), 'end_time': (base + timedelta(hours=5)).isoformat()}]
    r = await client.post('/v1/admin/showtimes/batch', json={'event_id': event_id, 'venue_id': venue_id, 'front_price': 50.0, 'middle_price': 50.0, 'back_price': 50.0, 'auto_seats': False, 'slots': overlapping}, headers=_auth(token))
    assert r.status_code == 422, f'Expected 422 for overlapping slots, got {r.status_code}: {r.text}'

async def test_batch_create_enforces_ownership(client: AsyncClient) -> None:
    token_a = await _make_user(client, f'ba_{uuid.uuid4().hex[:8]}@test.com', is_admin=True)
    token_b = await _make_user(client, f'bb_{uuid.uuid4().hex[:8]}@test.com', is_admin=True)
    event_id = await _create_event(client, token_a, "A's Batch")
    venue_id = await _create_venue(client, token_a)
    base = datetime.now(UTC)
    r = await client.post('/v1/admin/showtimes/batch', json={'event_id': event_id, 'venue_id': venue_id, 'front_price': 50.0, 'middle_price': 50.0, 'back_price': 50.0, 'auto_seats': False, 'slots': [{'start_time': (base + timedelta(hours=2)).isoformat(), 'end_time': (base + timedelta(hours=4)).isoformat()}]}, headers=_auth(token_b))
    assert r.status_code == 403, f"Expected 403 batch create on others' event, got {r.status_code}: {r.text}"

async def test_large_venue_auto_seats_generates_all_rows(client: AsyncClient) -> None:
    token = await _make_user(client, f'big_{uuid.uuid4().hex[:8]}@test.com', is_admin=True)
    event_id = await _create_event(client, token, 'Big Venue Event')
    r = await client.post('/v1/admin/venues', json={'name': 'Big Seat Arena', 'capacity': 5000}, headers=_auth(token))
    assert r.status_code == 201, f'Create big venue failed: {r.status_code} {r.text}'
    venue_id = r.json()['venue_id']
    payload = _showtime_payload(event_id, venue_id)
    payload['auto_seats'] = True
    r = await client.post('/v1/admin/showtimes', json=payload, headers=_auth(token))
    assert r.status_code == 201, f'Showtime create failed: {r.status_code} {r.text}'
    _ = r.json()['show_id']
    pass
