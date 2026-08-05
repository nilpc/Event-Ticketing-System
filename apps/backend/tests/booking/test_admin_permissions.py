"""FR-4: Admin/merchant permission enforcement tests.

Verifies:
1. Merchants can only mutate events they created (created_by) — others' events 403.
2. Events with no owner (created_by is NULL) are master-admin only.
3. Venue update/delete is master-admin only.
4. Showtime create is open to any merchant (any catalog event); update/delete
   is gated by the owning event's owner.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import update

PASSWORD = "Str0ng!Pass#2024"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _make_user(
    client: AsyncClient, email: str, *, is_admin: bool = False, is_master_admin: bool = False
) -> str:
    """Sign up a user, set role flags via DB, login, return access token."""
    from core.db.session import async_session_factory
    from services.identity.models.user import User

    r = await client.post("/v1/auth/signup", json={"email": email, "password": PASSWORD})
    assert r.status_code == 201, f"Signup failed: {r.text}"
    user_id = UUID(r.json()["user_id"])

    if is_admin or is_master_admin:
        async with async_session_factory() as session:
            await session.execute(
                update(User)
                .where(User.user_id == user_id)
                .values(is_admin=is_admin or is_master_admin, is_master_admin=is_master_admin)
            )
            await session.commit()

    r = await client.post("/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()["access_token"]


async def _create_event(client: AsyncClient, token: str, name: str) -> str:
    r = await client.post(
        "/v1/admin/events",
        json={"event_type": "EVENT", "name": name},
        headers=_auth(token),
    )
    assert r.status_code == 201, f"Create event failed: {r.status_code} {r.text}"
    return r.json()["event_id"]


async def _create_unowned_event(name: str) -> str:
    """Insert an event with created_by = NULL (as the seed script does)."""
    from core.db.session import async_session_factory
    from core.enums import EventType
    from services.booking.schemas.admin import EventCreate
    from services.booking.services.admin_service import AdminService

    async with async_session_factory() as session:
        svc = AdminService(session)
        event = await svc.create_event(
            EventCreate(event_type=EventType.EVENT, name=name), created_by=None
        )
        await session.commit()
        return event.event_id


async def _create_venue(
    client: AsyncClient, token: str, name: str = "Permission Test Arena"
) -> str:
    r = await client.post(
        "/v1/admin/venues",
        json={"name": name, "capacity": 10},
        headers=_auth(token),
    )
    assert r.status_code == 201, f"Create venue failed: {r.status_code} {r.text}"
    return r.json()["venue_id"]


def _showtime_payload(event_id: str, venue_id: str, price: float = 50.0) -> dict:
    start = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    end = (datetime.now(UTC) + timedelta(hours=4)).isoformat()
    return {
        "event_id": event_id,
        "venue_id": venue_id,
        "base_price": price,
        "start_time": start,
        "end_time": end,
        "auto_seats": False,
    }


async def _create_showtime(client: AsyncClient, token: str, payload: dict) -> str:
    r = await client.post("/v1/admin/showtimes", json=payload, headers=_auth(token))
    assert r.status_code == 201, f"Create showtime failed: {r.status_code} {r.text}"
    return r.json()["show_id"]


# ── Events ──────────────────────────────────────────────────────────────


async def test_merchant_cannot_modify_others_event(client: AsyncClient) -> None:
    token_a = await _make_user(client, f"a_{uuid.uuid4().hex[:8]}@test.com", is_admin=True)
    token_b = await _make_user(client, f"b_{uuid.uuid4().hex[:8]}@test.com", is_admin=True)

    event_id = await _create_event(client, token_a, "A's Concert")

    r = await client.put(
        f"/v1/admin/events/{event_id}",
        json={"name": "Hijacked"},
        headers=_auth(token_b),
    )
    assert r.status_code == 403, (
        f"Expected 403 updating others' event, got {r.status_code}: {r.text}"
    )

    r = await client.delete(f"/v1/admin/events/{event_id}", headers=_auth(token_b))
    assert r.status_code == 403, (
        f"Expected 403 deleting others' event, got {r.status_code}: {r.text}"
    )

    # Owner can still mutate their own event
    r = await client.put(
        f"/v1/admin/events/{event_id}",
        json={"name": "A's Concert v2"},
        headers=_auth(token_a),
    )
    assert r.status_code == 200, f"Owner update failed: {r.status_code} {r.text}"
    assert r.json()["name"] == "A's Concert v2"
    assert r.json()["created_by"] is not None


async def test_merchant_cannot_modify_unowned_event(client: AsyncClient) -> None:
    token = await _make_user(client, f"m_{uuid.uuid4().hex[:8]}@test.com", is_admin=True)
    event_id = await _create_unowned_event(f"Seeded {uuid.uuid4().hex[:4]}")

    r = await client.put(
        f"/v1/admin/events/{event_id}",
        json={"name": "Tampered"},
        headers=_auth(token),
    )
    assert r.status_code == 403, f"Expected 403 for unowned event, got {r.status_code}: {r.text}"

    r = await client.delete(f"/v1/admin/events/{event_id}", headers=_auth(token))
    assert r.status_code == 403, (
        f"Expected 403 delete for unowned event, got {r.status_code}: {r.text}"
    )


async def test_master_admin_can_modify_any_event(client: AsyncClient) -> None:
    master = await _make_user(client, f"root_{uuid.uuid4().hex[:8]}@test.com", is_master_admin=True)
    merchant = await _make_user(client, f"m2_{uuid.uuid4().hex[:8]}@test.com", is_admin=True)

    event_id = await _create_event(client, merchant, "Merchant's Event")
    r = await client.put(
        f"/v1/admin/events/{event_id}",
        json={"name": "Master Renamed"},
        headers=_auth(master),
    )
    assert r.status_code == 200, f"Master update failed: {r.status_code} {r.text}"

    r = await client.delete(f"/v1/admin/events/{event_id}", headers=_auth(master))
    assert r.status_code == 204, f"Master delete failed: {r.status_code} {r.text}"

    unowned = await _create_unowned_event(f"Seeded {uuid.uuid4().hex[:4]}")
    r = await client.put(
        f"/v1/admin/events/{unowned}",
        json={"name": "Master Fixes Seed"},
        headers=_auth(master),
    )
    assert r.status_code == 200, f"Master update of unowned event failed: {r.status_code} {r.text}"


async def test_admin_events_list_exposes_created_by(client: AsyncClient) -> None:
    from core.db.session import async_session_factory
    from services.identity.models.user import User

    email = f"list_{uuid.uuid4().hex[:8]}@test.com"
    r = await client.post("/v1/auth/signup", json={"email": email, "password": PASSWORD})
    assert r.status_code == 201
    user_id = UUID(r.json()["user_id"])

    async with async_session_factory() as session:
        await session.execute(update(User).where(User.user_id == user_id).values(is_admin=True))
        await session.commit()

    r = await client.post("/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200
    token = r.json()["access_token"]

    event_id = await _create_event(client, token, "Listed Event")

    r = await client.get("/v1/admin/events", headers=_auth(token))
    assert r.status_code == 200, f"Admin events list failed: {r.status_code} {r.text}"
    events = r.json()
    mine = [e for e in events if e["event_id"] == event_id]
    assert len(mine) == 1
    assert mine[0]["created_by"] == str(user_id)


async def test_public_catalog_does_not_expose_created_by(client: AsyncClient) -> None:
    token = await _make_user(client, f"pub_{uuid.uuid4().hex[:8]}@test.com", is_admin=True)
    await _create_event(client, token, "Public Event")

    r = await client.get("/v1/events")
    assert r.status_code == 200, f"Public events failed: {r.status_code} {r.text}"
    events = r.json()
    assert len(events) > 0
    assert "created_by" not in events[0], "Public catalog must not leak event owner UUIDs"


# ── Venues ──────────────────────────────────────────────────────────────


async def test_merchant_cannot_update_or_delete_venue(client: AsyncClient) -> None:
    master = await _make_user(client, f"root_{uuid.uuid4().hex[:8]}@test.com", is_master_admin=True)
    merchant = await _make_user(client, f"v_{uuid.uuid4().hex[:8]}@test.com", is_admin=True)

    venue_id = await _create_venue(client, master)

    r = await client.put(
        f"/v1/admin/venues/{venue_id}",
        json={"capacity": 500},
        headers=_auth(merchant),
    )
    assert r.status_code == 403, f"Expected 403 venue update, got {r.status_code}: {r.text}"

    r = await client.delete(f"/v1/admin/venues/{venue_id}", headers=_auth(merchant))
    assert r.status_code == 403, f"Expected 403 venue delete, got {r.status_code}: {r.text}"

    # Master admin can update + delete
    r = await client.put(
        f"/v1/admin/venues/{venue_id}",
        json={"capacity": 500},
        headers=_auth(master),
    )
    assert r.status_code == 200, f"Master venue update failed: {r.status_code} {r.text}"
    assert r.json()["capacity"] == 500

    r = await client.delete(f"/v1/admin/venues/{venue_id}", headers=_auth(master))
    assert r.status_code == 204, f"Master venue delete failed: {r.status_code} {r.text}"


async def test_merchant_can_still_create_venue(client: AsyncClient) -> None:
    merchant = await _make_user(client, f"vc_{uuid.uuid4().hex[:8]}@test.com", is_admin=True)
    r = await client.post(
        "/v1/admin/venues",
        json={"name": "Merchant Created", "capacity": 25},
        headers=_auth(merchant),
    )
    assert r.status_code == 201, f"Merchant venue create failed: {r.status_code} {r.text}"


# ── Showtimes ───────────────────────────────────────────────────────────


async def test_merchant_can_create_showtime_for_any_event(client: AsyncClient) -> None:
    token_a = await _make_user(client, f"sa_{uuid.uuid4().hex[:8]}@test.com", is_admin=True)
    token_b = await _make_user(client, f"sb_{uuid.uuid4().hex[:8]}@test.com", is_admin=True)

    event_id = await _create_event(client, token_a, "A's Film")
    venue_id = await _create_venue(client, token_b)

    # Any merchant can schedule a showtime using any catalog event/venue
    r = await client.post(
        "/v1/admin/showtimes",
        json=_showtime_payload(event_id, venue_id),
        headers=_auth(token_b),
    )
    assert r.status_code == 201, (
        f"Expected 201 cross-owner showtime create, got {r.status_code}: {r.text}"
    )

    # Owner can create showtime for own event
    r = await client.post(
        "/v1/admin/showtimes",
        json=_showtime_payload(event_id, venue_id),
        headers=_auth(token_a),
    )
    assert r.status_code == 201, f"Owner showtime create failed: {r.status_code} {r.text}"


async def test_merchant_cannot_modify_showtime_for_others_event(client: AsyncClient) -> None:
    token_a = await _make_user(client, f"ua_{uuid.uuid4().hex[:8]}@test.com", is_admin=True)
    token_b = await _make_user(client, f"ub_{uuid.uuid4().hex[:8]}@test.com", is_admin=True)

    event_id = await _create_event(client, token_a, "A's Theatre")
    venue_id = await _create_venue(client, token_a)
    show_id = await _create_showtime(client, token_a, _showtime_payload(event_id, venue_id))

    r = await client.put(
        f"/v1/admin/showtimes/{show_id}",
        json={"base_price": 99.00},
        headers=_auth(token_b),
    )
    assert r.status_code == 403, f"Expected 403 showtime update, got {r.status_code}: {r.text}"

    r = await client.delete(f"/v1/admin/showtimes/{show_id}", headers=_auth(token_b))
    assert r.status_code == 403, f"Expected 403 showtime delete, got {r.status_code}: {r.text}"


async def test_merchant_cannot_modify_showtime_for_unowned_event(client: AsyncClient) -> None:
    master = await _make_user(client, f"root_{uuid.uuid4().hex[:8]}@test.com", is_master_admin=True)
    merchant = await _make_user(client, f"sz_{uuid.uuid4().hex[:8]}@test.com", is_admin=True)

    event_id = await _create_unowned_event(f"Seeded {uuid.uuid4().hex[:4]}")
    venue_id = await _create_venue(client, master)
    show_id = await _create_showtime(client, master, _showtime_payload(event_id, venue_id))

    r = await client.put(
        f"/v1/admin/showtimes/{show_id}",
        json={"base_price": 42.00},
        headers=_auth(merchant),
    )
    assert r.status_code == 403, (
        f"Expected 403 for unowned event showtime, got {r.status_code}: {r.text}"
    )

    r = await client.delete(f"/v1/admin/showtimes/{show_id}", headers=_auth(merchant))
    assert r.status_code == 403, (
        f"Expected 403 delete unowned showtime, got {r.status_code}: {r.text}"
    )


async def test_large_venue_auto_seats_generates_all_rows(client: AsyncClient) -> None:
    """NFR-x: auto-generating seats for a large venue must stay bounded.

    Regression: bulk seat generation for big venues used to materialize
    every Seat ORM object in one list, OOM'ing the API pod (256Mi limit).
    """
    token = await _make_user(client, f"big_{uuid.uuid4().hex[:8]}@test.com", is_admin=True)
    event_id = await _create_event(client, token, "Big Venue Event")

    r = await client.post(
        "/v1/admin/venues",
        json={"name": "Big Seat Arena", "capacity": 5000},
        headers=_auth(token),
    )
    assert r.status_code == 201, f"Create big venue failed: {r.status_code} {r.text}"
    venue_id = r.json()["venue_id"]

    payload = _showtime_payload(event_id, venue_id)
    payload["auto_seats"] = True
    r = await client.post("/v1/admin/showtimes", json=payload, headers=_auth(token))
    assert r.status_code == 201, f"Showtime create failed: {r.status_code} {r.text}"
    show_id = r.json()["show_id"]

    r = await client.get(f"/v1/showtimes/{show_id}/seats")
    assert r.status_code == 200, f"Seat map fetch failed: {r.status_code} {r.text}"
    seats = r.json()["seats"]
    assert len(seats) == 5000, f"Expected 5000 auto seats, got {len(seats)}"
