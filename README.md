# Event Ticketing Backend

A high-concurrency event ticketing API built for flash-sale scenarios. Python 3.11+, FastAPI, PostgreSQL, Redis.

## Features

- **Five-layer concurrency control** — Redis hoarding locks, distributed locks, DB state checks, atomic transactions, and a background sweeper to prevent double-bookings
- **Virtual waiting room** — Redis-backed queue with token-based admission and crash recovery
- **JWT auth (RS256)** — Access/refresh token rotation with reuse detection, Google OAuth2
- **Stripe payments** — PaymentIntent flow with idempotent webhook processing
- **Transactional outbox** — `FOR UPDATE SKIP LOCKED` relay for reliable async event publishing
- **Kubernetes-ready** — Kustomize manifests, KEDA autoscaling, NetworkPolicies, PodDisruptionBudgets
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
- PostgreSQL 16+
- Redis 7+

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
cp .env.example .env           # edit DATABASE_URL, REDIS_URL, etc.

# Generate RSA keys for JWT
openssl genpkey -algorithm RSA -out certs/private.pem -pkeyopt rsa_keygen_bits:2048
openssl rsa -pubout -in certs/private.pem -out certs/public.pem

# Run migrations
alembic upgrade head

# Start the server
uvicorn services.gateway.app:create_app --factory --reload --port 8000
```

### Docker

```bash
docker build -t event-ticketing .
docker run -p 8000:8000 --env-file .env event-ticketing
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/auth/signup` | Register with email/password |
| POST | `/v1/auth/login` | Login, returns JWT pair |
| POST | `/v1/auth/refresh` | Rotate refresh token |
| GET | `/v1/venues` | List venues |
| GET | `/v1/events` | List events |
| GET | `/v1/showtimes/{id}/seats` | Seat map |
| POST | `/v1/queue/join` | Join virtual queue |
| GET | `/v1/queue/status` | Poll queue position |
| POST | `/v1/seats/lock` | Lock a seat |
| POST | `/v1/book` | Atomic booking |
| POST | `/v1/payments/intent` | Create Stripe PaymentIntent |
| POST | `/v1/webhooks/stripe` | Stripe webhook receiver |
| GET | `/health` | Liveness probe |
| GET | `/ready` | Readiness probe |

## Booking Flow

```
Signup/Login → Join Queue → Poll Status → Lock Seat → Book → Pay → Webhook Confirms
```

## Running Tests

```bash
# Unit + integration (requires Postgres + Redis)
pytest tests/ -v --tb=long

# Load test
locust -f tests/load/locustfile.py --host http://localhost:8000
```

## Background Workers

```bash
python -m services.workers sweeper    # Reverts expired bookings (60s cycle)
python -m services.workers relay      # Publishes outbox events (5s cycle)
python -m services.workers admitter   # Admits queued users (2s cycle)
```

## Kubernetes Deployment

```bash
kubectl apply -k k8s/base/
```

Includes: Gateway (2 replicas), Sweeper, Relay (2 replicas), Admitter, Migration Job, KEDA scalers, NetworkPolicies, PDB, Grafana dashboard.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI, Pydantic v2 |
| ORM | SQLAlchemy 2.0 (async) |
| Database | PostgreSQL (asyncpg), Redis |
| Auth | python-jose (RS256), bcrypt |
| Payments | Stripe SDK |
| Observability | structlog, Sentry, OpenTelemetry |
| Testing | pytest, testcontainers, Locust |
| CI/CD | GitHub Actions (lint, typecheck, test, Docker build + Trivy scan) |
| Deploy | Docker, Kubernetes (Kustomize), KEDA |

## License

MIT
