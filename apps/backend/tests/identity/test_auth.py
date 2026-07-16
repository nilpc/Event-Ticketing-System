"""FR-1: Identity service unit tests."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_signup_returns_201(client: AsyncClient) -> None:
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    r = await client.post(
        "/v1/auth/signup",
        json={"email": email, "password": "Str0ng!Pass#2024"},
    )
    assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
    body = r.json()
    assert "user_id" in body


@pytest.mark.asyncio
async def test_signup_duplicate_returns_409(client: AsyncClient) -> None:
    email = f"dup_{uuid.uuid4().hex[:8]}@example.com"
    payload = {"email": email, "password": "Str0ng!Pass#2024"}
    r1 = await client.post("/v1/auth/signup", json=payload)
    assert r1.status_code == 201, f"First signup should be 201, got {r1.status_code}: {r1.text}"
    r = await client.post("/v1/auth/signup", json=payload)
    assert r.status_code == 409


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
