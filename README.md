# Event Ticketing System

A full-stack event ticketing platform built for flash-sale scenarios. React frontend + FastAPI backend + PostgreSQL (Neon) + Redis (Docker).

## Features

- **React frontend** — Vite + TypeScript, Tailwind CSS, TanStack Query, React Router
- **Admin panel** — Unified form to create events/movies, venues, and showtimes in one step; catalog management with delete
- **Five-layer concurrency control** — Redis hoarding locks, distributed locks, DB state checks, atomic transactions, and a background sweeper to prevent double-bookings
- **Virtual waiting room** — Redis-backed queue with token-based admission and crash recovery
- **JWT auth (RS256)** — Access/refresh token rotation with reuse detection, Google OAuth2
- **Admin token auth** — Separate `X-Admin-Token` header for admin endpoints; validated on login
- **Stripe payments** — PaymentIntent flow with idempotent webhook processing
- **Transactional outbox** — `FOR UPDATE SKIP LOCKED` relay for reliable async event publishing
- **Observability** — structlog (JSON), Sentry, W3C traceparent, Grafana dashboard
- **Docker Compose** — Full stack (backend + frontend + Redis) in one command

## Architecture

Strict **Controller-Service-Repository** pattern across four domain modules:

```
services/
  gateway/     # FastAPI app, middleware, routing
  identity/    # Users, auth, OAuth2, refresh tokens
  booking/     # Venues, events, seats, queue, bookings, admin CRUD
  payment/     # Stripe integration, webhook handling
  workers/     # Background: sweeper, outbox relay, queue admitter
```

Two PostgreSQL schemas (`identity`, `booking`) with cross-schema foreign keys.

## Quick Start

### Docker (Recommended)

```bash
git clone https://github.com/<you>/Event-Ticketing-System.git
cd Event-Ticketing-System

# Configure environment
cp .env.example .env
# Edit .env — set DATABASE_URL, ADMIN_TOKEN, etc.

# Start everything
docker compose up --build
```

Services:
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **Redis**: localhost:6379

### Local Development

#### Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 16+ (or Neon cloud)
- Redis 7+ (Docker recommended)

#### Backend

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -e ".[dev]"

# Configure environment
cp .env.example .env           # edit DATABASE_URL, REDIS_URL, CORS_ORIGINS, ADMIN_TOKEN

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

#### Frontend

```bash
cd web
npm install
npm run dev          # Vite dev server on :5173, proxies /v1 → backend :8000
```

#### Redis

```bash
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

## Admin Panel

1. Navigate to `/admin` (or click "Admin" in navbar when logged in)
2. Enter your admin token (the `ADMIN_TOKEN` value from `.env`)
3. **Catalog tab** — view/delete events, venues, and showtimes
4. **New Show tab** — unified form:
   - Pick an existing event/movie or create a new one
   - Pick an existing venue or create a new one
   - Set base price (₹), start/end times
   - Click "Create Show" — seats are auto-generated (VIP 10%, Premium 30%, Standard 60%)

## API Endpoints

### Public

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/auth/signup` | Register with email/password |
| POST | `/v1/auth/login` | Login, returns JWT pair |
| POST | `/v1/auth/refresh` | Rotate refresh token |
| GET | `/v1/venues` | List venues |
| GET | `/v1/events` | List events |
| GET | `/v1/events/{id}/showtimes` | Showtimes for an event |
| GET | `/v1/showtimes/{id}` | Showtime details |
| GET | `/v1/showtimes/{id}/seats` | Seat map |

### Authenticated (JWT)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/queue/join` | Join virtual queue |
| GET | `/v1/queue/status` | Poll queue position |
| GET | `/v1/queue/recover` | Recover queue session |
| POST | `/v1/seats/lock` | Lock a seat (600s TTL, re-entrant) |
| POST | `/v1/book` | Atomic booking (requires X-Queue-Token header) |
| GET | `/v1/bookings` | List user's bookings |
| POST | `/v1/payments/intent` | Create Stripe PaymentIntent |
| POST | `/v1/book/{id}/mock-confirm` | Demo: confirm without payment |

### Admin (X-Admin-Token)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/admin/showtimes` | List all showtimes |
| POST | `/v1/admin/events` | Create event/movie |
| PUT | `/v1/admin/events/{id}` | Update event |
| DELETE | `/v1/admin/events/{id}` | Delete event |
| POST | `/v1/admin/venues` | Create venue |
| PUT | `/v1/admin/venues/{id}` | Update venue |
| DELETE | `/v1/admin/venues/{id}` | Delete venue |
| POST | `/v1/admin/showtimes` | Create showtime (auto-generates seats) |
| PUT | `/v1/admin/showtimes/{id}` | Update showtime |
| DELETE | `/v1/admin/showtimes/{id}` | Delete showtime |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Liveness probe |
| GET | `/ready` | Readiness probe |

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

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://user:pass@host/db` |
| `CORS_ORIGINS` | Comma-separated allowed origins | `http://localhost:5173` |
| `CLIENT_ORIGIN` | Frontend URL for redirects | `http://localhost:5173` |
| `ADMIN_TOKEN` | Shared secret for admin endpoints | `your-secret-token` |

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

All run inside the backend container on startup:

- **Sweeper** (60s) — Reverts expired bookings
- **Outbox relay** (5s) — Publishes outbox events
- **Queue admitter** (2s) — Admits queued users in FIFO order

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
| Deploy | Docker Compose (multi-stage builds) |

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
