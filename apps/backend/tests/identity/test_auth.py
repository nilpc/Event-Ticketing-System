"""FR-1: Identity service tests — signup, login, JWT auth, and error cases."""

from __future__ import annotations

import uuid

from httpx import AsyncClient


async def test_signup_returns_201(client: AsyncClient) -> None:
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    r = await client.post(
        "/v1/auth/signup",
        json={"email": email, "password": "Str0ng!Pass#2024"},
    )
    assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
    body = r.json()
    assert "user_id" in body


async def test_signup_duplicate_returns_409(client: AsyncClient) -> None:
    email = f"dup_{uuid.uuid4().hex[:8]}@example.com"
    payload = {"email": email, "password": "Str0ng!Pass#2024"}
    r1 = await client.post("/v1/auth/signup", json=payload)
    assert r1.status_code == 201, f"First signup should be 201, got {r1.status_code}: {r1.text}"
    r = await client.post("/v1/auth/signup", json=payload)
    assert r.status_code == 409


async def test_signup_weak_password_returns_422(client: AsyncClient) -> None:
    email = f"weak_{uuid.uuid4().hex[:8]}@example.com"
    r = await client.post("/v1/auth/signup", json={"email": email, "password": "123"})
    assert r.status_code == 422, f"Expected 422 for weak password, got {r.status_code}: {r.text}"


async def test_signup_missing_fields_returns_422(client: AsyncClient) -> None:
    r = await client.post("/v1/auth/signup", json={})
    assert r.status_code == 422


async def test_signup_invalid_email_returns_422(client: AsyncClient) -> None:
    r = await client.post(
        "/v1/auth/signup",
        json={"email": "not-an-email", "password": "Str0ng!Pass#2024"},
    )
    assert r.status_code == 422


async def test_login_returns_token(client: AsyncClient) -> None:
    email = f"login_{uuid.uuid4().hex[:8]}@example.com"
    pw = "Str0ng!Pass#2024"
    r_signup = await client.post("/v1/auth/signup", json={"email": email, "password": pw})
    assert r_signup.status_code == 201
    r = await client.post("/v1/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert len(body["access_token"]) > 20


async def test_login_wrong_password_returns_401(client: AsyncClient) -> None:
    email = f"wrongpw_{uuid.uuid4().hex[:8]}@example.com"
    pw = "Str0ng!Pass#2024"
    await client.post("/v1/auth/signup", json={"email": email, "password": pw})
    r = await client.post("/v1/auth/login", json={"email": email, "password": "WrongPassword!1"})
    assert r.status_code == 401


async def test_login_nonexistent_user_returns_401(client: AsyncClient) -> None:
    r = await client.post(
        "/v1/auth/login",
        json={"email": f"nope_{uuid.uuid4().hex[:8]}@example.com", "password": "Str0ng!Pass#2024"},
    )
    assert r.status_code == 401


async def test_login_missing_fields_returns_422(client: AsyncClient) -> None:
    r = await client.post("/v1/auth/login", json={})
    assert r.status_code == 422


async def test_protected_endpoint_requires_jwt(client: AsyncClient) -> None:
    r = await client.get("/v1/bookings")
    assert r.status_code == 401, f"Expected 401 without token, got {r.status_code}"


async def test_protected_endpoint_accepts_valid_jwt(client: AsyncClient) -> None:
    email = f"jwt_{uuid.uuid4().hex[:8]}@example.com"
    pw = "Str0ng!Pass#2024"
    await client.post("/v1/auth/signup", json={"email": email, "password": pw})
    login_resp = await client.post("/v1/auth/login", json={"email": email, "password": pw})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    r = await client.get(
        "/v1/bookings",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, f"Expected 200 with valid JWT, got {r.status_code}: {r.text}"


async def test_protected_endpoint_rejects_invalid_jwt(client: AsyncClient) -> None:
    r = await client.get(
        "/v1/bookings",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert r.status_code == 401


async def test_health(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
