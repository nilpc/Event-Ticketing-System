"""FR-1, FR-3: Pydantic schemas for auth endpoints."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, EmailStr


class SignupRequest(BaseModel):
    """FR-1: email + password signup."""

    email: EmailStr
    password: str


class SignupResponse(BaseModel):
    user_id: UUID
    email: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """FR-3: JWT access + refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    is_admin: bool = False


class RefreshRequest(BaseModel):
    """FR-3: Refresh token rotation request."""

    refresh_token: str


class ErrorResponse(BaseModel):
    detail: str
