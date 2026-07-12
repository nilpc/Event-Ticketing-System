Event Ticketing Backend - Phased Build Plan

## Revision Notes (this version)

- Added Phase 2.2, Google OAuth2 SSO (FR-2) - this requirement previously had no corresponding task anywhere in the plan.
- Split the old Phase 4.1 into two steps: gateway identity enforcement (FR-11: JWT validation, header stripping, X-User-Id injection) and W3C tracing, since only tracing was previously covered.
- Renamed "UC-6" / "UC-7" to FR-7 / FR-8 so seat locking and atomic booking initialization trace back to the requirements catalog.
- Fixed the Phase 1 migration bullet: the showtimes column is base_price, not price (only seats.price is named price).
- Added a Phase 1 migration bullet for the identity.users GDPR columns and the bookings → identity FK.
- Added a Phase 1 migration bullet and a Phase 2.5 note for the unique_active_payment_per_booking index, so a duplicate request reuses an intent instead of creating a second Stripe charge.
- Added a Sentry deployment step to Phase 6 (NFR-5) - it was listed in the tech stack with no task behind it.
- Added a "Terminal-Only Cleanup" bullet to Phase 4's webhook step so Redis locks are released only on succeeded/failed/canceled, not on every webhook event type.
- Updated FR/NFR citations throughout to match the renumbered catalog in Requirement.docx.
- Tagged Phase 4.2 (Routing & W3C Tracing) with FR-11 - it implements the X-Request-ID/traceparent half of that requirement, which previously had no FR-11-tagged task behind it.
- Tagged Phase 5.4 (Scaling Configuration) with NFR-2 and Phase 1.2 (Scaffold Repositories) with NFR-6 - both requirements were implemented but previously untracked in this plan.

**Phase 1: Foundation & Data Layer**

_Before writing application logic, establish the stateful backends, ORM models, and strict transactional boundaries._

**1\. Provision Cloud PostgreSQL & PgBouncer:** Create a Neon database. Create two schemas: identity and booking. Deploy PgBouncer in transaction mode.

**2\. Scaffold Repositories (SRP, NFR-6):** Set up Python project structures using SQLAlchemy 2.0 ORM models (no raw SQL). Separate SeatRepository, BookingRepository, LockRepository, PaymentRepository, and CacheRepository.

**3\. Write Migrations (FR-13):** Configure Alembic for zero-downtime migrations.

- Implement Partial Unique Index on bookings(user_id, show_id) WHERE status IN ('PENDING', 'CONFIRMED') (NFR-1).
- Add expires_at to bookings and idx_zombie_sweeper composite index.
- Add idx_outbox_unpublished partial index to outbox_events for relay worker performance.
- Add base_price to showtimes and price to seats.
- Add deleted_at and anonymized to identity.users, and add the foreign key from bookings.user_id to identity.users(user_id) (FR-1).
- Create payments, outbox_events, and processed_webhook_events (with payload JSONB) tables.
- Add unique_active_payment_per_booking partial index to payments so a duplicate request can't create a second non-terminal Stripe intent (FR-5).

**Phase 2: Identity, Catalog & Payment Foundations**

_Build foundational microservices allowing users to enter the system, authenticate, and initiate payments securely._

**1\. Identity Service (Auth & Security) (FR-1):** FastAPI endpoints for signup/login. Add password strength validation (zxcvbn), account lockout, and GDPR-compliant soft-delete/anonymization.

**2\. Google OAuth2 SSO (FR-2):** Implement the OAuth2 authorization-code flow against Google. Create or link an identity.users record via google_subject_id, including account-linking for a user who already has a password-based account under the same email.

**3\. Session Management (FR-3):** Issue RS256 JWTs with jti claims. Manage DB-backed rotating refresh tokens. Implement strict reuse detection: if a revoked token is used, invalidate the entire rotated_from chain.

**4\. Catalog Endpoints (FR-4):** Public routes for events/showtimes. Implement Redis caching with short TTLs and write-through invalidation (post-commit).

**5\. Payment Intent Endpoint (FR-5):** Implement POST /v1/payments/intent. Ensure strict PCI compliance.

- Write an initiated record to the payments table before calling Stripe. If Stripe succeeds, update the record. If Stripe fails, mark the record as failed.
- If DB update fails after Stripe intent creation, cancel the Stripe intent to prevent orphans.
- Reject intents if the booking's expires_at is less than 2 minutes away.
- Enforce unique_active_payment_per_booking: a repeated request against an existing non-terminal payment reuses that intent rather than creating a second one.

**Phase 3: The Concurrency Engine & Atomic Checkout**

_Build the mechanics that prevent double-booking, ensure data integrity, and handle flash-sale loads._

**1\. Queue System & Crash Recovery (FR-6):** Implement POST /queue/join, GET /queue/status (with Retry-After), and GET /queue/recover (allows clients to resume active sessions if their browser crashes).

**2\. Queue Admitter (HA) (NFR-3):** Implement the background worker using Kubernetes Lease-based leader election so multiple replicas can run, but only one actively admits users.

**3\. Seat Locking (FR-7):** Implement POST /seats/lock. Enforce 10-min Redis user_hold_limit. Server generates the idempotency_key here, stores it in Redis, and returns it to the client.

