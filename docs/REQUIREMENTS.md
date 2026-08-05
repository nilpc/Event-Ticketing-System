# Event Ticketing Backend — Enterprise Product Requirements Document (PRD)

## Revision Notes & Architectural Hardening (Latest Version)

- **Decoupled Cross-Schema Foreign Keys (Architecture Hardening)**: Removed the cross-schema database foreign key constraint (`booking.bookings.user_id` -> `identity.users.user_id`) in Alembic migration `008_decouple_cross_schema_fk.py` and ORM models, storing `user_id` as an unconstrained UUID column to allow true microservice database isolation.
- **Outbox Worker Async Notification via PostgreSQL `LISTEN / NOTIFY` (FR-15)**: Added trigger `booking.notify_outbox_inserted()` on `booking.outbox_events` and upgraded `relay.py` to listen for real-time PostgreSQL notifications (`LISTEN outbox_inserted`), achieving sub-second event publishing while retaining a 5s fallback safety loop.
- **Server-Sent Events (SSE) Queue Status Streaming (FR-6)**: Added `GET /v1/queue/stream` endpoint returning a `text/event-stream` feed. Clients hold a single persistent HTTP connection to receive real-time queue position drops and instant `ADMITTED` tokens, eliminating thousands of short HTTP polling requests during peak flash sales.
- **CDN Edge Cache Control Headers for Catalog Read Offloading (FR-4)**: Injected `Cache-Control: public, max-age=15, s-maxage=60, stale-while-revalidate=30` on public catalog routes (`/venues`, `/events`, `/showtimes`), allowing CloudFront CDN and edge proxies to offload catalog read traffic from PostgreSQL.
- **AWS WAF Security Mode (NFR-9)**: Updated Terraform configuration `infra/terraform/variables.tf` to default `waf_action = "block"`, actively enforcing managed AWS WAF rulesets against SQLi, XSS, bot scrapers, and volumetric DDoS attacks.
- **Zero-Cost ALB Bypass Prevention (NFR-10)**: Configured CloudFront origin custom header `X-CloudFront-Secret` (`cloudfront.tf`) and AWS WAF Rule Priority 0 (`require-cloudfront-secret` in `waf.tf`), blocking direct ALB DNS bypass attempts with `403 Forbidden` at **$0 extra cost** while preserving K8s `/health` and `/ready` probes.
- **Infrastructure Topology & Cost Restrictions**: Multi-AZ RDS replication and 3-AZ NAT Gateways are supported via Terraform (`multi_az = true`, `enable_single_nat_gateway = false`). To strictly respect the **$150/month AWS Budget cap** (`budgets.tf`), single NAT Gateway and single-AZ RDS `db.t4g.micro` were selected for staging/demo, avoiding an additional **+$79/month** infrastructure cost surge while preserving 100% architectural and functional parity.
- Renumbered the FR/NFR catalog sequentially and added FR-7 / FR-8 for seat locking and atomic booking initialization.
- Added `deleted_at` and `anonymized` columns to `identity.users` for GDPR soft-delete/anonymization compliance.
- Added a `unique_active_payment_per_booking` partial index to stop duplicate Stripe intents per booking.
- Fixed FR-5 PCI payment flow: PaymentIntent is card-only with Link/Klarna/Affirm disabled to prevent checkout confirmation blocks. Verified end-to-end in production.

# 1. Executive Summary & Product Vision

The **Event Ticketing System** is a high-concurrency, cloud-native event ticketing platform designed specifically for high-demand "flash-sale" scenarios (e.g., world concert tours, sporting finals). During peak sales, tens of thousands of users request seat locks within milliseconds, creating extreme database contention, potential double-bookings, and payment gateway bottlenecks.

