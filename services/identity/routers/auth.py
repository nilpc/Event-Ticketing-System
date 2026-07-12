"""FR-1, FR-2, FR-3: Identity auth router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.session import get_db_session
from core.exceptions import WeakPasswordError
from services.identity.schemas.auth import (
    ErrorResponse,
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    SignupRequest,
    SignupResponse,
)
from services.identity.schemas.oauth import OAuthAuthorizeResponse
from services.identity.services.auth_service import AuthService
from services.identity.services.oauth_service import OAuthService
from services.identity.services.session_service import SessionService

router = APIRouter(prefix="/v1/auth", tags=["identity"])


@router.post(
    "/signup",
    response_model=SignupResponse,
    status_code=201,
    responses={409: {"model": ErrorResponse}},
)
async def signup(
    payload: SignupRequest,
    session: AsyncSession = Depends(get_db_session),
) -> SignupResponse:
    """FR-1: Register with email/password."""
    svc = AuthService(session)
    try:
        return await svc.signup(payload)
    except WeakPasswordError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={401: {"model": ErrorResponse}, 423: {"model": ErrorResponse}},
)
async def login(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
) -> LoginResponse:
    """FR-1: Authenticate with email/password, get token pair."""
    svc = AuthService(session)
    try:
        return await svc.login(payload)
    except PermissionError as exc:
        raise HTTPException(status_code=423, detail=str(exc))
    except (ValueError, LookupError) as exc:
        raise HTTPException(status_code=401, detail=str(exc))


@router.post("/refresh", response_model=LoginResponse)
async def refresh(
    payload: RefreshRequest,
    session: AsyncSession = Depends(get_db_session),
) -> LoginResponse:
    """FR-3: Rotate refresh token, get new token pair."""
    svc = SessionService(session)
    try:
        return await svc.refresh_access_token(payload.refresh_token)
    except (ValueError, LookupError) as exc:
        raise HTTPException(status_code=401, detail=str(exc))


@router.post("/logout", status_code=204)
async def logout(
    payload: RefreshRequest,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """FR-3: Revoke refresh token."""
    svc = SessionService(session)
    await svc.logout(payload.refresh_token)


@router.get(
    "/google/authorize",
    response_model=OAuthAuthorizeResponse,
)
async def google_authorize(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> OAuthAuthorizeResponse:
    """FR-2: Get Google OAuth2 authorization URL."""
    from urllib.parse import urlparse, urlunparse

    parsed = urlparse(str(request.url))
    callback_path = parsed.path.replace("/authorize", "/callback")
    redirect_uri = urlunparse(parsed._replace(path=callback_path, query="", fragment=""))
    svc = OAuthService(session)
    state = "placeholder_state"  # TODO: generate CSRF state
    url = svc.get_authorize_url(redirect_uri, state)
    return OAuthAuthorizeResponse(authorize_url=url, state=state)


@router.get(
    "/google/callback",
    response_model=LoginResponse,
    responses={400: {"model": ErrorResponse}},
)
async def google_callback(
    code: str,
    state: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> LoginResponse:
    """FR-2: Handle Google OAuth2 callback, issue tokens."""
    from urllib.parse import urlparse, urlunparse

    parsed = urlparse(str(request.url))
    redirect_uri = urlunparse(parsed._replace(query="", fragment=""))
    svc = OAuthService(session)
    try:
        return await svc.handle_callback(code, redirect_uri)
    except (ValueError, LookupError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/me", status_code=204)
async def delete_me(
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """FR-1: GDPR soft-delete (placeholder — needs JWT auth dependency)."""
    raise HTTPException(status_code=501, detail="Requires JWT auth dependency (Phase 3)")


@router.post("/me/anonymize", status_code=204)
async def anonymize_me(
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """FR-1: GDPR anonymization (placeholder — needs JWT auth dependency)."""
    raise HTTPException(status_code=501, detail="Requires JWT auth dependency (Phase 3)")
