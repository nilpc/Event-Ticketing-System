"""FR-1: AuthService — signup, login, GDPR operations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import zxcvbn
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import NotFoundError, WeakPasswordError
from core.security.jwt import create_access_token
from core.security.refresh import create_refresh_token
from services.identity.repositories.user_repo import UserRepository
from services.identity.schemas.auth import (
    LoginRequest,
    LoginResponse,
    SignupRequest,
    SignupResponse,
)

# FR-1: minimum zxcvbn score for password strength
MIN_PASSWORD_SCORE = 3
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

# Password hashing — bcrypt via passlib or hashlib fallback
try:
    from passlib.hash import bcrypt

    def _hash_password(password: str) -> str:
        return bcrypt.hash(password)

    def _verify_password(password: str, hashed: str) -> bool:
        return bcrypt.verify(password, hashed)
except ImportError:
    import hashlib

    _SALT = b"event-ticketing-fallback-salt"  # noqa: S105

    def _hash_password(password: str) -> str:  # type: ignore[misc]
        return hashlib.pbkdf2_hmac(
            "sha256", password.encode(), _SALT, iterations=600_000
        ).hex()

    def _verify_password(password: str, hashed: str) -> bool:  # type: ignore[misc]
        return _hash_password(password) == hashed


class AuthService:
    """FR-1: Auth business logic — signup, login, GDPR."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)

    async def signup(self, payload: SignupRequest) -> SignupResponse:
        """FR-1: Register with zxcvbn password strength validation."""
        result = zxcvbn.zxcvbn(payload.password, user_inputs=[payload.email])
        if result["score"] < MIN_PASSWORD_SCORE:
            raise WeakPasswordError(
                f"Password too weak (score {result['score']}/{MIN_PASSWORD_SCORE}). "
                + " ".join(result["feedback"]["suggestions"])
            )

        existing = await self.user_repo.find_by_email(payload.email)
        if existing is not None:
            raise ValueError("Email already registered.")

        password_hash = _hash_password(payload.password)
        user = await self.user_repo.create_user(
            email=payload.email, password_hash=password_hash
        )
        return SignupResponse(user_id=user.user_id, email=user.email)

    async def login(self, payload: LoginRequest) -> LoginResponse:
        """FR-1: Authenticate with account lockout policy."""
        user = await self.user_repo.find_by_email(payload.email)
        if user is None:
            raise NotFoundError("Invalid email or password.")

        if user.locked_until and user.locked_until > datetime.now(UTC):
            raise PermissionError(
                f"Account locked. Try again after {user.locked_until.isoformat()}."
            )

        # FR-1: Check account active BEFORE password check to avoid
        # leaking password validity for deactivated accounts.
        if not user.is_active:
            raise NotFoundError("Invalid email or password.")

        if not user.password_hash or not _verify_password(payload.password, user.password_hash):
            await self.user_repo.increment_failed_attempts(user.user_id)
            attempts = (user.failed_login_attempts or 0) + 1
            if attempts >= MAX_FAILED_ATTEMPTS:
                lock_until = datetime.now(UTC) + timedelta(minutes=LOCKOUT_MINUTES)
                await self.user_repo.lock_account(user.user_id, lock_until)
            # Commit lockout state immediately so rollback in get_db_session
            # doesn't undo the security-relevant writes.
            await self.session.commit()
            raise NotFoundError("Invalid email or password.")

        await self.user_repo.reset_failed_attempts(user.user_id)

        raw_token, _ = await create_refresh_token(user.user_id, self.session)
        access_token = create_access_token(str(user.user_id))
        return LoginResponse(
            access_token=access_token,
            refresh_token=raw_token,
        )

    async def soft_delete(self, user_id: UUID) -> None:
        """FR-1: GDPR soft-delete — mark deleted_at, deactivate."""
        user = await self.user_repo.find_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        await self.user_repo.soft_delete_user(user_id)

    async def anonymize(self, user_id: UUID) -> None:
        """FR-1: GDPR anonymization — scrub PII."""
        user = await self.user_repo.find_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        await self.user_repo.anonymize_user(user_id)
