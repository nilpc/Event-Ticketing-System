"""FR-4/FR-6/FR-7/FR-8: End-to-end booking flow integration test.

Verifies the full lifecycle:
1. Admin creates venue, event, showtime (auto-generated seats)
2. Regular user joins queue → gets admitted → locks seats → books tickets
3. Booking appears in user's booking list
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import update


async def _make_admin(client: AsyncClient, email: str, password: str) -> str:
    """Sign up a user, promote to admin via DB, login, return access token."""
    from core.db.session import async_session_factory
    from services.identity.models.user import User

    r = await client.post("/v1/auth/signup", json={"email": email, "password": password})
    assert r.status_code == 201, f"Signup failed: {r.text}"
    user_id = r.json()["user_id"]

    async with async_session_factory() as session:
        await session.execute(
            update(User)
            .where(User.user_id == UUID(user_id))
            .values(is_admin=True)
        )
        await session.commit()

    r = await client.post("/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()["access_token"]


async def _admit_user(show_id: str, user_id: str) -> str:
    """Manually admit a user from the queue (replaces the background admitter worker).

    Returns the generated queue token.
    """
    from core.db.session import async_session_factory
    from core.redis import get_redis
    from services.booking.repositories.lock_repo import LockRepository

    async with async_session_factory() as session:
        lock_repo = LockRepository(session, redis_client=get_redis())
        return await lock_repo.admit_user(UUID(show_id), UUID(user_id))


async def test_full_booking_flow(client: AsyncClient) -> None:
    """End-to-end: admin creates catalog → user joins queue → locks → books → verify."""
    PASSWORD = "Str0ng!Pass#2024"

    # ── 1. Admin creates catalog ────────────────────────────────────────
    admin_email = f"admin_{uuid.uuid4().hex[:8]}@test.com"
    admin_token = await _make_admin(client, admin_email, PASSWORD)
    admin_h = {"Authorization": f"Bearer {admin_token}"}

    # Create venue (capacity=10 → auto_seats generates VIP/Premium/Standard)
    r = await client.post(
        "/v1/admin/venues",
        json={"name": "Integration Test Arena", "capacity": 10},
        headers=admin_h,
    )
    assert r.status_code == 201, f"Create venue failed: {r.text}"
    venue_id = r.json()["venue_id"]

    # Create event
    r = await client.post(
        "/v1/admin/events",
        json={"event_type": "EVENT", "name": "Integration Test Concert"},
        headers=admin_h,
    )
    assert r.status_code == 201, f"Create event failed: {r.text}"
    event_id = r.json()["event_id"]

    # Create showtime with auto-generated seats
    start = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    end = (datetime.now(UTC) + timedelta(hours=4)).isoformat()
    r = await client.post(
        "/v1/admin/showtimes",
        json={
            "event_id": event_id,
            "venue_id": venue_id,
            "base_price": 75.00,
            "start_time": start,
            "end_time": end,
            "auto_seats": True,
        },
        headers=admin_h,
    )
    assert r.status_code == 201, f"Create showtime failed: {r.text}"
    show_id = r.json()["show_id"]

    # Get seat map — verify auto-seats were created
    r = await client.get(f"/v1/showtimes/{show_id}/seats")
    assert r.status_code == 200, f"Get seats failed: {r.text}"
    seat_map = r.json()
    seats = seat_map["seats"]
    assert len(seats) > 0, "No seats were auto-generated"
    available_seats = [s for s in seats if s["status"] == "AVAILABLE"]
    assert len(available_seats) >= 2, "Need at least 2 available seats"
    seat_ids = [available_seats[0]["seat_id"], available_seats[1]["seat_id"]]

    # ── 2. Regular user joins queue and gets admitted ───────────────────
    user_email = f"fan_{uuid.uuid4().hex[:8]}@test.com"
    r = await client.post(
        "/v1/auth/signup", json={"email": user_email, "password": PASSWORD}
    )
    assert r.status_code == 201
    user_id = r.json()["user_id"]

    r = await client.post(
        "/v1/auth/login", json={"email": user_email, "password": PASSWORD}
    )
    assert r.status_code == 200
    user_token = r.json()["access_token"]
    user_h = {"Authorization": f"Bearer {user_token}"}

    # Join queue
    r = await client.post(
        "/v1/queue/join", json={"show_id": show_id}, headers=user_h
    )
    assert r.status_code == 200, f"Queue join failed: {r.text}"
    join_resp = r.json()
    assert join_resp["status"] in ("waiting", "admitted")

    # Manually admit the user (background admitter is not running in tests)
    queue_token = await _admit_user(show_id, user_id)

    # Verify admission via queue status
    r = await client.get(
        f"/v1/queue/status?show_id={show_id}", headers=user_h
    )
    assert r.status_code == 200
    status_resp = r.json()
    assert status_resp["status"] == "admitted", f"Not admitted: {status_resp}"
    assert status_resp["queue_token"] == queue_token

    # ── 3. Lock seats ───────────────────────────────────────────────────
    r = await client.post(
        "/v1/seats/lock",
        json={"show_id": show_id, "seat_ids": seat_ids},
        headers=user_h,
    )
    assert r.status_code == 200, f"Lock seats failed: {r.text}"
    lock_resp = r.json()
    idempotency_key = lock_resp["idempotency_key"]
    assert set(lock_resp["locked_seat_ids"]) == set(seat_ids)

    # ── 4. Book seats ───────────────────────────────────────────────────
    r = await client.post(
        "/v1/book",
        json={
            "show_id": show_id,
            "seat_ids": seat_ids,
            "idempotency_key": idempotency_key,
        },
        headers={**user_h, "X-Queue-Token": queue_token},
    )
    assert r.status_code == 200, f"Book failed: {r.status_code} {r.text}"
    book_resp = r.json()
    assert "booking_id" in book_resp
    assert book_resp["status"] == "PENDING"

    # ── 5. Verify booking appears in user's list ────────────────────────
    r = await client.get("/v1/bookings", headers=user_h)
    assert r.status_code == 200
    bookings = r.json()
    booking_ids = [b["booking_id"] for b in bookings]
    assert str(book_resp["booking_id"]) in booking_ids, (
        f"Booking {book_resp['booking_id']} not found in {booking_ids}"
    )

    # ── 6. Verify seat statuses are updated ─────────────────────────────
    r = await client.get(f"/v1/showtimes/{show_id}/seats")
    assert r.status_code == 200
    updated_seats = r.json()["seats"]
    for s in updated_seats:
        if s["seat_id"] in seat_ids:
            assert s["status"] == "PENDING_PAYMENT", (
                f"Seat {s['seat_id']} should be PENDING_PAYMENT, got {s['status']}"
            )
        else:
            assert s["status"] == "AVAILABLE", (
                f"Seat {s['seat_id']} should be AVAILABLE, got {s['status']}"
            )