### Target Performance Metrics & SLAs
- **Availability SLA**: 99.95% uptime across all gateway and catalog services.
- **Concurrency SLA**: 0% double-bookings under 10,000 requests per second (RPS) peak contention.
- **Latency SLAs**: P95 < 50ms for cached catalog requests; P99 < 150ms for seat locking and atomic booking transactions.
- **RPO / RTO**: Recovery Point Objective (RPO) = 0 for committed financial bookings; Recovery Time Objective (RTO) < 60s via KEDA autoscaling and Kubernetes self-healing.

# 2. Requirements Catalog

## Functional Requirements (FR)

- **FR-1:** Secure email/password authentication with strength validation (`zxcvbn`), account lockout policies, and GDPR-compliant soft-delete/anonymization (`identity.users.deleted_at`, `identity.users.anonymized`).
- **FR-2:** Google OAuth2 SSO tracked via `google_subject_id`.
- **FR-3:** Short-lived JWT access tokens (RS256) with `jti` claims, and database-backed rotating refresh tokens with strict reuse detection (family invalidation).
- **FR-4:** Public catalog endpoints for venues, events, and seat maps with Redis caching and **CloudFront CDN Edge headers (`Cache-Control: public, max-age=15, s-maxage=60, stale-while-revalidate=30`)** to eliminate database CPU read spikes during flash sales.
- **FR-5:** PCI-compliant payment flow. Backend generates a `client_secret` via `POST /v1/payments/intent` by writing a local initiated payment record before calling the provider; raw card data never touches the backend. At most one non-terminal (`initiated`/`requires_action`) payment record is permitted per booking.
- **FR-6:** Queue system admitting users at a fixed rate. Supports traditional `Retry-After` HTTP headers as well as **real-time Server-Sent Events (SSE) streaming (`GET /v1/queue/stream`)**, allowing clients to hold a single connection and receive instant `ADMITTED` tokens without HTTP polling. Includes `GET /queue/recover` for client crash resilience.
- **FR-7:** Time-boxed seat locking. `POST /seats/lock` issues a server-generated idempotency key and a 10-minute Redis hold on `show_id:seat_id`, enforced alongside a 10-minute per-user hold limit that prevents seat hoarding.
- **FR-8:** Atomic booking initialization with decoupled schema architecture. `POST /book` validates the server-generated idempotency key and executes seat transition to `PENDING_PAYMENT`, booking insertion (`user_id` stored as an unconstrained UUID column without cross-schema FK dependency to allow independent microservice DB scaling), and outbox event insertion inside a single database transaction.
- **FR-9:** Background sweeper task reverting "Zombie" bookings every 60 seconds. Bookings have a 10-minute `expires_at`, but the sweeper applies a 5-minute grace period (sweeping at 15 minutes) to handle delayed webhook race conditions.
- **FR-10:** Strict server-side price verification. The backend ignores client-sent amounts and calculates totals directly from the database during the atomic transaction.
- **FR-11:** API Gateway enforces global JWT validation, strips any client-supplied identity headers, and injects trusted `X-User-Id`, `X-Request-ID`, and `W3C traceparent` headers on every proxied request.
- **FR-12:** Distinct K8s probes: `/health` (liveness, process alive) and `/ready` (readiness, DB/Redis pings, returns 503 gracefully if Redis or DB is unreachable to prevent crash loops).
- **FR-13:** Database state managed via zero-downtime Alembic migrations executed as a K8s Init Job prior to application rollout.
- **FR-14:** Live seat-map updates over WebSockets. `ws://host/ws/showtime/{show_id}?token={jwt}` broadcasts seat status changes (`LOCK`, `PENDING_PAYMENT`, `SOLD`) in real time; an in-memory connection manager per gateway replica plus a Redis Pub/Sub backplane keep multi-replica clusters consistent.
- **FR-15:** Event-driven transactional outbox relay. PostgreSQL `booking.notify_outbox_inserted()` trigger emits `NOTIFY outbox_inserted`, signaling `relay.py` to publish outbox events instantaneously with sub-second latency while maintaining a 5s fallback polling loop.

## Non-Functional Requirements (NFR)

