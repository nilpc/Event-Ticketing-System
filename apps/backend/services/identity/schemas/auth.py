from __future__ import annotations
from uuid import UUID
from pydantic import BaseModel, EmailStr

class SignupRequest(BaseModel):
    email: EmailStr
    password: str

class SignupResponse(BaseModel):
    user_id: UUID
    email: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = 'bearer'
    is_admin: bool = False
    is_master_admin: bool = False

class RefreshRequest(BaseModel):
    refresh_token: str

class ErrorResponse(BaseModel):
    detail: str
