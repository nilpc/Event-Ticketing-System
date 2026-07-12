"""FR-2: Pydantic schemas for OAuth endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class GoogleCallbackParams(BaseModel):
    """FR-2: Query params from Google redirect."""

    code: str
    state: str


class OAuthAuthorizeResponse(BaseModel):
    authorize_url: str
    state: str
