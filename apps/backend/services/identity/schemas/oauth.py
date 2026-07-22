"""FR-2: Pydantic schemas for OAuth endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class OAuthAuthorizeResponse(BaseModel):
    authorize_url: str
    state: str
