# Event Ticketing System

A full-stack event ticketing platform built for flash-sale scenarios. Turborepo monorepo with React frontend + FastAPI backend + PostgreSQL + Redis. **Live on AWS EKS** — full Stripe card checkout verified end-to-end.

Source of truth: [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md) (requirement contract, FR/NFR catalog) and [`docs/PHASES.md`](docs/PHASES.md) (build order + status).

## Features

- **React frontend** — Vite + TypeScript, Tailwind CSS, TanStack Query, React Router
- **Admin panel** — Unified form to create events/movies, venues, and showtimes in one step; catalog management with delete; promote users to admin via API
- **Multi-seat booking** — Select up to 8 seats in one checkout; all locked and paid atomically via a `booking_seats` junction table
- **Five-layer concurrency control** — Redis hoarding locks, distributed locks, DB state checks, atomic transactions, and a background sweeper to prevent double-bookings
- **Virtual waiting room** — Redis-backed queue with token-based admission and crash recovery
- **JWT auth (RS256)** — Access/refresh token rotation with reuse detection, Google OAuth2; admin users identified by `is_admin` column in DB
- **Stripe payments (card-only, verified E2E)** — PCI-compliant PaymentIntent flow, card-only (Link/Klarna disabled so `confirmPayment` never blocks), webhook auto-confirmation of bookings
- **Transactional outbox** — `FOR UPDATE SKIP LOCKED` relay for reliable async event publishing
- **WebSocket live updates** — Real-time seat status broadcasting via Redis Pub/Sub backplane (`FR-14`)
- **Catalog caching** — Redis cache-aside for venues/events with invalidation (`FR-4`)
- **Rate limiting** — slowapi + Redis distributed rate limits (public/auth/booking tiers) (`NFR-8`)
- **Observability** — structlog (JSON), Sentry, W3C traceparent, CloudWatch dashboard
- **Docker Compose** — Full stack (backend + frontend + Redis) in one command; auto-migration + auto-seed on startup
- **Kubernetes (EKS, live)** — EKS 1.30 + ALB + RDS + CloudFront + WAF (count mode), KEDA, PDBs, network policies, ArgoCD GitOps

## Current Status

- **Phase 1–9 complete** (see [`docs/PHASES.md`](docs/PHASES.md) for per-phase status).
- **Live on AWS EKS**: Terraform (VPC, EKS, RDS, IAM, CloudWatch), ArgoCD auto-syncs `k8s/prod/` on push to `main`, ECR images via `scripts/deploy.ps1`.
- **Payment flow verified in production**: queue → lock → book → card-only Stripe charge → webhook auto-confirms the booking in ~2s. Three real production bugs (webhook `StripeObject.metadata` 500, CSP blocking Stripe.js, Stripe Link blocking card confirmation) were found and fixed during this verification.

## Monorepo Structure

```
Event-Ticketing-System/
├── apps/
│   ├── backend/              # Python FastAPI (core, services, migrations, tests)
│   └── web/                  # React + Vite frontend
├── turbo.json                # Turborepo task pipeline + caching
├── pnpm-workspace.yaml       # Workspace package resolution
├── package.json              # Root scripts (dev, build, lint, test, typecheck)
├── k8s/                   # Kustomize: base + minikube + prod overlays
│   ├── base/              # Deployments, services, PDBs, KEDA scalers, network policies
│   ├── minikube/          # Ingress, local Postgres/Redis, secrets
│   ├── prod/              # ALB ingress, External Secrets, ECR image patches
│   └── argocd/            # ArgoCD Repository + Application (GitOps bootstrap)
├── infra/terraform/       # AWS EKS infrastructure (VPC, EKS, RDS, IAM, CloudWatch)
├── scripts/               # Bootstrap (init.ps1), deploy (deploy.ps1), minikube scripts
├── Dockerfile                # Multi-stage build (api + web targets)
├── supervisord.conf          # Process manager for nginx + backend
└── docker-compose.yml        # Postgres + Redis + app
```

### Backend Services

Strict **Controller-Service-Repository** pattern across four domain modules:

```
apps/backend/
├── core/          # Config, DB, security, middleware, observability
├── services/
│   ├── gateway/   # FastAPI app, middleware, routing
│   ├── identity/  # Users, auth, OAuth2, refresh tokens
│   ├── booking/   # Venues, events, seats, queue, bookings, admin CRUD
│   ├── payment/   # Stripe integration, webhook handling
│   └── workers/   # Background: sweeper, outbox relay, queue admitter
├── migrations/    # Alembic
└── tests/         # pytest
```

