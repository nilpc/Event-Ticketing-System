from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, Request


def get_current_user_id(request: Request) -> UUID:
    raw = getattr(request.state, "user_id", None)
    if not raw:
        raise HTTPException(status_code=401, detail="Authentication required.")
    try:
        return UUID(raw)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid user identity.")
