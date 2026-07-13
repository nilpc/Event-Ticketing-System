"""FR-11: Gateway middleware -- JWT enforcement, header stripping, request ID, traceparent."""

from __future__ import annotations

import uuid

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = structlog.get_logger()

# Paths that bypass JWT enforcement (must present a valid token).
# Auth endpoints and catalog are public; they do NOT require a JWT.
_PUBLIC_PREFIXES: tuple[str, ...] = (
    "/health",
    "/ready",
    "/v1/auth/",
    "/v1/venues",
    "/v1/events",
    "/v1/showtimes/",
    "/v1/webhooks/",
    "/docs",
    "/openapi.json",
    "/redoc",
)

# Client-supplied headers that MUST be stripped (zero-trust).
_STRIPPED_HEADERS: tuple[str, ...] = (
    "x-user-id",
    "x-request-id",
    "x-correlation-id",
)


class IdentityMiddleware(BaseHTTPMiddleware):
    """FR-11: Validate JWT, strip client identity headers, inject trusted headers.

    In a real deployment this runs on an API Gateway (Kong/Envoy) in front
    of the backend services.  In the monolith it is modelled as ASGI
    middleware so the same contract holds locally.
    """

    def __init__(self, app, public_key_path: str = "certs/public.pem") -> None:
        super().__init__(app)
        self._public_key_path = public_key_path

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # --- Step 1: Strip client-supplied identity headers (zero-trust) ---
        filtered_headers = []
        for k, v in request.scope.get("headers", []):
            name = k.decode() if isinstance(k, bytes) else k
            if name not in _STRIPPED_HEADERS:
                filtered_headers.append((k, v))
        request.scope["headers"] = filtered_headers

        # --- Step 2: X-Request-ID injection ---
        request_id = ""
        for k, v in request.scope.get("headers", []):
            name = k.decode() if isinstance(k, bytes) else k
            if name == "x-request-id":
                request_id = v.decode() if isinstance(v, bytes) else v
                break
        if not request_id:
            request_id = str(uuid.uuid4())

        # --- Step 3: W3C traceparent injection ---
        traceparent = ""
        for k, v in request.scope.get("headers", []):
            name = k.decode() if isinstance(k, bytes) else k
            if name == "traceparent":
                traceparent = v.decode() if isinstance(v, bytes) else v
                break
        if not traceparent:
            trace_id = uuid.uuid4().hex  # 32 hex chars
            span_id = uuid.uuid4().hex[:16]  # 16 hex chars
            traceparent = f"00-{trace_id}-{span_id}-01"

        # --- Step 4: JWT extraction ---
        # Always extract user_id from Bearer token if present.
        # For protected routes, missing/invalid token returns 401.
        # For public routes, missing token sets user_id to empty.
        user_id = ""
        token = ""
        auth_header = ""
        for k, v in request.scope.get("headers", []):
            name = k.decode() if isinstance(k, bytes) else k
            if name == "authorization":
                auth_header = v.decode() if isinstance(v, bytes) else v
                break
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:]

        is_public = any(
            request.url.path == p or request.url.path.startswith(p)
            for p in _PUBLIC_PREFIXES
        )

        if token:
            try:
                from jose import JWTError

                from core.security.jwt import decode_access_token

                claims = decode_access_token(token)
                user_id = claims.get("sub", "")
            except JWTError as exc:
                if not is_public:
                    logger.warning("jwt_validation_failed", error=str(exc))
                    return Response(
                        content='{"detail":"Invalid or expired token."}',
                        status_code=401,
                        media_type="application/json",
                    )
                # Public route with bad token: ignore silently
                user_id = ""
        elif not is_public:
            return Response(
                content='{"detail":"Authentication required."}',
                status_code=401,
                media_type="application/json",
            )

        # --- Step 5: Expose user_id to downstream dependencies ---
        request.state.user_id = user_id

        # --- Step 6: Build response with trusted headers ---
        response = await call_next(request)

        response.headers["X-Request-ID"] = request_id
        response.headers["X-User-Id"] = user_id
        response.headers["Traceparent"] = traceparent

        return response
