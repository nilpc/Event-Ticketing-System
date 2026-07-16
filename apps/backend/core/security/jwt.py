"""FR-3: RS256 JWT creation and validation with jti claims."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from jose import jwt

from core.config import settings

_private_key: str | None = None
_public_key: str | None = None


def _get_private_key() -> str:
    global _private_key  # noqa: PLW0603
    if _private_key is None:
        with open(settings.JWT_PRIVATE_KEY_PATH) as f:
            _private_key = f.read()
    return _private_key


def _get_public_key() -> str:
    global _public_key  # noqa: PLW0603
    if _public_key is None:
        with open(settings.JWT_PUBLIC_KEY_PATH) as f:
            _public_key = f.read()
    return _public_key


def create_access_token(user_id: str, extra_claims: dict | None = None) -> str:
    """FR-3: Issue a short-lived RS256 JWT with jti claim."""
    now = datetime.now(UTC)
    claims = {
        "sub": user_id,
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()),
        "type": "access",
    }
    if extra_claims:
        claims.update(extra_claims)
    return jwt.encode(claims, _get_private_key(), algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """FR-3: Validate and decode an access token. Raises JWTError on failure."""
    return jwt.decode(token, _get_public_key(), algorithms=[settings.JWT_ALGORITHM])