Two PostgreSQL schemas (`identity`, `booking`) with cross-schema foreign keys.

## Quick Start

### Docker (Recommended)

```bash
git clone https://github.com/<you>/Event-Ticketing-System.git
cd Event-Ticketing-System

cp .env.example .env
# Edit .env — set DATABASE_URL, etc.

docker compose up --build
```

On first boot the entrypoint automatically:
1. Checks the database for required schemas
2. Runs all Alembic migrations (001 → latest)
3. Seeds default data (10 events, 10 showtimes, 120 seats, admin user)

Services:
- **App (frontend + API)**: http://localhost
- **Redis**: localhost:6379

### Kubernetes (Minikube)

One-command local deployment with Kustomize overlays:

```powershell
.\k8s\deploy-minikube.ps1
```

The script starts Minikube, builds the Docker image inside the Minikube daemon, applies the `k8s/minikube/` overlay (includes local Postgres, Redis, secrets, ingress), and waits for all pods to be ready.

```bash
# Get the service URL
minikube service gateway -n event-ticketing --url

# Useful commands
kubectl get pods -n event-ticketing
kubectl logs -f deployment/gateway -n event-ticketing
kubectl delete -k k8s/minikube/
minikube stop
```

Base manifests (`k8s/base/`) include: gateway deployment + service, background worker deployments (sweeper, relay, admitter), migration job, KEDA autoscalers, PodDisruptionBudgets, and network policies.

### AWS EKS (Production)

Provision the cluster with Terraform, then bootstrap and deploy:

```bash
# 1. Provision AWS infrastructure (VPC, EKS 1.30, RDS, IAM, CloudWatch)
cd infra/terraform
terraform apply

# 2. Bootstrap the cluster — Helm charts (ALB Controller, KEDA, ESO, Redis, ArgoCD,
#    cert-manager, node-termination-handler) + writes secrets to SSM Parameter Store
.\scripts\init.ps1 `
    -LbControllerRoleArn "<from terraform output>" `
    -EsoRoleArn "<from terraform output>" `
    -RdsEndpoint "<from terraform output>"

# 3. Point ArgoCD at the repo (one-time) — it then syncs k8s/prod/ on every push to main
kubectl apply -f k8s/argocd/

# 4. Build images, push to ECR, apply + restart the prod overlay
$env:VITE_STRIPE_PUBLISHABLE_KEY = "pk_test_..."   # Stripe publishable key for the web build
.\scripts\deploy.ps1

# 5. Get the public URLs
kubectl -n event-ticketing get ingress/gateway                       # ALB DNS
terraform -chdir=infra/terraform output cloudfront_domain             # CloudFront URL (production SPA)
```

Image updates ship via `scripts/deploy.ps1` (build → push `:main` to ECR → `kubectl apply -k k8s/prod/` → rollout restart). Manifest-only changes are pushed to `main` and ArgoCD auto-syncs them (`automated.sync` on, `prune: false`, `selfHeal: false`). Access ArgoCD with `kubectl port-forward -n argocd svc/argocd-server 8080:80`; the admin password is in `argocd-initial-admin-secret`.

**Secrets & security:** JWT keys are injected at runtime via `JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY` env vars (never baked into images — `entrypoint.sh` writes them to disk before app start); Redis requires auth (`REDIS_URL` includes `:password@`); DB/Redis/JWT/Stripe secrets live in SSM Parameter Store and are fetched by External Secrets Operator. WAF starts in **Count** mode (set `waf_action = "block"` only after analyzing CloudWatch Logs). HTTPS requires a custom domain + ACM cert; it's HTTP-only by default.

Cost-optimized: single-AZ RDS db.t4g.micro (10GB), 1× on-demand t3.small for infra pods, 1× spot t3.medium for app pods, single NAT Gateway, self-hosted Redis via Bitnami Helm ($0), CloudFront CDN, WAF in Count mode. Monthly budget alarm at $150 (~$5.50/day). Destroy with `terraform destroy` (from `infra/terraform/`) when not in use.

### Database Management

#### Reset booking data (keep users)

Truncates all booking schema tables (events, showtimes, seats, bookings, etc.) while preserving identity data (users, refresh tokens). The entrypoint will automatically re-seed events on next container restart.

```bash
docker compose exec -T app python -c "
import asyncio
from sqlalchemy import text
from core.db.session import async_session_factory