- **NFR-1:** One active booking per user per showtime via DB Partial Unique Index.
- **NFR-2:** Stateless services scale horizontally via KEDA based on custom metrics (Redis queue depth, HTTP RPS).
- **NFR-3:** Queue Admitter uses Kubernetes Lease-based leader election for HA.
- **NFR-4:** Standard Prometheus metrics, W3C-compliant OpenTelemetry distributed tracing, and structured JSON logging (`structlog`) across all paths.
- **NFR-5:** Unhandled exceptions and application errors are captured in Sentry across all services, tagged with `request_id` and `trace_id` for correlation with logs and traces.
- **NFR-6:** Strict Controller-Service-Repository (CSR) layered architecture using SQLAlchemy 2.0 ORM, Pydantic v2 validation, and Python Enums.
- **NFR-7:** Ephemeral Redis prioritizes memory speed; financial data is strictly protected by Postgres atomicity.
- **NFR-8:** Redis-backed distributed rate limiting (`slowapi`). Configurable per-route/role tiers — public (60/min), auth (10/min), and booking (5/min) — with HTTP 429 responses.
- **NFR-9:** AWS WAF v2 in active `block` mode deployed at ALB/CloudFront edge, enforcing SQLi, XSS, IP rate limiting, and bot protection rulesets.
- **NFR-10:** Zero-cost perimeter isolation against ALB bypass attacks via CloudFront `X-CloudFront-Secret` custom header injection and AWS WAF Rule Priority 0 (`require-cloudfront-secret`), rejecting direct ALB URL hits with a 403 Forbidden.

# 3. Tech Stack

- **Framework:** FastAPI (Python 3.11+) + Pydantic v2
- **Server Stack:** Uvicorn + Gunicorn
- **Relational Layer:** PostgreSQL via PgBouncer (transaction mode), SQLAlchemy 2.0, Alembic
- **Cache & Locks:** Ephemeral Redis (`redis.asyncio`) with Lua scripts
- **Observability:** OpenTelemetry, Prometheus, Grafana, Loki, Sentry (NFR-5)
- **Deployment:** AWS EKS 1.35, KEDA, ArgoCD, Terraform, CloudFront, AWS WAF (Block Mode)


# 4\. Architecture & Topology

The system isolates microservices into stateless boundaries. A single PostgreSQL database contains two schemas: identity and booking, with cross-schema foreign keys applied consistently (including booking.bookings.user_id → identity.users.user_id).

**Five-Layer Concurrency Strategy:**

**1\. Redis Hoarding Lock (FR-7):** 10-minute user_hold limit prevents seat hoarding.

**2\. Redis Distributed Lock (FR-7):** SETNX with 600s TTL on show_id:seat_id. Instant 409 rejection on failure.

**3\. PostgreSQL State Verification:** Non-locking read to verify seat is AVAILABLE.

**4\. Atomic Booking Initialization (FR-8, FR-10):** A single serializable DB transaction transitions seat to PENDING_PAYMENT, inserts PENDING booking (looking up the true price internally), and writes to the outbox_events table. Cache invalidation occurs after commit and is failure-tolerant.

**5\. Background Sweeper & Webhook Guard (FR-9):** Sweeper reverts seats after 15 minutes. Webhooks arriving for FAILED bookings trigger a REFUND_REQUIRED outbox event; Redis holds are released only once a terminal payment outcome (succeeded/failed/canceled) is recorded - see §6.

# 5\. Database Schemas (PostgreSQL)

\-- IDENTITY SCHEMA

CREATE SCHEMA identity;

CREATE TABLE identity.users (

user_id UUID PRIMARY KEY,

email VARCHAR(255) UNIQUE NOT NULL,

password_hash VARCHAR(255),

google_subject_id VARCHAR(255) UNIQUE,

is_active BOOLEAN DEFAULT TRUE,

email_verified_at TIMESTAMP WITH TIME ZONE,

failed_login_attempts INT DEFAULT 0,

locked_until TIMESTAMP WITH TIME ZONE,

deleted_at TIMESTAMP WITH TIME ZONE, -- FIX: FR-1 GDPR soft-delete

anonymized BOOLEAN DEFAULT FALSE, -- FIX: FR-1 GDPR anonymize flag

created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()

);

