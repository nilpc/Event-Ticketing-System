Event Ticketing Backend - Phased Build Plan

## Revision Notes (this version)

- Maintained source of truth in [`docs/REQUIREMENTS.md`](REQUIREMENTS.md) (Enterprise PRD & Requirement Contract) and [`docs/PHASES.md`](PHASES.md) (Build Roadmap & Release Plan).

- Added a Build Status tracker and per-phase status/What-Was-Built notes reflecting the current state of the project (all 7 original phases + the two feature additions are implemented and Phase 7 is live in AWS).
- Added Phase 8 "Rate Limiting & Advanced Caching" (previously FEATURE-2-RATE-LIMIT-CACHE.md, now **NFR-8**) and Phase 9 "WebSocket Live Seat Updates" (previously FEATURE-3-WEBSOCKET.md, now **FR-14**). Both were already shipped in code; the feature docs existed only as proposals.
- Added a "What We've Done So Far" section recording the Phase 7 go-live and the production checkout fixes (webhook StripeObject metadata bug, CSP blocking Stripe.js, Stripe Link blocking card confirmation).

## Build Status

| Phase | Area | Status |
|-------|------|--------|
| 1 | Foundation & Data Layer | Complete |
| 2 | Identity, Catalog & Payment Foundations | Complete |
| 3 | The Concurrency Engine & Atomic Checkout | Complete |
| 4 | API Gateway, Webhooks & Background Workers | Complete |
| 5 | Minikube Containerization & Orchestration | Complete |
| 6 | Observability, Testing & CI/CD | Complete |
| 7 | The EKS Finale (The Demo) | Complete — **LIVE** |
| 8 | Rate Limiting & Advanced Caching (NFR-8) | Complete |
| 9 | WebSocket Live Seat Updates (FR-14) | Complete |
| 10 | Architecture Hardening & Scale Optimizations | Complete |
| 11 | High-Capacity Venues & 3-Tier Pricing | Complete |
## What We've Done So Far

- **Local dev**: Minikube cluster runs the full stack (gateway, api, web, sweeper, relay, admitter, migration job) with local Postgres/Redis; Docker Compose quick-start for one-command bring-up with auto-migration + auto-seed.
- **AWS EKS (Phase 7) is live.** Terraform provisions VPC, EKS 1.35 (`event-ticketing`), two node groups (on-demand t3.small infra + spot t3.medium app), single-AZ RDS db.t4g.micro, IAM/IRSA roles, CloudWatch dashboard, budget alarm ($150/mo). `scripts/init.ps1` installs the AWS Load Balancer Controller, KEDA, External Secrets Operator, Bitnami Redis (auth enabled), node-termination-handler, cert-manager, and ArgoCD; secrets (DB password, Redis password, JWT keys, Stripe keys) are generated and stored in SSM Parameter Store and fetched via ESO.
- **GitOps**: ArgoCD (ClusterIP, `automated.sync`, no prune/selfHeal) is the controller of record for `k8s/prod/`; `kubectl apply -f k8s/argocd/` bootstraps it. Manifest updates ship by pushing to `main`; image updates ship via `scripts/deploy.ps1` (build → push `:main` to ECR → `kubectl apply -k` → rollout restart).
- **Production checkout fixed + verified end-to-end.** Three real production bugs were found and fixed while validating the demo: (1) the webhook handler called `metadata.get(...)` on a real Stripe `StripeObject` (no `.get()` → HTTP 500 on every webhook); (2) the CSP blocked `js.stripe.com`/`api.stripe.com` so Stripe.js never loaded and the Pay button was stuck; (3) Stripe Link wallet phone-validation blocked `confirmPayment` — fixed by making the PaymentIntent card-only and disabling Link in the PaymentElement. Verified with automated browser testing: a card charge on `https://d15zml7hjfgs6j.cloudfront.net` succeeds and the booking auto-confirms via webhook in ~2s.
- **Tests**: backend unit + integration suites (identity, booking, concurrency, cache, rate limit, websocket, payment) run against Postgres 16 + Redis 7 in GitHub Actions; 16 payment/webhook tests pass locally.