async def reset():
    async with async_session_factory() as session:
        await session.execute(text('TRUNCATE booking.outbox_events, booking.processed_webhook_events, booking.booking_events, booking.payments, booking.booking_seats, booking.bookings, booking.seats, booking.showtimes, booking.events, booking.venues CASCADE'))
        await session.commit()
    print('Done')

asyncio.run(reset())
"
```

#### Check table counts

```bash
docker compose exec -T app python -c "
import asyncio
from sqlalchemy import text
from core.db.session import async_session_factory

async def check():
    async with async_session_factory() as session:
        for t in ['booking.events', 'booking.showtimes', 'booking.seats', 'booking.bookings']:
            r = await session.execute(text(f'SELECT count(*) FROM {t}'))
            print(f'{t}: {r.scalar()}')

asyncio.run(check())
"
```

#### Re-seed manually

```bash
docker compose exec -T app python seed.py --reset
```

### Local Development

#### Prerequisites

- Python 3.11+
- Node.js 22+
- pnpm 9+
- PostgreSQL 16+
- Redis 7+ (Docker recommended)

#### Install All Dependencies

```bash
pnpm install          # installs JS deps for all workspace packages
```

#### Backend

```bash
cd apps/backend

python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -e ".[dev]"

# Configure environment (edit DATABASE_URL, REDIS_URL, CORS_ORIGINS)
cp ../../.env.example ../../.env

# Generate RSA keys for JWT
mkdir -p certs
openssl genpkey -algorithm RSA -out certs/private.pem -pkeyopt rsa_keygen_bits:2048
openssl rsa -pubout -in certs/private.pem -out certs/public.pem

# Run migrations
alembic upgrade head

# Seed database (optional — creates admin user + 10 events + showtimes + seats)
python seed.py

# Start the backend
uvicorn services.gateway.app:create_app --factory --reload --port 8000
```

#### Frontend

```bash
pnpm --filter @event-ticketing/web dev    # Vite dev server on :5173, proxies /v1 → backend :8000
```

#### Redis

```bash
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

## Admin Panel

1. Navigate to `/admin` (or click "Admin" in navbar when logged in as an admin user)
2. Admin access is controlled by the `is_admin` column on `identity.users` — no shared token needed
3. **Catalog tab** — view/delete events, venues, and showtimes
4. **New Show tab** — unified form:
   - Pick an existing event/movie or create a new one
   - Pick an existing venue or create a new one
   - Set base price (₹), start/end times
   - Click "Create Show" — seats are auto-generated (VIP 10%, Premium 30%, Standard 60%)

### Default Admin Credentials

- **Email**: `admin@event-ticketing.dev`
- **Password**: generated at seed time — set the `ADMIN_PASSWORD` env var when seeding (a random one is generated and printed to logs if unset)

### Grant Admin Access to an Existing User

Admin users can promote others via `POST /v1/admin/users/{id}/promote` (JWT + `is_admin` required), or set `is_admin` directly in the database.

#### Docker

```bash
# Promote by email
docker compose exec -T app python -c "
import asyncio
from sqlalchemy import text
from core.db.session import async_session_factory

async def promote(email):
    async with async_session_factory() as session:
        await session.execute(
            text('UPDATE identity.users SET is_admin = true WHERE email = :email'),
            {'email': email},
        )
        await session.commit()
    print(f'{email} is now an admin')

asyncio.run(promote('user@example.com'))
"
```

#### Local (psql)

```sql
UPDATE identity.users SET is_admin = true WHERE email = 'user@example.com';
```

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
| GET | `/v1/showtimes` | List all showtimes |
| GET | `/v1/showtimes/{id}` | Showtime details |
| GET | `/v1/showtimes/{id}/seats` | Seat map |
| POST | `/v1/webhooks/stripe` | Stripe webhook receiver (signature-verified, no auth) |

### Authenticated (JWT)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/auth/logout` | Logout (revoke refresh token) |
| GET | `/v1/auth/google` | Google OAuth2 SSO redirect |
| POST | `/v1/queue/join` | Join virtual queue |
| GET | `/v1/queue/status` | Poll queue position |
| GET | `/v1/queue/recover` | Recover queue session |
| POST | `/v1/seats/lock` | Lock one or more seats (600s TTL, re-entrant) |
| POST | `/v1/book` | Atomic multi-seat booking (requires X-Queue-Token header) |
| GET | `/v1/bookings` | List user's bookings (includes all seats per booking) |
| POST | `/v1/book/{id}/mock-confirm` | Demo: confirm all seats in a booking without payment |
| POST | `/v1/payments/intent` | Create card-only Stripe PaymentIntent |
| POST | `/v1/payments/{id}/sync` | Sync payment status with Stripe and confirm booking |
| DELETE | `/v1/auth/me` | Delete account (GDPR soft-delete) |
| POST | `/v1/auth/me/anonymize` | Anonymize account data (GDPR) |

