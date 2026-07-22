# Feature 1: OpenAPI Client Generation (SDK Enhancement)

**Status:** Proposed
**Priority:** High (Quick Win)
**Owner:** Backend/Frontend
**Estimated Effort:** 1-2 days

## Overview

Auto-generate a type-safe TypeScript SDK from the existing FastAPI OpenAPI specification. Replace manual API calls in the frontend with generated clients/hooks.

## Goals

- Eliminate type drift between backend and frontend.
- Improve developer experience and reduce bugs.
- Enable easy extension for future clients (mobile, admin tools).

## Requirements

- Full type-safe client for all endpoints.
- Integration with TanStack Query (optional hooks).
- CI/CD automated regeneration.

## Implementation Plan

### Backend

Enhance OpenAPI docs (add examples, tags, response models where missing). Expose `/openapi.json` (already available).

### SDK Package (`packages/sdk`)

Add generation script using `openapi-typescript`.

```json
// packages/sdk/package.json
"scripts": {
  "generate": "openapi-typescript http://localhost:8000/openapi.json -o src/generated/api.ts"
}
```

### Frontend Integration

- Import generated types from `@event-ticketing/sdk` in `src/lib/api-routes.ts`.
- Replace hand-written types in `src/types/api.ts` with SDK exports.
- Wrap with TanStack Query where beneficial.

### CI/CD

Add step in `.github/workflows/ci.yml` to run generation and fail on diffs.

## Testing

- Type checking on generated code.
- E2E tests remain unchanged.

## Edge Cases

- Custom auth headers (handled in generated base client).
- Large responses (pagination already supported).

## Benefits

Strong type safety, faster feature development.