## Revision Notes (earlier versions)

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

**Status: ✅ Complete.** Two Postgres schemas (`identity`, `booking`) with cross-schema FKs; SQLAlchemy 2.0 ORM repositories (Seat/Booking/Lock/Payment/Cache); Alembic migrations 001–005 (admin roles, multi-seat `booking_seats`, partial unique indexes, seat CASCADE FKs).

**1\. Provision Cloud PostgreSQL & PgBouncer:** Create a PostgreSQL database. Create two schemas: identity and booking. Deploy PgBouncer in transaction mode.

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

**Status: ✅ Complete.** Email/password auth with lockout + GDPR soft-delete/anonymize, Google OAuth2 SSO, RS256 JWT + rotating refresh tokens with reuse detection, Redis-cached catalog endpoints, and the PaymentIntent endpoint with write-before-call orphan prevention.

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

**Status: ✅ Complete.** Virtual waiting room with token admission + crash recovery, Lease-based HA admitter, Redis seat locking with server-generated idempotency keys, atomic multi-seat booking in a single `async with session.begin():` block with server-side price verification (FR-10).

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

**Status: ✅ Complete.** Gateway does global JWT validation + header stripping/injection + W3C tracing; zero-trust NetworkPolicies; transactional webhook receiver (idempotency, late-webhook refund guard, terminal-only Redis cleanup, StripeObject metadata handling); sweeper + outbox relay workers.

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

**Status: ✅ Complete.** Multi-stage Dockerfiles (api + web), Kustomize base/minikube/prod overlays, PDBs + pod anti-affinity, /health + /ready probes, KEDA (later replaced by native HPA for gateway) and migration Init Job. Docker Compose quick-start also added.

**1\. Dockerize:** Write lightweight Dockerfiles for Gateway, Identity, Booking, Sweeper, Relay, and Admitter, served via Gunicorn with Uvicorn workers.

**2\. K8s Manifests (Kustomize):** Write base manifests with explicit CPU/Memory requests/limits. Add PodDisruptionBudgets and podAntiAffinity.

**3\. Probes (FR-12):** Implement /health (liveness, returns 200 if process alive) and /ready (readiness, returns 503 gracefully if Redis/DB are unreachable to prevent K8s crash loops).

**4\. Scaling Configuration (NFR-2):** Use KEDA for HPA based on Redis queue depth and HTTP RPS.

**5\. Database Migrations (FR-13):** Deploy Alembic as an InitContainer Job in the FastAPI Deployment to ensure migrations run sequentially before app startup.

**Phase 6: Observability, Testing & CI/CD**

_Prove the system works under pressure and automate the development lifecycle._

**Status: ✅ Complete.** GitHub Actions (ruff, mypy, pytest suites against Postgres+Redis, migration+seed validation, Docker build); structlog JSON logging + Sentry + W3C traceparent; CloudWatch dashboard for EKS/ALB/RDS/NAT on the AWS side.

**1\. CI/CD Pipeline:** GitHub Actions running ruff, mypy, pytest (unit + integration via testcontainers), and trivy container scanning. Block PR merges on failure.

**2\. Observability Suite (NFR-4, NFR-5):** Deploy kube-prometheus-stack and Loki via Helm. Implement structured JSON logging (structlog) injecting request_id and trace_id. Initialize the Sentry SDK in every service so unhandled exceptions are captured and tagged with the same request_id/trace_id.

**3\. Grafana Dashboards:** Track booking write rates, 409 rejection rates, queue depth, DB connection pool usage, and Sweeper revert rates.

**4\. Advanced Load Testing (Locust):** Simulate thousands of fans hitting /queue/join, respecting Retry-After, securing holds, and initializing checkouts.

- **Disclaimer:** Document that Minikube is for functional concurrency validation; true throughput benchmarking happens in EKS.