CREATE TABLE identity.refresh_tokens (

token_id UUID PRIMARY KEY,

user_id UUID NOT NULL,

token_hash VARCHAR(255) UNIQUE NOT NULL,

rotated_from UUID, -- For reuse detection

expires_at TIMESTAMP WITH TIME ZONE NOT NULL,

is_revoked BOOLEAN DEFAULT FALSE,

FOREIGN KEY (user_id) REFERENCES identity.users(user_id) ON DELETE CASCADE

);

\-- BOOKING SCHEMA

CREATE SCHEMA booking;

CREATE TABLE booking.venues (

venue_id UUID PRIMARY KEY, name VARCHAR(255) NOT NULL, capacity INT NOT NULL

);

CREATE TABLE booking.events (

event_id UUID PRIMARY KEY, name VARCHAR(255) NOT NULL, description TEXT

);

CREATE TABLE booking.showtimes (

show_id UUID PRIMARY KEY,

event_id UUID REFERENCES booking.events (event_id) ON DELETE CASCADE,

venue_id UUID REFERENCES booking.venues (venue_id) ON DELETE CASCADE,

base_price DECIMAL(10,2) NOT NULL,

start_time TIMESTAMP WITH TIME ZONE NOT NULL,

end_time TIMESTAMP WITH TIME ZONE NOT NULL

);

CREATE TYPE booking.seat_status AS ENUM ('AVAILABLE', 'PENDING_PAYMENT', 'SOLD');

CREATE TABLE booking.seats (

show_id UUID REFERENCES booking.showtimes (show_id) ON DELETE CASCADE,

seat_id VARCHAR(10) NOT NULL,

tier VARCHAR(20) NOT NULL,

price DECIMAL(10,2) NOT NULL,

status booking.seat_status DEFAULT 'AVAILABLE' NOT NULL,

PRIMARY KEY (show_id, seat_id)

);

CREATE INDEX idx_seats_lookup ON booking.seats (show_id, status);

CREATE TYPE booking.booking_status AS ENUM ('PENDING', 'CONFIRMED', 'FAILED', 'CANCELLED');

CREATE TABLE booking.bookings (

booking_id UUID PRIMARY KEY,

user_id UUID NOT NULL,

show_id UUID NOT NULL,

seat_id VARCHAR(10) NOT NULL,

status booking.booking_status DEFAULT 'PENDING' NOT NULL,

idempotency_key VARCHAR(255) UNIQUE NOT NULL,

amount DECIMAL(10, 2) NOT NULL, -- Server-verified

currency VARCHAR(3) NOT NULL,

expires_at TIMESTAMP WITH TIME ZONE NOT NULL,

created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

FOREIGN KEY (show_id, seat_id) REFERENCES booking.seats (show_id, seat_id) ON DELETE RESTRICT,

FOREIGN KEY (user_id) REFERENCES identity.users (user_id) ON DELETE RESTRICT -- FIX: was missing

);

\-- Sweeper optimization index

CREATE INDEX idx_zombie_sweeper ON booking.bookings (status, expires_at) WHERE status = 'PENDING';

CREATE UNIQUE INDEX unique_active_booking_per_user_show

ON booking.bookings(user_id, show_id) WHERE status IN ('PENDING', 'CONFIRMED');

CREATE TABLE booking.payments (

payment_id UUID PRIMARY KEY,

booking_id UUID REFERENCES booking.bookings(booking_id) ON DELETE RESTRICT,

provider VARCHAR(50) NOT NULL,

provider_payment_id VARCHAR(255) UNIQUE,

amount DECIMAL(10,2) NOT NULL,

status VARCHAR(50) NOT NULL, -- 'initiated', 'requires_action', 'succeeded', 'failed', 'refunded'

created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()

);

