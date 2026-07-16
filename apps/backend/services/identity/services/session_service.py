"""FR-3: SessionService — token pair issuance, rotation, logout."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import NotFoundError
from core.security.jwt import create_access_token
from core.security.refresh import (
    create_refresh_token,
    revoke_refresh_token,
    rotate_refresh_token,
)
from services.identity.repositories.user_repo import UserRepository
from services.identity.schemas.auth import LoginResponse

logger = structlog.get_logger()


class SessionService:
    """FR-3: JWT access + rotating refresh token management."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)

    async def issue_token_pair(self, user_id: UUID) -> LoginResponse:
        """FR-3: Issue access + refresh token pair."""
        raw_refresh, _ = await create_refresh_token(user_id, self.session)
        access_token = create_access_token(str(user_id))
        return LoginResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
        )

    async def refresh_access_token(self, refresh_token_raw: str) -> LoginResponse:
        """FR-3: Rotate refresh token with reuse detection."""
        token_hash = hashlib.sha256(refresh_token_raw.encode()).hexdigest()

        row = await self.user_repo.find_refresh_token_with_user(token_hash)

        if row is None:
            raise NotFoundError("Refresh token not found.")

        stored, user = row

        # FR-3: Reject expired refresh tokens immediately
        if stored.expires_at < datetime.now(UTC):
            raise NotFoundError("Refresh token has expired.")

        # C4: Reject tokens for soft-deleted or deactivated users
        if not user.is_active or user.deleted_at is not None:
            logger.warning(
                "refresh_token_used_by_inactive_user",
                user_id=str(user.user_id),
                is_active=user.is_active,
                deleted=user.deleted_at is not None,
            )
            raise NotFoundError("Refresh token not found.")

        new_raw, _ = await rotate_refresh_token(
            old_token_id=stored.token_id,
            user_id=stored.user_id,
            session=self.session,
        )

        access_token = create_access_token(str(stored.user_id))
        return LoginResponse(
            access_token=access_token,
            refresh_token=new_raw,
        )

    async def logout(self, refresh_token_raw: str) -> None:
        """FR-3: Revoke a refresh token."""
        token_hash = hashlib.sha256(refresh_token_raw.encode()).hexdigest()
        stored = await self.user_repo.find_refresh_token_by_hash(token_hash)
        if stored is not None:
            await revoke_refresh_token(stored.token_id, self.session)