### WebSocket

| Endpoint | Description |
|----------|-------------|
| `ws://host/ws/showtime/{id}?token={jwt}` | Real-time seat status updates (FR-14) |

### Admin (JWT + is_admin)

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
| POST | `/v1/admin/users/{id}/promote` | Promote a user to admin |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Liveness probe |
| GET | `/ready` | Readiness probe |

## Booking Flow

```
Signup/Login → Join Queue → Admitted → Select Seats → Lock → Book → Pay → Confirmed
```

1. **Queue**: User joins the virtual waiting room; background admitter admits users in FIFO order
2. **Multi-Seat Selection**: Admitted users see the seat map and select up to 8 seats (toggle to select/deselect, live total shown)
3. **Lock**: Redis Lua script acquires exclusive locks for all selected seats (600s TTL); re-entrant for same user; atomic rollback on failure
4. **Book**: Single atomic DB transaction transitions all seats to PENDING, creates one booking with `booking_seats` junction rows, emits outbox event
5. **Pay**: Card-only Stripe PaymentIntent or mock-confirm for demo (pays total across all seats); Stripe Link/Klarna disabled so `confirmPayment` never blocks
6. **Confirm**: Stripe webhook (or `sync`) marks the booking CONFIRMED and all seats SOLD — verified to fire ~2s after the card charge succeeds

## WebSocket Live Updates (`FR-14`)

Clients connect to `ws://host/ws/showtime/{show_id}?token={jwt}` to receive real-time seat status changes. The server pushes JSON messages:

```json
{
  "type": "seat_update",
  "seat_id": "A1",
  "status": "SOLD",
  "locked_by": "user-uuid"
}
```

- Authenticated via the same JWT used for HTTP; invalid/missing token closes with code 4001
- Single-instance: connections held in memory
- Multi-instance: Redis Pub/Sub backplane broadcasts across all gateway replicas
- Dead connections are silently pruned on broadcast

## Rate Limiting (`NFR-8`)

Redis-backed distributed rate limiting via slowapi. Three tiers:

| Tier | Default | Applies to |
|------|---------|-----------|
| Public | 60/min | All unauthenticated endpoints |
| Auth | 10/min | Auth endpoints (signup, login, refresh) |
| Booking | 5/min | Seat lock, book, payment endpoints |

Custom limits can be set via `RATE_LIMIT_PUBLIC`, `RATE_LIMIT_AUTH`, `RATE_LIMIT_BOOKING` environment variables.

## Catalog Caching (`FR-4`)

Cache-aside pattern for venue and event listings via `CacheRepository`:

- Venues/events cached with 300s TTL
- Seat map invalidation publishes via Redis Pub/Sub for cross-instance consistency
- All cache operations are failure-tolerant — Redis outages never break API responses

## Data Model

### Key Tables

| Schema | Table | Description |
|--------|-------|-------------|
| `identity` | `users` | User accounts with `is_admin` flag |
| `identity` | `refresh_tokens` | JWT refresh token rotation |
| `booking` | `events` | Events/movies (auto-prefixed IDs: `STM01`, `EVT01`) |
| `booking` | `venues` | Venues with capacity |
| `booking` | `showtimes` | Showtimes linked to event + venue |
| `booking` | `seats` | Individual seats with tier, price, and status |
| `booking` | `bookings` | Booking records (amount = sum of all seats) |
| `booking` | `booking_seats` | Junction table linking bookings to seats (with per-seat price) |
| `booking` | `payments` | Payment records |
| `booking` | `booking_events` | Audit trail for state transitions |
| `booking` | `outbox_events` | Transactional outbox for async publishing |

### Booking Uniqueness