**5\. Concurrency Verification:** Run property-based tests verifying that under 10,000 randomized concurrent requests, zero double-bookings occur.

**Phase 7: The EKS Finale (The Demo)**

_Translate the proven local system to the real cloud for portfolio validation._

**Status: ✅ Complete — LIVE.** EKS 1.35 + ALB + RDS + ECR + CloudFront + WAF (count mode) provisioned via Terraform; ArgoCD GitOps for `k8s/prod/`; ESO + SSM for secrets; cert-manager issuers ready; budget alarm at $150/mo. Full Stripe card checkout verified end-to-end against the live CloudFront URL (see "What We've Done So Far").

1. **Infrastructure (Terraform):**
- EKS cluster `event-ticketing` v1.35 with two node groups: `on-demand` (t3.small, infra pods) and `spot` (t3.medium/t4g, app pods), plus node-termination-handler for spot draining.
- RDS PostgreSQL `db.t4g.micro`, single-AZ, `skip_final_snapshot = true` (dev); DB password auto-generated via `random_password` into SSM `/event-ticketing/DB_PASSWORD`.
- IAM roles + OIDC/IRSA trust policies for the AWS Load Balancer Controller, External Secrets Operator, and EBS CSI driver.
- WAF with `waf_action` variable (default `count`) — switch to `block` only after analyzing CloudWatch Logs traffic.
- CloudFront distribution in front of the SPA (TTLs set to 0 so cache-busting is unnecessary).
- CloudWatch dashboard (`cloudwatch.tf`): EKS nodes, ALB, RDS, NAT, billing. Budget alarm at $150/month.

**2\. Cloud-Native Add-ons (`scripts/init.ps1`):**

- Installs Helm charts: `aws-load-balancer-controller` (kube-system), `keda` (keda), `external-secrets` (external-secrets, with IRSA role), `bitnami/redis` (event-ticketing, standalone, auth enabled — password to SSM `/event-ticketing/REDIS_PASSWORD`, `REDIS_URL` includes `:password@`), `eks/node-termination-handler` (kube-system), `argo-cd` (argocd, ClusterIP only — port-forward to access), `jetstack/cert-manager` (cert-manager, `installCRDs=true`).
- Writes all secrets to SSM Parameter Store (DB password, Redis password, JWT keys, Stripe keys).
- `scripts/init.ps1 -LbControllerRoleArn <out> -EsoRoleArn <out> -RdsEndpoint <out>`.

**3\. GitOps Deployment (ArgoCD):**

- Bootstrap once: `kubectl apply -f k8s/argocd/` (Repository secret + Application).
- ArgoCD syncs `k8s/prod/` from `main` on every push (`automated.sync` ON, `prune: false`, `selfHeal: false`).
- `k8s/prod/` extends `k8s/base/`, patches out minikube secrets + the migration job, adds the ALB Ingress (shared ALB group `event-ticketing`, WAF ARN hardcoded), cert-manager ClusterIssuers (`letsencrypt-staging`/`letsencrypt-prod`), ESO `ClusterSecretStore` → SSM, `nodeSelector: node-type: on-demand` on app pods, `imagePullPolicy: Always`, and the `redis-master-service.yaml` pin.
- Access: `kubectl port-forward -n argocd svc/argocd-server 8080:80`; admin password from `argocd-initial-admin-secret`.

**4\. Deploy & Test (`scripts/deploy.ps1`):**

- ECR login → `docker build` (api + web targets) → push `:main` → `aws eks update-kubeconfig` → `kubectl apply -k k8s/prod/` → rollout restart all deployments → wait for rollout.
- Set `VITE_STRIPE_PUBLISHABLE_KEY` before running so the web bundle is built with Stripe enabled.
- Run Locust against the public ALB/CloudFront URL; verify KEDA/HPAs scale based on load.
- Verified E2E: queue → lock → book → card-only Stripe charge → webhook auto-confirms the booking in ~2s (see "What We've Done So Far").

**5\. Capture & Destroy:**