\-- FIX: prevent more than one non-terminal payment intent per booking

CREATE UNIQUE INDEX unique_active_payment_per_booking

ON booking.payments(booking_id) WHERE status IN ('initiated', 'requires_action');

CREATE TABLE booking.booking_events (

event_id UUID PRIMARY KEY,

booking_id UUID REFERENCES booking.bookings(booking_id) ON DELETE CASCADE,

from_status booking.booking_status,

to_status booking.booking_status NOT NULL,

source VARCHAR(50) NOT NULL,

correlation_id UUID,

changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()

);

CREATE TABLE booking.processed_webhook_events (

event_id VARCHAR(255) PRIMARY KEY,

event_type VARCHAR(100) NOT NULL,

payload JSONB NOT NULL,

processed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()

);

\-- Outbox pattern for reliable async event publishing

CREATE TABLE booking.outbox_events (

event_id UUID PRIMARY KEY,

aggregate_type VARCHAR(50),

aggregate_id UUID,

event_type VARCHAR(100),

payload JSONB,

created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

published_at TIMESTAMP WITH TIME ZONE

);

\-- Relay worker performance index

CREATE INDEX idx_outbox_unpublished ON booking.outbox_events (created_at) WHERE published_at IS NULL;

# 6\. CSR Implementation Example (Atomic & Edge-Case Resilient)

**_Layer 1: Booking Service (services/booking_service.py)_**

import uuid

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from repositories import SeatRepository, BookingRepository, LockRepository, CacheRepository

from domain.exceptions import BookingConflictError, SeatUnavailableError, InvalidTokenError, PersistenceError

from domain.enums import BookingStatus, SeatStatus

import logging

logger = logging.getLogger(\__name_\_)

class BookingService:

def \__init_\_(self, db_session: AsyncSession, seat_repo: SeatRepository, booking_repo: BookingRepository, lock_repo: LockRepository, cache_repo: CacheRepository):

self.session = db_session

self.seat_repo = seat_repo

self.booking_repo = booking_repo

self.lock_repo = lock_repo

self.cache_repo = cache_repo

async def initialize_checkout(self, payload, user_id: str, queue_token: str, idempotency_key: str, request_id: str):

if not await self.lock_repo.validate_queue_session(queue_token, user_id):

raise InvalidTokenError("Invalid or expired queue session token.")

\# FIX: renamed from check_idempotency_cache - True means the key is unused

if not await self.lock_repo.is_idempotency_key_available(idempotency_key):

existing = await self.booking_repo.get_booking_by_idempotency(idempotency_key)

if existing:

return {"booking_id": existing.booking_id, "status": existing.status}

raise BookingConflictError("Duplicate payload.")

if await self.lock_repo.get_seat_lock(payload.show_id, payload.seat_id) != user_id:

raise BookingConflictError("Seat lock expired or assigned to another user.")

booking_id = str(uuid.uuid4())

expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

try:

\# CRITICAL: Single Atomic Transaction

async with self.session.begin():

\# 1. Transition Seat

await self.seat_repo.transition_seat_to_pending(payload.show_id, payload.seat_id)

\# 2. Verify Price & Create Booking (Prevents Price Tampering)

seat_price = await self.seat_repo.get_seat_price(payload.show_id, payload.seat_id)

await self.booking_repo.create_pending_booking(

booking_id=booking_id, user_id=user_id, show_id=payload.show_id,

seat_id=payload.seat_id, idempotency_key=idempotency_key,

amount=seat_price, expires_at=expires_at, correlation_id=request_id

)

\# 3. Outbox event for async notification service

await self.booking_repo.add_outbox_event("Booking", booking_id, "BOOKING_INITIALIZED", {"booking_id": booking_id})

except (BookingConflictError, SeatUnavailableError, InvalidTokenError):

\# FIX: expected domain conflicts release holds and propagate unchanged