A partial unique index (`unique_pending_booking_per_user_show`) prevents users from having multiple **PENDING** bookings for the same show. Multiple **CONFIRMED** bookings are allowed (multi-seat support).

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | — (required) |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `CORS_ORIGINS` | Comma-separated allowed origins | `http://localhost:5173` |
| `CLIENT_ORIGIN` | Frontend URL for redirects | `http://localhost:5173` |
| `STRIPE_SECRET_KEY` | Stripe secret key (optional) | — |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook secret (optional) | — |
| `GOOGLE_CLIENT_ID` | Google OAuth2 client ID (optional) | — |
| `GOOGLE_CLIENT_SECRET` | Google OAuth2 client secret (optional) | — |
| `SENTRY_DSN` | Sentry error tracking DSN (optional) | — |
| `LOG_LEVEL` | Logging level | `INFO` |
| `LOG_FORMAT` | `json` or `console` | `json` |
| `RATE_LIMIT_PUBLIC` | Public endpoint rate limit | `60/minute` |
| `RATE_LIMIT_AUTH` | Auth endpoint rate limit | `10/minute` |
| `RATE_LIMIT_BOOKING` | Booking endpoint rate limit | `5/minute` |

## Running Tests

```bash
# Backend (unit + integration, requires Postgres + Redis)
cd apps/backend
pytest tests/ -v --tb=long

# Frontend
pnpm --filter @event-ticketing/web lint
pnpm --filter @event-ticketing/web typecheck

# Everything via Turborepo
pnpm test
pnpm lint
pnpm typecheck

# Load test
cd apps/backend
locust -f tests/load/locustfile.py --host http://localhost:8000
```

## Background Workers

All run inside the backend container on startup:

- **Sweeper** (60s) — Reverts expired PENDING bookings and releases seat locks
- **Outbox relay** (5s) — Publishes outbox events via `FOR UPDATE SKIP LOCKED`
- **Queue admitter** (2s) — Admits queued users in FIFO order

## Migrations

| Version | Description |
|---------|-------------|
| 001 | Initial schema — identity + booking tables, indexes |
| 002 | Event type enum + prefixed IDs (`STM`, `EVT`) |
| 003 | Ensure identity sequences exist |
| 004 | Add `is_admin` boolean to `identity.users` |
| 005 | Relax unique constraint — allow multiple CONFIRMED bookings per user per show |
| 006 | Multi-seat booking — `booking_seats` junction table |
| 007 | Add `is_master_admin` to `identity.users` |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Monorepo | Turborepo, pnpm workspaces |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, Framer Motion |
| Framework | FastAPI, Pydantic v2 |
| ORM | SQLAlchemy 2.0 (async) |
| Database | PostgreSQL 16 (asyncpg), Redis 7 |
| Auth | python-jose (RS256), bcrypt, Google OAuth2 |
| Payments | Stripe SDK (card-only intents, webhook auto-confirm, mock-confirm for demo) |
| Real-time | WebSockets, Redis Pub/Sub |
| Caching | Redis cache-aside (venues, events, seat maps) |
| Rate limiting | slowapi (Redis-backed, distributed) |
| Observability | structlog, Sentry, OpenTelemetry, CloudWatch |
| Testing | pytest, Locust |
| CI/CD | GitHub Actions (ruff, mypy, eslint, tsc, pytest) |
| Deploy | Docker Compose, Kubernetes (Kustomize), Terraform (EKS), ArgoCD, ECR |

## CI Checks

All checks must pass before merge:

```bash
# Turborepo (runs all workspace tasks)
pnpm turbo lint
pnpm turbo typecheck
pnpm turbo test

# Or individually
cd apps/backend
ruff check .
mypy core services --ignore-missing-imports
pytest tests/ -v

pnpm --filter @event-ticketing/web lint
pnpm --filter @event-ticketing/web typecheck
```

### GitHub Actions Workflow (`.github/workflows/ci.yml`)

Runs on every push to `main` and on all pull requests.

| Job | Trigger | What it does |
|-----|---------|--------------|
| `backend-lint` | push + PR | `ruff check` + `mypy` |
| `backend-test` | push + PR | `pytest` for identity, booking integration/concurrency, rate limit, payment/webhook suites against Postgres 16 + Redis 7 services |
| `rate-limit-cache-tests` | push + PR | `pytest` for catalog cache + rate limit tests |
| `websocket-tests` | push + PR | `pytest` for websocket manager tests |
| `migration-test` | push + PR | Fresh DB must `alembic upgrade head` + `seed.py` cleanly |
| `frontend-check` | push + PR | `typecheck` + `lint` + `build` for React app (with Stripe publishable key) |
| `docker-build` | push + PR | Builds both ECR images (`--target api` / `--target web`) to mirror `deploy.ps1` |

### Docker Images

Production images are built and pushed to **ECR** (`078682762568.dkr.ecr.us-east-1.amazonaws.com/event-ticketing-{api,web}:main`) by `scripts/deploy.ps1`, then applied + restarted via the `k8s/prod/` overlay. ArgoCD auto-syncs manifest changes from `main`.

## License

MIT
