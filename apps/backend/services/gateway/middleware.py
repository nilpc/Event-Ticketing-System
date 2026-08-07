from __future__ import annotations

import uuid

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = structlog.get_logger()
_PUBLIC_PREFIXES: tuple[str, ...] = ('/health', '/ready', '/v1/auth/', '/v1/venues', '/v1/events', '/v1/showtimes', '/v1/webhooks/', '/docs', '/openapi.json', '/redoc')
_STRIPPED_HEADERS: tuple[str, ...] = ('x-user-id', 'x-request-id', 'x-correlation-id')

class IdentityMiddleware(BaseHTTPMiddleware):

    def __init__(self, app, public_key_path: str='certs/public.pem') -> None:
        super().__init__(app)
        self._public_key_path = public_key_path

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        filtered_headers = []
        for k, v in request.scope.get('headers', []):
            name = k.decode() if isinstance(k, bytes) else k
            if name not in _STRIPPED_HEADERS:
                filtered_headers.append((k, v))
        request.scope['headers'] = filtered_headers
        request_id = ''
        for k, v in request.scope.get('headers', []):
            name = k.decode() if isinstance(k, bytes) else k
            if name == 'x-request-id':
                request_id = v.decode() if isinstance(v, bytes) else v
                break
        if not request_id:
            request_id = str(uuid.uuid4())
        traceparent = ''
        for k, v in request.scope.get('headers', []):
            name = k.decode() if isinstance(k, bytes) else k
            if name == 'traceparent':
                traceparent = v.decode() if isinstance(v, bytes) else v
                break
        if not traceparent:
            trace_id = uuid.uuid4().hex
            span_id = uuid.uuid4().hex[:16]
            traceparent = f'00-{trace_id}-{span_id}-01'
        user_id = ''
        token = ''
        auth_header = ''
        for k, v in request.scope.get('headers', []):
            name = k.decode() if isinstance(k, bytes) else k
            if name == 'authorization':
                auth_header = v.decode() if isinstance(v, bytes) else v
                break
        if auth_header.lower().startswith('bearer '):
            token = auth_header[7:]
        is_public = any(request.url.path == p or request.url.path.startswith(p) for p in _PUBLIC_PREFIXES)
        if token:
            try:
                from jose import JWTError

                from core.security.jwt import decode_access_token
                claims = decode_access_token(token)
                user_id = claims.get('sub', '')
            except JWTError as exc:
                if not is_public:
                    logger.warning('jwt_validation_failed', error=str(exc))
                    return Response(content='{"detail":"Invalid or expired token."}', status_code=401, media_type='application/json')
                user_id = ''
        elif not is_public:
            return Response(content='{"detail":"Authentication required."}', status_code=401, media_type='application/json')
        request.state.user_id = user_id
        response = await call_next(request)
        response.headers['X-Request-ID'] = request_id
        response.headers['X-User-Id'] = user_id
        response.headers['Traceparent'] = traceparent
        return response