await self.lock_repo.release_seat_lock_safe(payload.show_id, payload.seat_id, user_id)

await self.lock_repo.release_user_hold_limit(payload.show_id, user_id)

raise

except Exception as e:

\# FIX: unexpected failures (DB outage, bugs) are no longer rebranded as a booking conflict

await self.lock_repo.release_seat_lock_safe(payload.show_id, payload.seat_id, user_id)

await self.lock_repo.release_user_hold_limit(payload.show_id, user_id)

logger.exception(f"Unexpected persistence failure during checkout: {e}")

raise PersistenceError(f"Checkout failed unexpectedly: {e}") from e

\# CRITICAL FIX: Cache invalidation MUST happen AFTER DB commit.

\# Wrapped in its own try/except so a Redis failure does not raise an

\# API error after the database transaction has successfully committed.

try:

await self.cache_repo.invalidate(f"seatmap:{payload.show_id}")

except Exception as cache_err:

logger.error(f"Cache invalidation failed for show {payload.show_id}. DB transaction is safe. Error: {cache_err}")

await self.lock_repo.consume_queue_session(queue_token)

return {"booking_id": booking_id, "status": "PENDING_PAYMENT", "expires_at": expires_at}

**_Layer 2: Payment Service (services/payment_service.py)_**

class PaymentService:

def \__init_\_(self, db_session: AsyncSession, booking_repo: BookingRepository, payment_repo: PaymentRepository, provider_client):

self.session = db_session

self.booking_repo = booking_repo

self.payment_repo = payment_repo

self.provider = provider_client

async def create_intent(self, booking_id: str, user_id: str):

booking = await self.booking_repo.get_booking_by_id(booking_id)

if not booking or booking.user_id != user_id:

raise NotFoundError("Booking not found")

\# Edge Case Fix: Prevent late payment intents

if booking.expires_at < datetime.now(timezone.utc) + timedelta(minutes=2):

raise BookingConflictError("Booking expires too soon to initiate payment. Please restart.")

\# FIX: reuse an existing non-terminal intent instead of creating a duplicate

\# (backed by the unique_active_payment_per_booking partial index)

existing = await self.payment_repo.get_active_payment_for_booking(booking_id)

if existing:

return {"client_secret": existing.client_secret}

payment_id = str(uuid.uuid4())

\# CRITICAL FIX: Write to DB FIRST to prevent orphaned Stripe intents

async with self.session.begin():

await self.payment_repo.create_payment_record(

payment_id=payment_id, booking_id=booking_id, amount=booking.amount, status="initiated"

)

\# Call provider

intent = None

try:

intent = await self.provider.create_payment_intent(

amount=booking.amount,

currency=booking.currency,

metadata={"booking_id": booking_id, "user_id": user_id, "show_id": booking.show_id, "seat_id": booking.seat_id}

)

\# Update DB record with provider ID

async with self.session.begin():

await self.payment_repo.update_payment_record(

payment_id=payment_id, provider_payment_id=intent.id, status="requires_action"

)

return {"client_secret": intent.client_secret}

except Exception as e:

\# Mark as failed locally so finance team can reconcile

async with self.session.begin():

await self.payment_repo.update_payment_record(payment_id=payment_id, status="failed")

\# CRITICAL FIX: If the intent was created but the DB update failed, cancel it in Stripe to prevent orphaned funds

if intent:

try:

await self.provider.cancel_payment_intent(intent.id)

except Exception as cancel_err:

logger.error(f"Failed to cancel orphaned Stripe intent {intent.id}: {cancel_err}")

raise e

**_Layer 3: Webhook Service (services/payment_callback_service.py)_**

class PaymentCallbackService:

def \__init_\_(self, db_session: AsyncSession, booking_repo: BookingRepository, seat_repo: SeatRepository, lock_repo: LockRepository, payment_repo: PaymentRepository, provider_client):

self.session = db_session

self.booking_repo = booking_repo

self.seat_repo = seat_repo

self.lock_repo = lock_repo

