from __future__ import annotations

from urllib.parse import urlencode

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.security.jwt import create_access_token
from core.security.refresh import create_refresh_token
from services.identity.repositories.user_repo import UserRepository
from services.identity.schemas.auth import LoginResponse

GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL = 'https://www.googleapis.com/oauth2/v3/userinfo'
SCOPES = 'openid email profile'

class OAuthService:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)

    def get_authorize_url(self, redirect_uri: str, state: str) -> str:
        params = {'client_id': settings.GOOGLE_CLIENT_ID, 'redirect_uri': redirect_uri, 'response_type': 'code', 'scope': SCOPES, 'state': state, 'access_type': 'offline', 'prompt': 'consent'}
        return f'{GOOGLE_AUTH_URL}?{urlencode(params)}'

    async def handle_callback(self, code: str, redirect_uri: str) -> LoginResponse:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                token_resp = await client.post(GOOGLE_TOKEN_URL, data={'code': code, 'client_id': settings.GOOGLE_CLIENT_ID, 'client_secret': settings.GOOGLE_CLIENT_SECRET, 'redirect_uri': redirect_uri, 'grant_type': 'authorization_code'})
                token_resp.raise_for_status()
                tokens = token_resp.json()
                userinfo_resp = await client.get(GOOGLE_USERINFO_URL, headers={'Authorization': f"Bearer {tokens['access_token']}"})
                userinfo_resp.raise_for_status()
                userinfo = userinfo_resp.json()
        except httpx.HTTPStatusError as exc:
            raise ValueError(f'Google OAuth token exchange failed. Status {exc.response.status_code}: {exc.response.text[:200]}') from exc
        google_subject = userinfo['sub']
        email = userinfo.get('email', '')
        user = await self.user_repo.find_by_google_subject(google_subject)
        if user is None:
            user = await self.user_repo.find_by_email(email)
            if user is not None:
                linked = await self.user_repo.link_google_subject(user.user_id, google_subject)
                if not linked:
                    raise ValueError('Google account already linked to another user.')
            else:
                try:
                    user = await self.user_repo.create_user(email=email, google_subject_id=google_subject)
                except IntegrityError:
                    user = await self.user_repo.find_by_google_subject(google_subject)
                    if user is None:
                        raise ValueError('Failed to create or find user account.')
        raw_refresh, _ = await create_refresh_token(user.user_id, self.session)
        access_token = create_access_token(str(user.user_id))
        return LoginResponse(access_token=access_token, refresh_token=raw_refresh, is_admin=user.is_admin, is_master_admin=user.is_master_admin)