- HTTPS requires a custom domain + ACM cert (HTTP-only by default when `domain_name` is empty). Security headers (CSP, HSTS, X-Frame-Options, X-Content-Type-Options, X-XSS-Protection, Referrer-Policy, Permissions-Policy) are set in both nginx.conf and the FastAPI middleware; JWT keys are injected at runtime via env (never baked into the image) and written to disk by `entrypoint.sh`.
- Screenshot Grafana dashboards, OpenTelemetry traces, and ArgoCD UI for your technical write-up.
- Destroy to conserve budget: `terraform destroy` from `infra/terraform/`.

**Phase 8: Rate Limiting & Advanced Caching (NFR-8)**

_Protect public endpoints from abuse while keeping catalog reads fast under flash-sale load. (Consolidated from the former FEATURE-2-RATE-LIMIT-CACHE.md.)_

**Status: ✅ Complete.**

**1\. Distributed Rate Limiting (NFR-8):** slowapi with a Redis-backed limiter, wired into the gateway as middleware + a `RateLimitExceeded` exception handler returning HTTP 429.

- Configurable per-route/role tiers: Public 60/min, Auth 10/min, Booking 5/min (seat lock, book, payment intent/sync).
- Limits tunable via `RATE_LIMIT_PUBLIC`, `RATE_LIMIT_AUTH`, `RATE_LIMIT_BOOKING` env vars (defaults live in `core/config/settings.py`).
- Tests: `tests/gateway/test_rate_limit.py` in CI.

**2\. Catalog Caching (FR-4):** Cache-aside via `CacheRepository`.

- Venues/events/showtimes cached with a 300s TTL; seat maps served fresh (short TTL) for accuracy during checkouts.
- Write-through invalidation executes strictly after the DB commit and is failure-tolerant — a Redis outage never breaks API responses.
- Tests: `tests/booking/test_cache.py`, `tests/booking/test_catalog_cache.py` in CI.

**3\. Edge Cases Covered:** cache stampede avoidance, authenticated vs public limits, invalidation under high write load.

**Phase 9: WebSocket Live Seat Updates (FR-14)**

_Real-time seat map updates using WebSockets, powered by Redis Pub/Sub. (Consolidated from the former FEATURE-3-WEBSOCKET.md.)_

**Status: ✅ Complete.**

**1\. Authenticated WebSocket Endpoint (FR-14):** `ws://host/ws/showtime/{show_id}?token={jwt}` in `services/gateway/websocket.py`.

- JWT validated on connect; invalid/missing token closes with code 4001.
- Keep-alive ping/pong; client messages are acked with a `pong` JSON frame.

**2\. Broadcast (Booking Service):** seat status changes (AVAILABLE → PENDING_PAYMENT → SOLD, plus lock events) are published to Redis channel `showtime:{show_id}:seats`; the gateway subscribes and fans out JSON `seat_update` messages to connected clients.

**3\. Connection Manager (`websocket_manager.py`):** per-show in-memory connection sets; Redis Pub/Sub backplane keeps multi-replica clusters consistent; dead connections are silently pruned on broadcast; clients fall back to polling on reconnect.

**4\. Tests:** `tests/gateway/test_websocket_manager.py` in CI.

**Phase 11: High-Capacity Venues (Sectioning) & 3-Tier Pricing**

_Scale seat maps to handle large stadiums without DOM lag and introduce tiered pricing._

**Status: ✅ Complete.**

**1\. Seat Sectioning:** Chunk seat generation into batches of 100 per section (`SEC-1`, `SEC-2`, etc.) to prevent massive primary key conflicts and unbounded DOM nodes.
**2\. Tiered Pricing:** Replaced flat `base_price` with `front_price`, `middle_price`, and `back_price`. 
**3\. 2-Step Seat Selection UI:** Refactored `showtime-page.tsx` to first ask users to pick a section, then render only that section's seats.
**4\. Frontend Testing:** Initialized Vitest, configured it with Vite, and added basic test suites for UI components to ensure frontend regressions are caught early.