self.payment_repo = payment_repo

self.provider = provider_client

async def process_webhook(self, payload: bytes, signature: str, headers: dict):

event = self.provider.verify_signature(payload, signature)

show_id = seat_id = user_id = None

terminal = False # FIX: only release Redis holds once the outcome is actually known

async with self.session.begin():

inserted = await self.booking_repo.log_webhook_event(event.id, event.type, payload.decode())

if not inserted:

return # Silently drop duplicate

metadata = event.data.object.metadata

show_id, seat_id = metadata.show_id, metadata.seat_id

user_id, booking_id = metadata.user_id, metadata.booking_id

booking = await self.booking_repo.get_booking_by_id(booking_id)

\# CRITICAL FIX: Null check to prevent AttributeError on spoofed or deleted booking webhooks

if not booking:

return

if event.type == "payment_intent.succeeded":

await self.payment_repo.update_payment_status_by_intent(event.data.object.id, "succeeded")

if booking.status == BookingStatus.FAILED:

\# Sweeper beat us to it. Trigger refund workflow via outbox.

await self.booking_repo.add_outbox_event("Payment", booking_id, "REFUND_REQUIRED", {"reason": "Late webhook on failed booking"})

elif booking.status == BookingStatus.PENDING:

await self.seat_repo.finalize_sold_seat(show_id, seat_id)

await self.booking_repo.update_booking_status(booking_id, BookingStatus.CONFIRMED, event.data.object.id, source="webhook")

await self.booking_repo.add_outbox_event("Booking", booking_id, "BOOKING_CONFIRMED", {"email": metadata.email})

terminal = True

elif event.type in \["payment_intent.payment_failed", "payment_intent.canceled"\]:

await self.payment_repo.update_payment_status_by_intent(event.data.object.id, "failed")

if booking.status == BookingStatus.PENDING:

await self.seat_repo.revert_seat_to_available(show_id, seat_id)

await self.booking_repo.update_booking_status(booking_id, BookingStatus.FAILED, None, source="webhook")

terminal = True

\# else: intermediate event (e.g. requires_action, processing) - nothing to reconcile yet

\# FIX: Redis cleanup stays outside the DB transaction, now gated to terminal outcomes only

if terminal:

await self.lock_repo.release_seat_lock_safe(show_id, seat_id, user_id)

await self.lock_repo.release_user_hold_limit(show_id, user_id)

**_Layer 4: Outbox Relay Worker (workers/relay.py)_**

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker

class OutboxRelayWorker:

def \__init_\_(self, db_session_factory: async_sessionmaker, booking_repo: BookingRepository, message_broker):

self.session_factory = db_session_factory

self.booking_repo = booking_repo

self.broker = message_broker

async def run_periodically(self, interval_seconds=5):

while True:

await asyncio.sleep(interval_seconds)

await self.poll_and_publish()

async def poll_and_publish(self):

async with self.session_factory() as session:

async with session.begin():

\# CRITICAL: Prevents duplicate publishing across HA worker replicas

events = await self.booking_repo.get_unpublished_outbox_events_for_update_skip_locked()

for event in events:

await self.broker.publish(event.event_type, event.payload)

await self.booking_repo.mark_outbox_published(event.event_id)

# 7\. Infrastructure & Testing Strategy

