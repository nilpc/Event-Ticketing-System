"""FR-1: Identity service unit tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_signup_returns_201(client: AsyncClient) -> None:
    r = await client.post(
        "/v1/auth/signup",
        json={"email": "test@example.com", "password": "Str0ng!Pass#2024"},
    )
    assert r.status_code == 201
    body = r.json()
    assert "user_id" in body


@pytest.mark.asyncio
async def test_signup_duplicate_returns_409(client: AsyncClient) -> None:
    payload = {"email": "dup@example.com", "password": "Str0ng!Pass#2024"}
    await client.post("/v1/auth/signup", json=payload)
    r = await client.post("/v1/auth/signup", json=payload)
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_login_returns_token(client: AsyncClient) -> None:
    email = "login_test@example.com"
    pw = "Str0ng!Pass#2024"
    await client.post("/v1/auth/signup", json={"email": email, "password": pw})
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
