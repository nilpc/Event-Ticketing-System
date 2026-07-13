"""NFR-4: Middleware that binds request context to structlog contextvars."""

from __future__ import annotations

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class RequestContextMiddleware(BaseHTTPMiddleware):
    """NFR-4: Bind request_id, trace_id, user_id into structlog context.

    Runs AFTER IdentityMiddleware so request.state.user_id is already set.
    Every ``structlog.get_logger()`` call downstream will automatically
    include these fields without manual pass-through.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Extract from response headers set by IdentityMiddleware
        request_id = request.headers.get("x-request-id", "") or str(uuid.uuid4())
        traceparent = request.headers.get("traceparent", "")
        trace_id = ""
        if traceparent:
            parts = traceparent.split("-")
            if len(parts) >= 3:
                trace_id = parts[1]

        user_id = getattr(request.state, "user_id", "")

        # Bind to structlog contextvars — all downstream log calls inherit these
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            trace_id=trace_id,
            user_id=user_id,
            service="gateway",
            method=request.method,
            path=request.url.path,
        )

        response = await call_next(request)

        # Ensure response headers carry the request_id
        response.headers["X-Request-ID"] = request_id
        if trace_id:
            response.headers["Traceparent"] = traceparent

        return response