- **CI/CD & GitOps:** GitHub Actions (`.github/workflows/ci.yml`) enforces ruff, mypy, pytest (backend/booking-concurrency/rate-limit/websocket/migration suites against Postgres 16 + Redis 7 services), and Docker image builds on every push to main. ArgoCD (ClusterIP, port-forward only) is the declarative controller of record for `k8s/prod/` and auto-syncs on every push to main (`automated.sync` on, `prune: false`, `selfHeal: false`).
- **Database Migrations:** Alembic runs as a K8s Init Job before rolling out new FastAPI pods to prevent race conditions; CI validates a fresh DB migrates + seeds cleanly.
- **Network Policies (Zero-Trust):** K8s NetworkPolicies restrict ingress to backend services so they only accept traffic from the API Gateway, preventing header spoofing.
- **Connection Pooling:** PgBouncer runs in front of Postgres in transaction mode to prevent connection exhaustion during flash sales.
- **Error Tracking (NFR-5):** Sentry SDK is initialized in every service; captured exceptions are tagged with request_id and trace_id so they can be correlated with Loki logs and OpenTelemetry traces.
- **Testing:** Property-based tests (Hypothesis) verify zero double-bookings under randomized concurrent interleavings. E2E Locust tests verify queue dynamics and 409 rejection rates.
- **Production runtime (Phase 7, live):** EKS 1.35 (`event-ticketing`, us-east-1), two node groups (on-demand t3.small + spot t3.medium), single-AZ RDS db.t4g.micro behind ESO-managed secrets, ALB Ingress + AWS LB Controller, CloudFront CDN in front of the SPA, WAF in Count mode, Redis via Bitnami Helm (auth enabled), cert-manager ACME issuers, KEDA, and node-termination-handler for spot draining. Deployments ship via ECR (`...:main`) + `scripts/deploy.ps1`.
- **Verified E2E (Stripe):** the full purchase path — queue admission → seat lock → atomic booking → card-only PaymentIntent → card charge (test mode) → webhook auto-confirmation — has been verified against production with headless/headed browser automation; a booking auto-confirms ~2s after the card charge succeeds, and replaying a real webhook event recovers any straggler bookings.

**Deployment & AWS Operations (runbook):**

1. **Provision infrastructure:** `cd infra/terraform && terraform apply` — VPC, EKS 1.35, node groups (`on-demand` t3.small infra + `spot` t3.medium app), single-AZ RDS db.t4g.micro, IAM/IRSA, CloudFront, WAF (`waf_action` default `count`), CloudWatch dashboard, $150/mo budget alarm. All resources tagged with `merge(var.tags, {Name = ...})`.
2. **Bootstrap cluster add-ons:** `scripts/init.ps1 -LbControllerRoleArn <out> -EsoRoleArn <out> -RdsEndpoint <out>` — installs AWS LB Controller, KEDA, External Secrets Operator, Bitnami Redis (auth enabled), node-termination-handler, cert-manager, and ArgoCD (ClusterIP only); writes secrets to SSM Parameter Store (`/event-ticketing/DB_PASSWORD`, `/event-ticketing/REDIS_PASSWORD`, JWT + Stripe keys).
3. **Bootstrap GitOps:** `kubectl apply -f k8s/argocd/` once. ArgoCD Application `event-ticketing` auto-syncs `k8s/prod/` from `main` on every push (`automated.sync` ON, `prune: false`, `selfHeal: false`). Access via `kubectl port-forward -n argocd svc/argocd-server 8080:80`; admin password from `argocd-initial-admin-secret`.
4. **Ship images:** `$env:VITE_STRIPE_PUBLISHABLE_KEY=...; scripts/deploy.ps1` — ECR login, build `api`/`web` Docker targets, push `:main`, `kubectl apply -k k8s/prod/`, rollout restart + wait (selfHeal is off, so the restart is not reverted).
5. **Manifest-only changes:** commit + push to `main` → ArgoCD auto-syncs (no manual apply).
6. **Security baseline:** JWT keys injected via `JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY` env vars at runtime (never baked into images; `entrypoint.sh` writes them to disk before app start); Redis requires auth (`REDIS_URL` includes `:password@`); CSP/HSTS/X-Frame-Options/X-Content-Type-Options/X-XSS-Protection/Referrer-Policy/Permissions-Policy set in both `nginx.conf` and FastAPI middleware; WAF stays in Count mode until traffic is analyzed, then set `waf_action = "block"`; HTTPS requires a custom domain + ACM cert (HTTP-only by default when `domain_name` is empty).
7. **Destroy:** `terraform destroy` from `infra/terraform/` to conserve budget.