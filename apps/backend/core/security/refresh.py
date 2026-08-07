from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from services.identity.models.user import RefreshToken


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

async def create_refresh_token(user_id: UUID, session: AsyncSession, *, rotated_from: UUID | None=None) -> tuple[str, UUID]:
    raw_token = secrets.token_urlsafe(64)
    token_hash = _hash_token(raw_token)
    token_id = uuid.uuid4()
    expires_at = datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    rt = RefreshToken(token_id=token_id, user_id=user_id, token_hash=token_hash, rotated_from=rotated_from, expires_at=expires_at)
    session.add(rt)
    await session.flush()
    return (raw_token, token_id)

async def rotate_refresh_token(old_token_id: UUID, user_id: UUID, session: AsyncSession) -> tuple[str, UUID]:
    result = await session.execute(select(RefreshToken).where(RefreshToken.token_id == old_token_id))
    old_token = result.scalar_one_or_none()
    if old_token is None:
        raise ValueError('Refresh token not found — family invalidated.')
    if old_token.is_revoked:
        await _revoke_family_by_id(old_token_id, session)
        await session.commit()
        raise ValueError('Refresh token reuse detected — family invalidated.')
    old_token.is_revoked = True
    await session.flush()
    return await create_refresh_token(user_id, session, rotated_from=old_token_id)

async def revoke_refresh_token(token_id: UUID, session: AsyncSession) -> None:
    await session.execute(update(RefreshToken).where(RefreshToken.token_id == token_id, RefreshToken.is_revoked.is_(False)).values(is_revoked=True))

async def _revoke_family_by_id(token_id: UUID, session: AsyncSession) -> None:
    revoked_ids: set[UUID] = set()
    current_id: UUID | None = token_id
    while current_id is not None:
        result = await session.execute(select(RefreshToken).where(RefreshToken.token_id == current_id))
        token = result.scalar_one_or_none()
        if token is None:
            break
        token.is_revoked = True
        revoked_ids.add(current_id)
        current_id = token.rotated_from
    frontier = list(revoked_ids)
    while frontier:
        result = await session.execute(select(RefreshToken.token_id, RefreshToken.is_revoked).where(RefreshToken.rotated_from.in_(frontier)))
        children = [(row[0], row[1]) for row in result.all()]
        if not children:
            break
        to_revoke = [cid for cid, revoked in children if not revoked]
        if to_revoke:
            await session.execute(update(RefreshToken).where(RefreshToken.token_id.in_(to_revoke)).values(is_revoked=True))
        all_children = [cid for cid, _ in children]
        revoked_ids.update(all_children)
        frontier = all_children
    await session.flush()
