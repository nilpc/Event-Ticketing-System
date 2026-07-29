"""FR-3: RS256 JWT creation and validation with jti and kid claims."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from jose import jwt

from core.config import settings

_KID = "rsa-2048-1"
_private_key: str | None = None
_public_key: str | None = None


def _load_key(path: str, env_var: str) -> str | None:
    """Try env var first, then file path. Returns None if neither exists."""
    if env_var:
        return env_var
    try:
        with open(path) as f:
            return f.read()
    except (FileNotFoundError, OSError):
        return None


def _get_private_key() -> str:
    global _private_key  # noqa: PLW0603
    if _private_key is None:
        val = _load_key(settings.JWT_PRIVATE_KEY_PATH, settings.JWT_PRIVATE_KEY)
        if val is None:
            msg = "No JWT private key found — set JWT_PRIVATE_KEY env var or provide certs/private.pem"
            raise RuntimeError(msg)
        _private_key = val
    return _private_key


def _get_public_key() -> str:
    global _public_key  # noqa: PLW0603
    if _public_key is None:
        val = _load_key(settings.JWT_PUBLIC_KEY_PATH, settings.JWT_PUBLIC_KEY)
        if val is None:
            msg = "No JWT public key found — set JWT_PUBLIC_KEY env var or provide certs/public.pem"
            raise RuntimeError(msg)
        _public_key = val
    return _public_key


def create_access_token(user_id: str, extra_claims: dict | None = None) -> str:
    """FR-3: Issue a short-lived RS256 JWT with jti and kid claims."""
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
    headers = {"kid": _KID}
    return jwt.encode(claims, _get_private_key(), algorithm=settings.JWT_ALGORITHM, headers=headers)


def decode_access_token(token: str) -> dict:
    """FR-3: Validate and decode an access token. Raises JWTError on failure."""
    return jwt.decode(token, _get_public_key(), algorithms=[settings.JWT_ALGORITHM])
