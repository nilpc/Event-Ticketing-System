"""FR-3: Database-backed rotating refresh tokens with reuse detection."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings

# NOTE: RefreshToken model lives in services/identity/models (correct CSR location),
# but core.security.refresh needs it for DB operations. This creates a
# core→services dependency. Acceptable trade-off for Phase 2; refactor in Phase 3
# by moving token DB ops into the identity service layer.
from services.identity.models.user import RefreshToken


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def create_refresh_token(
    user_id: UUID,
    session: AsyncSession,
    *,
    rotated_from: UUID | None = None,
) -> tuple[str, UUID]:
    """FR-3: Create a DB-backed refresh token. Returns (raw_token, token_id)."""
    raw_token = secrets.token_urlsafe(64)
    token_hash = _hash_token(raw_token)
    token_id = uuid.uuid4()
    expires_at = datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    rt = RefreshToken(
        token_id=token_id,
        user_id=user_id,
        token_hash=token_hash,
        rotated_from=rotated_from,
        expires_at=expires_at,
    )
    session.add(rt)
    await session.flush()
    return raw_token, token_id


async def rotate_refresh_token(
    old_token_id: UUID,
    user_id: UUID,
    session: AsyncSession,
) -> tuple[str, UUID]:
    """FR-3: Rotate with strict reuse detection.

    Looks up the old token by ID, verifies it hasn't been tampered with
    or reused, then creates a new token linked to it.
    """
    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token_id == old_token_id)
    )
    old_token = result.scalar_one_or_none()

    if old_token is None:
        raise ValueError("Refresh token not found — family invalidated.")

    if old_token.is_revoked:
        await _revoke_family_by_id(old_token_id, session)
        # FR-3: Commit revocations immediately so rollback in get_db_session
        # doesn't undo the security-relevant family invalidation.
        await session.commit()
        raise ValueError("Refresh token reuse detected — family invalidated.")

    old_token.is_revoked = True
    await session.flush()

    return await create_refresh_token(user_id, session, rotated_from=old_token_id)


async def revoke_refresh_token(token_id: UUID, session: AsyncSession) -> None:
    """FR-3: Revoke a single refresh token."""
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.token_id == token_id, RefreshToken.is_revoked.is_(False))
        .values(is_revoked=True)
    )


async def _revoke_family_by_id(token_id: UUID, session: AsyncSession) -> None:
    """FR-3: Walk the rotated_from chain and revoke all tokens in the family.

    Revokes both backward (ancestors via rotated_from) and forward
    (all descendants via recursive BFS) to fully invalidate a stolen
    token chain.
    """
    # Backward: revoke this token and all ancestors
    revoked_ids: set[UUID] = set()
    current_id: UUID | None = token_id
    while current_id is not None:
        result = await session.execute(
            select(RefreshToken).where(RefreshToken.token_id == current_id)
        )
        token = result.scalar_one_or_none()
        if token is None:
            break
        token.is_revoked = True
        revoked_ids.add(current_id)
        current_id = token.rotated_from

    # Forward: iteratively find ALL descendants (including through
    # already-revoked intermediaries) and revoke any still-active ones.
    frontier = list(revoked_ids)
    while frontier:
        result = await session.execute(
            select(RefreshToken.token_id, RefreshToken.is_revoked)
            .where(RefreshToken.rotated_from.in_(frontier))
        )
        children = [(row[0], row[1]) for row in result.all()]
        if not children:
            break
        # Revoke any children that aren't revoked yet
        to_revoke = [cid for cid, revoked in children if not revoked]
        if to_revoke:
            await session.execute(
                update(RefreshToken)
                .where(RefreshToken.token_id.in_(to_revoke))
                .values(is_revoked=True)
            )
        # Continue traversal through ALL children (even already-revoked)
        all_children = [cid for cid, _ in children]
        revoked_ids.update(all_children)
        frontier = all_children

    await session.flush()
