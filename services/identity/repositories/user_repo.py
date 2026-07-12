"""FR-1: Repository for identity.users persistence."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from services.identity.models.user import User


class UserRepository:
    """FR-1: User CRUD and GDPR operations — SRP, NFR-6."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def find_by_id(self, user_id: UUID) -> User | None:
        result = await self.session.execute(
            select(User).where(User.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def find_by_google_subject(self, google_subject_id: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.google_subject_id == google_subject_id)
        )
        return result.scalar_one_or_none()

    async def create_user(
        self,
        email: str,
        password_hash: str | None = None,
        google_subject_id: str | None = None,
    ) -> User:
        user = User(
            email=email,
            password_hash=password_hash,
            google_subject_id=google_subject_id,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def increment_failed_attempts(self, user_id: UUID) -> None:
        await self.session.execute(
            update(User)
            .where(User.user_id == user_id)
            .values(failed_login_attempts=User.failed_login_attempts + 1)
        )

    async def reset_failed_attempts(self, user_id: UUID) -> None:
        await self.session.execute(
            update(User)
            .where(User.user_id == user_id)
            .values(failed_login_attempts=0, locked_until=None)
        )

    async def lock_account(self, user_id: UUID, until: datetime) -> None:
        await self.session.execute(
            update(User)
            .where(User.user_id == user_id)
            .values(locked_until=until)
        )

    async def link_google_subject(self, user_id: UUID, google_subject_id: str) -> None:
        """FR-2: Link a Google subject ID to an existing user."""
        await self.session.execute(
            update(User)
            .where(User.user_id == user_id)
            .values(google_subject_id=google_subject_id)
        )

    # FR-1: GDPR soft-delete / anonymization

    async def soft_delete_user(self, user_id: UUID) -> None:
        await self.session.execute(
            update(User)
            .where(User.user_id == user_id)
            .values(deleted_at=datetime.now(UTC), is_active=False)
        )

    async def anonymize_user(self, user_id: UUID) -> None:
        anon_hash = hashlib.sha256(str(user_id).encode()).hexdigest()[:16]
        await self.session.execute(
            update(User)
            .where(User.user_id == user_id)
            .values(
                email=f"deleted_{anon_hash}@anonymized.invalid",
                password_hash=None,
                google_subject_id=None,
                anonymized=True,
                is_active=False,
                deleted_at=datetime.now(UTC),
            )
        )
