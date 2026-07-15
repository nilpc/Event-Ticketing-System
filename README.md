# Event Ticketing System

A full-stack event ticketing platform built for flash-sale scenarios. React frontend + FastAPI backend + PostgreSQL (Neon) + Redis (Docker).

## Features

- **React frontend** — Vite + TypeScript, Tailwind CSS, TanStack Query, React Router
- **Five-layer concurrency control** — Redis hoarding locks, distributed locks, DB state checks, atomic transactions, and a background sweeper to prevent double-bookings
- **Virtual waiting room** — Redis-backed queue with token-based admission and crash recovery
- **JWT auth (RS256)** — Access/refresh token rotation with reuse detection, Google OAuth2
- **Stripe payments** — PaymentIntent flow with idempotent webhook processing
- **Transactional outbox** — `FOR UPDATE SKIP LOCKED` relay for reliable async event publishing
- **Observability** — structlog (JSON), Sentry, W3C traceparent, Grafana dashboard

## Architecture

Strict **Controller-Service-Repository** pattern across four domain modules:

```
services/
  gateway/     # FastAPI app, middleware, routing
  identity/    # Users, auth, OAuth2, refresh tokens
  booking/     # Venues, events, seats, queue, bookings
  payment/     # Stripe integration, webhook handling
  workers/     # Background: sweeper, outbox relay, queue admitter
```

Two PostgreSQL schemas (`identity`, `booking`) with cross-schema foreign keys.

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 16+ (or Neon cloud)
- Redis 7+ (Docker recommended)

### Local Development

```bash
# Clone and install
git clone https://github.com/<you>/Event-Ticketing-System.git
cd Event-Ticketing-System
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -e ".[dev]"

# Configure environment
cp .env.example .env           # edit DATABASE_URL, REDIS_URL, CORS_ORIGINS, etc.

# Generate RSA keys for JWT
openssl genpkey -algorithm RSA -out certs/private.pem -pkeyopt rsa_keygen_bits:2048
openssl rsa -pubout -in certs/private.pem -out certs/public.pem

# Run migrations
alembic upgrade head

# Seed database (optional)
python -m scripts.seed

# Start the backend
uvicorn services.gateway.app:create_app --factory --reload --port 8000
```

### Frontend

```bash
cd web
npm install
npm run dev          # Vite dev server on :5173, proxies /v1 → backend :8000
```

### Redis (Docker)

```bash
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

### Docker (Full Stack)

```bash
docker build -t event-ticketing .
docker run -p 8000:8000 --env-file .env event-ticketing
```

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/v1/auth/signup` | — | Register with email/password |
| POST | `/v1/auth/login` | — | Login, returns JWT pair |
| POST | `/v1/auth/refresh` | — | Rotate refresh token |
| GET | `/v1/venues` | — | List venues |
| GET | `/v1/events` | — | List events |
| GET | `/v1/showtimes/{id}` | — | Showtime details |
| GET | `/v1/showtimes/{id}/seats` | — | Seat map |
| POST | `/v1/queue/join` | JWT | Join virtual queue |
| GET | `/v1/queue/status` | JWT | Poll queue position |
| GET | `/v1/queue/recover` | JWT | Recover queue session |
| POST | `/v1/seats/lock` | JWT | Lock a seat (600s TTL) |
| POST | `/v1/book` | JWT + Queue Token | Atomic booking |
| GET | `/v1/bookings` | JWT | List user's bookings |
| POST | `/v1/payments/intent` | JWT | Create Stripe PaymentIntent |
| POST | `/v1/webhooks/stripe` | — | Stripe webhook receiver |
| POST | `/v1/book/{id}/mock-confirm` | JWT | Demo: confirm without payment |
| GET | `/health` | — | Liveness probe |
| GET | `/ready` | — | Readiness probe |

## Booking Flow

```
Signup/Login → Join Queue → Admitted → Select Seat → Lock → Book → Pay → Confirmed
```

1. **Queue**: User joins the virtual waiting room; background admitter admits users in FIFO order
2. **Seat Selection**: Admitted users see the seat map and select a seat
3. **Lock**: Redis Lua script acquires an exclusive lock (600s TTL); re-entrant for same user
4. **Book**: Atomic DB transaction transitions seat to PENDING, creates booking, emits outbox event
5. **Pay**: Stripe PaymentIntent or mock-confirm for demo
6. **Confirm**: Booking marked CONFIRMED, seat marked SOLD

## Running Tests

```bash
# Unit + integration (requires Postgres + Redis)
pytest tests/ -v --tb=long

# Frontend lint + typecheck
cd web
npm run lint
npx tsc -b --noEmit

# Load test
locust -f tests/load/locustfile.py --host http://localhost:8000
```

## Background Workers

```bash
python -m services.workers sweeper    # Reverts expired bookings (60s cycle)
python -m services.workers relay      # Publishes outbox events (5s cycle)
python -m services.workers admitter   # Admits queued users (2s cycle)
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS, TanStack Query |
| Framework | FastAPI, Pydantic v2 |
| ORM | SQLAlchemy 2.0 (async) |
| Database | PostgreSQL (Neon cloud, asyncpg), Redis 7 (Docker) |
| Auth | python-jose (RS256), bcrypt |
| Payments | Stripe SDK |
| Observability | structlog, Sentry, OpenTelemetry |
| Testing | pytest, testcontainers, Locust |
| CI/CD | GitHub Actions (ruff, mypy, eslint, tsc, pytest) |
| Deploy | Docker (multi-stage build) |

## CI Checks

All checks must pass before merge:

```bash
ruff check .                    # Python lint
mypy core services --ignore-missing-imports   # Python typecheck
cd web && npm run lint          # ESLint
cd web && npx tsc -b --noEmit   # TypeScript typecheck
pytest tests/ -v                # Backend tests
```

## License

MIT
