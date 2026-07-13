"""FR-11: FastAPI dependency — extract trusted user_id from gateway middleware."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, Request


def get_current_user_id(request: Request) -> UUID:
    """FR-11: Return the trusted user_id injected by IdentityMiddleware.

    Raises 401 if the middleware has not set request.state.user_id
    (i.e. the request bypassed JWT enforcement or the token was invalid).
    """
    raw = getattr(request.state, "user_id", None)
    if not raw:
        raise HTTPException(
            status_code=401,
            detail="Authentication required.",
        )
    try:
        return UUID(raw)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=401,
            detail="Invalid user identity.",
        )
