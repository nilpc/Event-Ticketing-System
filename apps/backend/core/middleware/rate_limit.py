from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.routing import BaseRoute, Match

from core.config import settings

if TYPE_CHECKING:
    from starlette.types import Scope

def _find_route_handler(routes: Iterable[BaseRoute], scope: Scope) -> Callable | None:
    handler = None
    for route in routes:
        match, _ = route.matches(scope)
        if match == Match.FULL:
            if hasattr(route, 'endpoint'):
                handler = route.endpoint
            elif hasattr(route, 'original_router'):
                sub = _find_route_handler(route.original_router.routes, scope)
                if sub is not None:
                    handler = sub
    return handler

def create_limiter() -> Limiter:
    import slowapi.middleware as _sm
    _sm._find_route_handler = _find_route_handler
    return Limiter(key_func=get_remote_address, storage_uri=settings.REDIS_URL, default_limits=[settings.RATE_LIMIT_PUBLIC], in_memory_fallback=[settings.RATE_LIMIT_PUBLIC], in_memory_fallback_enabled=True)
