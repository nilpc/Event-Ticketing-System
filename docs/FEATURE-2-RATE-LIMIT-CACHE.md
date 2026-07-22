# Feature 2: Rate Limiting + Advanced Caching

**Status:** Proposed
**Priority:** High
**Owner:** Backend
**Estimated Effort:** 3-4 days

## Overview

Implement robust rate limiting and Redis-based caching to improve performance, protect against abuse, and handle traffic spikes.

## Goals

- Prevent bot abuse and DDoS on public endpoints.
- Reduce database load for read-heavy operations (catalog, seat maps).
- Maintain low latency during peak events.

## Requirements

- Configurable rate limits per route/role.
- Cache-Aside pattern with intelligent invalidation.
- Monitoring for hit rates and throttled requests.

## Implementation Plan

### Rate Limiting (Middleware)

```python
# apps/backend/core/middleware/rate_limit.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# In gateway/app.py
app.state.limiter = limiter
app.add_middleware(...)
# or use @limiter.limit("100/minute")
```

### Caching (Repository Layer)

```python
# apps/backend/services/booking/repositories/catalog_repo.py
async def get_events(self, filters):
    cache_key = f"events:{hash(filters)}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    data = await self.db_query(...)
    await redis.set(cache_key, json.dumps(data), ex=300)  # 5 min
    return data
```

### Invalidation

- Use existing Redis Pub/Sub or Outbox pattern.
- On booking events: `redis.publish("cache_invalidate", {"key": "events:*"})`.

### Config

Add to `core/config/settings.py` (limits, TTLs).

## Testing

- Load tests with Locust (before/after metrics).
- Unit tests for middleware and cache logic.

## Edge Cases

- Cache stampede (use locks or early expiration).
- Authenticated vs public limits.
- Invalidations during high write load.

## Benefits

Better scalability and resilience.
