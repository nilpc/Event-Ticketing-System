from __future__ import annotations
import uuid
import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

class RequestContextMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get('x-request-id', '') or str(uuid.uuid4())
        traceparent = request.headers.get('traceparent', '')
        trace_id = ''
        if traceparent:
            parts = traceparent.split('-')
            if len(parts) >= 3:
                trace_id = parts[1]
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id, trace_id=trace_id, service='gateway', method=request.method, path=request.url.path)
        response = await call_next(request)
        user_id = response.headers.get('X-User-Id', '')
        structlog.contextvars.bind_contextvars(user_id=user_id)
        response.headers['X-Request-ID'] = request_id
        if trace_id:
            response.headers['Traceparent'] = traceparent
        return response
