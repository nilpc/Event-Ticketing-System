from __future__ import annotations
import secrets
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from core.db.session import get_db_session
from core.exceptions import WeakPasswordError
from core.redis import get_redis
from services.identity.schemas.auth import ErrorResponse, LoginRequest, LoginResponse, RefreshRequest, SignupRequest, SignupResponse
from services.identity.schemas.oauth import OAuthAuthorizeResponse
from services.identity.services.auth_service import AuthService
from services.identity.services.oauth_service import OAuthService
from services.identity.services.session_service import SessionService
logger = structlog.get_logger()
router = APIRouter(prefix='/v1/auth', tags=['identity'])

@router.post('/signup', response_model=SignupResponse, status_code=201, responses={409: {'model': ErrorResponse}})
async def signup(payload: SignupRequest, session: AsyncSession=Depends(get_db_session)) -> SignupResponse:
    svc = AuthService(session)
    try:
        return await svc.signup(payload)
    except WeakPasswordError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

@router.post('/login', response_model=LoginResponse, responses={401: {'model': ErrorResponse}, 423: {'model': ErrorResponse}})
async def login(payload: LoginRequest, session: AsyncSession=Depends(get_db_session)) -> LoginResponse:
    svc = AuthService(session)
    try:
        return await svc.login(payload)
    except PermissionError as exc:
        raise HTTPException(status_code=423, detail=str(exc))
    except (ValueError, LookupError) as exc:
        raise HTTPException(status_code=401, detail=str(exc))

@router.post('/refresh', response_model=LoginResponse)
async def refresh(payload: RefreshRequest, session: AsyncSession=Depends(get_db_session)) -> LoginResponse:
    svc = SessionService(session)
    try:
        return await svc.refresh_access_token(payload.refresh_token)
    except (ValueError, LookupError) as exc:
        raise HTTPException(status_code=401, detail=str(exc))

@router.post('/logout', status_code=204)
async def logout(payload: RefreshRequest, session: AsyncSession=Depends(get_db_session)) -> None:
    svc = SessionService(session)
    await svc.logout(payload.refresh_token)

@router.get('/google/authorize', response_model=OAuthAuthorizeResponse)
async def google_authorize(request: Request, session: AsyncSession=Depends(get_db_session)) -> OAuthAuthorizeResponse:
    from core.config.settings import settings
    redirect_uri = f'{settings.CLIENT_ORIGIN}/auth/callback'
    svc = OAuthService(session)
    state = secrets.token_urlsafe(32)
    try:
        redis = get_redis()
        await redis.set(f'oauth_state:{state}', '1', ex=600)
    except Exception:
        logger.warning('oauth_state_store_failed', reason='Redis unavailable')
    url = svc.get_authorize_url(redirect_uri, state)
    return OAuthAuthorizeResponse(authorize_url=url, state=state)

@router.get('/google/callback', response_model=LoginResponse, responses={400: {'model': ErrorResponse}})
async def google_callback(code: str, state: str, request: Request, session: AsyncSession=Depends(get_db_session)) -> LoginResponse:
    from core.config.settings import settings as app_settings
    try:
        redis = get_redis()
        exists = await redis.delete(f'oauth_state:{state}')
        if not exists:
            raise HTTPException(status_code=400, detail='Invalid or expired OAuth state.')
    except HTTPException:
        raise
    except Exception:
        logger.warning('oauth_state_validate_failed', reason='Redis unavailable')
    redirect_uri = f'{app_settings.CLIENT_ORIGIN}/auth/callback'
    svc = OAuthService(session)
    try:
        return await svc.handle_callback(code, redirect_uri)
    except (ValueError, LookupError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.delete('/me', status_code=204)
async def delete_me(request: Request, session: AsyncSession=Depends(get_db_session)) -> None:
    from core.security.auth import get_current_user_id
    user_id = get_current_user_id(request)
    svc = AuthService(session)
    await svc.soft_delete(user_id)

@router.post('/me/anonymize', status_code=204)
async def anonymize_me(request: Request, session: AsyncSession=Depends(get_db_session)) -> None:
    from core.security.auth import get_current_user_id
    user_id = get_current_user_id(request)
    svc = AuthService(session)
    await svc.anonymize(user_id)