**4\. Atomic Booking Initialization (FR-8):** Implement POST /book.

- Validate the server-generated idempotency key.
- CRITICAL: Execute seat transition to PENDING_PAYMENT, booking insertion, and outbox event insertion inside a single async with session.begin(): block.
- Price Tampering Fix (FR-10): Ignore client-sent amounts. The backend must look up the price from the seats table during the transaction to calculate amount.
- Cache Fix: Execute cache_repo.invalidate() strictly after the transaction block closes, wrapped in its own try/except so Redis failures do not cause API errors post-commit.

**Phase 4: API Gateway, Webhooks & Background Workers**

_Unify the system behind a single entry point and handle asynchronous state changes safely._

**1\. Identity Enforcement (FR-11):** Set up the FastAPI Gateway to validate the JWT on every proxied request, strip any client-supplied identity headers (e.g. X-User-Id, X-Roles), and inject the trusted X-User-Id derived from the validated token.

**2\. Routing & W3C Tracing (FR-11):** Reverse-proxy requests. Inject X-Request-ID for logs, and generate and inject W3C traceparent headers so OpenTelemetry can stitch traces across services.

**3\. Zero-Trust Network:** Implement K8s NetworkPolicies restricting ingress to backend services exclusively from the API Gateway.

**4\. Transactional Webhooks:** Implement unauthenticated webhook receiver.

- CRITICAL: Execute webhook log insertion, payments table status update, seat finalization, and booking status update inside a single serializable transaction.
- Late Webhook Guard: If a webhook arrives for a booking already marked FAILED by the sweeper, trigger a REFUND_REQUIRED outbox event instead of modifying seat state.
- Null Check Guard: If a webhook arrives for a non-existent booking, return early after logging the event to prevent AttributeError crashes.
- Terminal-Only Cleanup: Release the Redis seat lock and user hold limit only after a terminal outcome (succeeded / failed / canceled) is recorded for the booking - never on an intermediate webhook event type.

**5\. Background Workers:**

- **Sweeper:** Reverts PENDING bookings older than 15 minutes (providing a 5-minute grace period for delayed webhooks) (FR-9).
- **Outbox Relay:** Polls outbox_events using SELECT ... FOR UPDATE SKIP LOCKED to ensure exactly-once publishing to the message broker across HA worker replicas.

**Phase 5: Minikube Containerization & Orchestration**

_Move the system into the Kubernetes sandbox with production-grade configurations._

**1\. Dockerize:** Write lightweight Dockerfiles for Gateway, Identity, Booking, Sweeper, Relay, and Admitter, served via Gunicorn with Uvicorn workers.

**2\. K8s Manifests (Kustomize):** Write base manifests with explicit CPU/Memory requests/limits. Add PodDisruptionBudgets and podAntiAffinity.

**3\. Probes (FR-12):** Implement /health (liveness, returns 200 if process alive) and /ready (readiness, returns 503 gracefully if Redis/DB are unreachable to prevent K8s crash loops).

**4\. Scaling Configuration (NFR-2):** Use KEDA for HPA based on Redis queue depth and HTTP RPS.

**5\. Database Migrations (FR-13):** Deploy Alembic as an InitContainer Job in the FastAPI Deployment to ensure migrations run sequentially before app startup.

**Phase 6: Observability, Testing & CI/CD**

_Prove the system works under pressure and automate the development lifecycle._

**1\. CI/CD Pipeline:** GitHub Actions running ruff, mypy, pytest (unit + integration via testcontainers), and trivy container scanning. Block PR merges on failure.

**2\. Observability Suite (NFR-4, NFR-5):** Deploy kube-prometheus-stack and Loki via Helm. Implement structured JSON logging (structlog) injecting request_id and trace_id. Initialize the Sentry SDK in every service so unhandled exceptions are captured and tagged with the same request_id/trace_id.

**3\. Grafana Dashboards:** Track booking write rates, 409 rejection rates, queue depth, DB connection pool usage, and Sweeper revert rates.

**4\. Advanced Load Testing (Locust):** Simulate thousands of fans hitting /queue/join, respecting Retry-After, securing holds, and initializing checkouts.

- **Disclaimer:** Document that Minikube is for functional concurrency validation; true throughput benchmarking happens in EKS.

**5\. Concurrency Verification:** Run property-based tests verifying that under 10,000 randomized concurrent requests, zero double-bookings occur.

**Phase 7: The EKS Finale (The Demo)**

_Translate the proven local system to the real cloud for portfolio validation._

**1\. Provision AWS Infrastructure:** Use Terraform to spin up EKS with Spot Instances for cost optimization.

**2\. Cloud-Native Add-ons:** Install AWS Load Balancer Controller, External Secrets Operator (ESO), and ArgoCD. Configure IRSA so ESO pulls DB creds from AWS SSM Parameter Store.

**3\. GitOps Deployment:** Push K8s manifests to Git. ArgoCD syncs the prod overlay to the EKS cluster automatically.

**4\. Deploy & Test:** Run the Locust test against the public ALB URL. Verify KEDA scales the booking pods dynamically based on queue depth.

**5\. Capture & Destroy:** Screenshot Grafana dashboards, OpenTelemetry traces, and ArgoCD UI for your technical write-up. Destroy the cluster via Terraform to conserve budget.