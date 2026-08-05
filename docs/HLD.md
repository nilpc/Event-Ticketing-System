# High-Level Design (HLD) — Event Ticketing System

## 1. Executive Summary & Architectural Principles

The **Event Ticketing System** is a distributed, high-concurrency event ticketing platform built specifically for high-demand "flash-sale" scenarios (e.g., major concert tours, sports championships). During peak sales, thousands of users request seat locks simultaneously within seconds, creating extreme database contention, potential double-bookings, and payment gateway bottlenecks.

### Core Architectural Principles
1. **Zero Double-Bookings Guarantee**: Enforced through a **5-Layer Concurrency Control Engine** (Redis hoarding locks, distributed locking, atomic database status checks, single-transaction state transitions, and background sweeper reconciliation).
2. **Strict Controller-Service-Repository (CSR) Separation**: Uncompromising boundary isolation between HTTP routing (Controllers), domain business logic (Services), and database interactions (Repositories).
3. **Transactional Outbox & Eventual Consistency**: Money and state mutations occur inside a single PostgreSQL `async with session.begin():` block. Downstream events (email, analytics, notification) are appended to a `booking.outbox_events` table within the same transaction and read asynchronously via `FOR UPDATE SKIP LOCKED`.
4. **Resilient Payment Reconciliation**: Uses an **"Initiated-Record-First"** pattern before interacting with Stripe, preventing orphaned payment intents and handling out-of-order webhook delivery idempotently.
5. **GitOps & Cloud-Native Elasticity**: Fully containerized multi-stage Docker builds deployed on AWS EKS 1.35, utilizing KEDA autoscaling, Bitnami Redis HA (Master/Replica), Amazon RDS PostgreSQL, External Secrets Operator (ESO), CloudFront CDN, AWS WAF, and ArgoCD GitOps continuous reconciliation.

---

## 2. High-Level Architecture Diagram

```mermaid
flowchart TB
    subgraph Clients["Clients & Edge Tier"]
        Browser["React SPA (Vite / Tailwind)"]
        MobileApp["Mobile / API Clients"]
        CF["AWS CloudFront CDN"]
        WAF["AWS WAF (Managed Rules / Count Mode)"]
    end

    subgraph AWS_Ingress["Ingress Tier"]
        ALB["AWS Application Load Balancer (ALB)"]
    end

    subgraph EKS_Cluster["AWS EKS Cluster (event-ticketing)"]
        subgraph Ingress_Controller["Ingress & Cert Controller"]
            AWS_LB_Ctrl["AWS Load Balancer Controller"]
            CertMgr["cert-manager (Let's Encrypt / ACME)"]
        end

        subgraph K8s_Namespace["Namespace: event-ticketing"]
            GatewayWeb["gateway-web Deployment\n(nginx SPA Static & Proxy)"]
            GatewayAPI["gateway-api Deployment\n(FastAPI Gateway & Microservices)"]
            
            subgraph Workers["Background Workers"]
                Admitter["queue-admitter\n(Lease Leader Election)"]
                Sweeper["booking-sweeper\n(Zombie Cleanup)"]
                Relay["outbox-relay\n(FOR UPDATE SKIP LOCKED)"]
            end
        end

        subgraph Controllers["Ops Controllers"]
            ESO["External Secrets Operator"]
            KEDA["KEDA Queue / CPU Scaler"]
            ArgoCD["ArgoCD GitOps Controller"]
        end
    end

    subgraph Data_Tier["State & Data Persistence Layer"]
        RDS[("Amazon RDS PostgreSQL 16\n(Schemas: identity, booking)")]
        RedisHA[("Bitnami Redis 7 HA\n(Master: redis-node-1, Replica: redis-node-0)")]
        SSM["AWS SSM Parameter Store\n(Encrypted Secrets)"]
    end

    subgraph External["External Services"]
        Stripe["Stripe Payment Gateway\n(PaymentIntent / Webhooks)"]
        GoogleOAuth["Google OAuth2 Provider"]
    end

    %% Flow Connections
    Browser --> CF
    MobileApp --> WAF
    CF --> WAF
    WAF --> ALB
    ALB --> GatewayWeb
    GatewayWeb --> GatewayAPI
    GatewayAPI --> RedisHA
    GatewayAPI --> RDS
    GatewayAPI --> Stripe
    GatewayAPI --> GoogleOAuth
    
    Workers --> RedisHA
    Workers --> RDS
    Stripe -- "Async Webhook POST" --> ALB
    ESO -- "Sync Secrets" --> SSM
    ESO -- "Inject Secrets" --> K8s_Namespace
    ArgoCD -- "Sync Manifests" --> EKS_Cluster
```

---

## 3. Subsystem Boundaries & Microservices

```
apps/backend/
├── core/                   # Shared Infrastructure (DB Session, Redis, Security, Exceptions, Observability)
└── services/
    ├── gateway/            # FastAPI Gateway App, Middleware (Auth, CORS, Security Headers, Rate Limit, W3C)
    ├── identity/           # Authentication, User Management, RS256 JWT, Refresh Tokens, Google OAuth2
    ├── booking/            # Catalog (Events/Showtimes/Venues), Seats, Queue (Waiting Room), Booking Core
    ├── payment/            # Stripe Client Integration, Payment Service, Webhook Reconciliation Service
    └── workers/            # In-Process / Standalone Background Workers (Admitter, Sweeper, Outbox Relay)
```

### 3.1 Gateway API Subsystem
- **Role**: Entry point for all HTTP traffic and WebSocket connections (`/v1/*`, `/ws`).
- **Responsibilities**: Security header injection (CSP, HSTS, X-Frame-Options), W3C traceparent context propagation, RS256 JWT authentication middleware, slowapi rate limiting (public, auth, and booking tiers), and CORS enforcement.

### 3.2 Identity & Security Subsystem
- **Role**: Identity lifecycle management and token issuance (`identity` schema).
- **Responsibilities**:
  - Email/Password signup with `zxcvbn` strength scoring and progressive login lockout.
  - Google OAuth2 Authorization Code flow with automatic account linking by email.
  - RS256 JWT issuance (`access_token` with 15-min TTL, `jti` claim) and DB-backed refresh tokens with automatic reuse detection (invalidates entire token family if stolen token is presented).
  - GDPR-compliant soft-deletion and anonymization (`/auth/me/anonymize`).

### 3.3 Catalog & Virtual Waiting Room Subsystem
- **Role**: Public event catalog and high-throughput traffic control (`booking` schema & Redis).
- **Responsibilities**:
  - Redis cache-aside catalog queries for venues, events, showtimes, and seat maps.
  - Virtual Waiting Room (`POST /queue/join`, `GET /queue/status`, `GET /queue/recover`): Redis Sorted Set (`zset`) ranking users by arrival timestamp.
  - Leader-elected Queue Admitter worker that grants `X-Queue-Token` admission slots at a controlled throughput rate.

### 3.4 Concurrency & Atomic Booking Engine
- **Role**: High-speed seat reservation and multi-seat booking initialization.
- **Responsibilities**:
  - Multi-seat reservation (`POST /seats/lock`) supporting up to 8 seats per request.
  - 10-minute Redis seat holds (`hold:{show_id}:{seat_id}`).
  - Server-generated idempotency keys.
  - Atomic booking initialization (`POST /book`) in a single PostgreSQL `async with session.begin():` block that inserts `booking.bookings` and `booking.booking_seats` rows.

### 3.5 Payment & Webhook Reconciliation Subsystem
- **Role**: Payment Intent lifecycle and Stripe webhook processing.
- **Responsibilities**:
  - `POST /payments/intent`: Checks booking expiry ($> 2$ min remaining), enforces `unique_active_payment_per_booking` partial index, and creates Stripe PaymentIntent.
  - `POST /payments/{id}/sync` & `POST /payments/webhook`: Webhook idempotency guard (`booking.processed_webhook_events`), status reconciliation, seat state finalization to `SOLD`, and outbox event dispatch.

### 3.6 Background Worker Subsystem
- **Role**: Asynchronous system maintenance and event propagation.
- **Workers**:
  - **Queue Admitter**: Kubernetes Lease-based leader election; admits batches of waiting queue tokens into active booking windows.
  - **Booking Sweeper**: Scans for `PENDING` bookings past `expires_at` timestamp; cancels bookings and releases locked seats back to `AVAILABLE`.
  - **Outbox Relay**: Queries `booking.outbox_events` via `SELECT ... FOR UPDATE SKIP LOCKED` and publishes unpublished events to external sinks or loggers.

---

## 4. End-to-End Workflows & Sequence Diagrams

### 4.1 Authentication & Session Management Workflow

```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant Gateway as Gateway API
    participant Identity as Identity Service
    participant DB as Postgres (identity.users)
    participant Redis as Redis (Token Blacklist)

    alt Password Login
        Client->>Gateway: POST /v1/auth/login {email, password}
        Gateway->>Identity: authenticate_user()
        Identity->>DB: Fetch user by email
        DB-->>Identity: User record (hashed_password)
        Identity->>Identity: Verify password (bcrypt) & Check lockout
        Identity->>DB: Create Refresh Token Record
        Identity-->>Gateway: Access Token (RS256 JWT, 15m) + Refresh Token
        Gateway-->>Client: 200 OK + JWT Tokens
    else Google OAuth2 SSO
        Client->>Gateway: GET /v1/auth/google/authorize
        Gateway-->>Client: Redirect to accounts.google.com
        Client->>Gateway: GET /v1/auth/google/callback?code=...
        Gateway->>Identity: Process OAuth2 Code
        Identity->>DB: Find or create identity.users (by google_subject_id/email)
        Identity-->>Gateway: Access Token + Refresh Token
        Gateway-->>Client: 200 OK + JWT Tokens
    end
```

---

### 4.2 Virtual Waiting Room & Admission Workflow

```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant Gateway as Gateway API
    participant Queue as Queue Service
    participant Redis as Redis (zset & tokens)
    participant Admitter as Queue Admitter (Worker)

    Client->>Gateway: POST /v1/queue/join {show_id}
    Gateway->>Queue: join_queue(user_id, show_id)
    Queue->>Redis: ZADD queue:{show_id} {timestamp} {user_id}
    Queue-->>Client: 200 OK {position, queue_token, retry_after=5s}

    loop Every 5s Polling
        Client->>Gateway: GET /v1/queue/status?show_id=...
        Gateway->>Queue: get_status()
        Queue->>Redis: ZRANK queue:{show_id} {user_id}
        Redis-->>Queue: Position #142
        Queue-->>Client: 200 OK {status: "WAITING", position: 142}
    end

    note over Admitter: Leader-Elected Worker Runs Batch Loop
    Admitter->>Redis: ZPOPMIN queue:{show_id} (batch of 50)
    Admitter->>Redis: SET admitted:{show_id}:{queue_token} TTL=600s

    Client->>Gateway: GET /v1/queue/status?show_id=...
    Gateway->>Queue: get_status()
    Queue->>Redis: EXISTS admitted:{show_id}:{queue_token}
    Redis-->>Queue: True
    Queue-->>Client: 200 OK {status: "ADMITTED", queue_token: "qt_12345"}
```

---

### 4.3 5-Layer Concurrency Control & Atomic Booking Workflow

```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant Gateway as Gateway API
    participant Booking as Booking Service
    participant Redis as Redis (Seat Holds & Locks)
    participant DB as Postgres (booking schema)

    note over Client,DB: Step 1: Seat Locking (Layer 1 & Layer 2)
    Client->>Gateway: POST /v1/seats/lock {show_id, seat_ids: ["A1", "A2"]} (Header: X-Queue-Token)
    Gateway->>Booking: lock_seats()
    Booking->>Redis: EVAL Lua Script (Acquire hold:{show_id}:{seat_id} for user)
    alt Seat already held by another user
        Redis-->>Booking: Hold Failed
        Booking-->>Client: 409 Conflict ("Seat A1 unavailable")
    else Holds Acquired
        Redis-->>Booking: Hold Success
        Booking->>DB: UPDATE booking.seats SET status='PENDING_PAYMENT' WHERE status='AVAILABLE'
        Booking-->>Client: 200 OK {idempotency_key: "ik_abc123", expires_at: "..."}
    end

    note over Client,DB: Step 2: Atomic Booking Creation (Layer 3, Layer 4, Layer 5)
    Client->>Gateway: POST /v1/book {show_id, seat_ids, idempotency_key}
    Gateway->>Booking: create_booking()
    Booking->>DB: BEGIN TRANSACTION (async with session.begin())
    Booking->>DB: SELECT * FROM booking.bookings WHERE idempotency_key = 'ik_abc123'
    alt Idempotency Replay
        DB-->>Booking: Existing Booking Found
        Booking-->>Client: 200 OK (Return existing booking)
    else New Booking
        Booking->>DB: Verify active booking guard for user+show (NFR-1 partial index)
        Booking->>DB: Verify seat prices from booking.seats table (Server-side validation)
        Booking->>DB: INSERT INTO booking.bookings (PENDING)
        Booking->>DB: INSERT INTO booking.booking_seats (junction rows)
        Booking->>DB: COMMIT TRANSACTION
        Booking-->>Client: 201 Created {booking_id: "bk_999", status: "PENDING"}
    end
```

---

### 4.4 Stripe PaymentIntent & Async Webhook Reconciliation Workflow

```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant Gateway as Gateway API
    participant Payment as Payment Service
    participant DB as Postgres (booking schema)
    participant Stripe as Stripe API
    participant Webhook as Webhook Service

    note over Client,Stripe: Step 1: Initiate Payment Intent
    Client->>Gateway: POST /v1/payments/intent {booking_id}
    Gateway->>Payment: create_intent()
    Payment->>DB: Check booking.bookings (expires_at > 2m & status == PENDING)
    Payment->>DB: INSERT INTO booking.payments (status='INITIATED') (Initiated-First Pattern)
    Payment->>Stripe: stripe.PaymentIntent.create(amount, currency='inr', metadata={booking_id})
    Stripe-->>Payment: PaymentIntent {id: "pi_123", client_secret: "cs_123"}
    Payment->>DB: UPDATE booking.payments SET provider_payment_id='pi_123', status='REQUIRES_ACTION'
    Payment-->>Client: 200 OK {client_secret: "cs_123", payment_id: "pay_555"}

    note over Client,Stripe: Step 2: Client Completes Card Payment
    Client->>Stripe: stripe.confirmPayment(client_secret, card_element)
    Stripe-->>Client: PaymentIntent status: "succeeded"
    Client->>Gateway: POST /v1/payments/pay_555/sync

    note over Stripe,DB: Step 3: Webhook Asynchronous Reconciliation
    Stripe->>Gateway: POST /v1/payments/webhook (Header: Stripe-Signature)
    Gateway->>Webhook: process_webhook(payload, signature)
    Webhook->>Webhook: Verify Stripe signature via STRIPE_WEBHOOK_SECRET
    Webhook->>DB: INSERT INTO booking.processed_webhook_events (event_id)
    alt Duplicate Webhook Event
        DB-->>Webhook: Unique Constraint Violation (event_id)
        Webhook-->>Stripe: 200 OK (Duplicate Dropped)
    else New Webhook Event
        Webhook->>DB: BEGIN TRANSACTION
        Webhook->>DB: UPDATE booking.payments SET status='SUCCEEDED'
        Webhook->>DB: UPDATE booking.seats SET status='SOLD' WHERE status='PENDING_PAYMENT'
        Webhook->>DB: UPDATE booking.bookings SET status='CONFIRMED'
        Webhook->>DB: INSERT INTO booking.outbox_events (event_type='BOOKING_CONFIRMED')
        Webhook->>DB: COMMIT TRANSACTION
        Webhook->>Redis: PUBLISH seat_map_updates {show_id, seat_ids, status: "SOLD"}
        Webhook-->>Stripe: 200 OK (Processed)
    end
```

---

### 4.5 Live WebSocket Seat Map Update Workflow

```mermaid
sequenceDiagram
    autonumber
    actor Client1 as Client 1 (Viewer)
    actor Client2 as Client 2 (Buyer)
    participant Gateway as Gateway API (ws endpoint)
    participant RedisPubSub as Redis Pub/Sub Backplane
    participant Webhook as Webhook Service

    Client1->>Gateway: WS /ws/showtimes/{show_id}/seats
    Gateway->>RedisPubSub: SUBSCRIBE showtime:{show_id}:seats

    Client2->>Webhook: Webhook confirms payment for seat "A1"
    Webhook->>RedisPubSub: PUBLISH showtime:{show_id}:seats {seat_id: "A1", status: "SOLD"}
    RedisPubSub-->>Gateway: Message received for channel
    Gateway-->>Client1: WS Frame: {event: "SEAT_UPDATE", seat_id: "A1", status: "SOLD"}
```

---

## 5. Infrastructure, Cloud Topology & Security Model

### 5.1 AWS EKS Production Infrastructure Topology

- **AWS Region**: `us-east-1`
- **VPC Architecture**: 3 Public Subnets, 3 Private Subnets, Single NAT Gateway (Cost-optimized).
- **EKS Cluster Version**: 1.35 (Cluster Name: `event-ticketing`).
- **Node Groups**:
  - `on-demand`: `t3.small` (Infra pods: ingress controllers, external-secrets, metrics-server).
  - `spot`: `t3.medium` / `t4g.medium` (Application pods: gateway-api, gateway-web, workers).
- **Database (RDS)**: PostgreSQL 16 (`db.t4g.micro`, single-AZ, encrypted storage, security group restricted to EKS node security group).
- **Cache (Redis)**: Bitnami Redis Helm chart (`redis-node-1` Master, `redis-node-0` Replica, password authenticated, pinned master Service `redis-master`).

### 5.2 Security Architecture & Controls

| Security Domain | Implementation Specification |
| :--- | :--- |
| **IAM / IRSA** | IAM Roles for Service Accounts. EKS Service Accounts bind to AWS IAM roles for SSM Parameter Store read access. |
| **Secrets Management** | AWS SSM Parameter Store $\rightarrow$ External Secrets Operator (ESO) $\rightarrow$ Kubernetes Secret (`event-ticketing-secrets`). |
| **JWT Key Security** | RSA-2048 keys generated dynamically at pod startup by `entrypoint.sh` or injected via `JWT_PRIVATE_KEY` / `JWT_PUBLIC_KEY` env vars. Keys are never baked into Docker images. |
| **WAF Protection** | AWS WAF Web ACL attached to ALB with AWS Managed Rules (Core Rule Set, Known Bad Inputs, SQLi protection) operating in **Count** mode. |
| **Security Headers** | Injected in both Nginx (`nginx.conf`) and FastAPI Middleware: Content-Security-Policy (CSP), HSTS, X-Frame-Options (`DENY`), X-Content-Type-Options (`nosniff`), Referrer-Policy (`strict-origin-when-cross-origin`). |
| **Network Isolation** | Kubernetes NetworkPolicies restricting pod-to-pod communication (`allow-gateway-only`, `gateway-external-access`). |

---

## 6. Resilience, High Availability & Disaster Recovery

1. **Pod Disruption Budgets (PDBs)**: Configured for all core deployments (`gateway-api-pdb`, `gateway-web-pdb`, `sweeper-pdb`, `relay-pdb`, `admitter-pdb`) ensuring minimum availability during node drains or spot replacements.
2. **Spot Draining**: `eks/node-termination-handler` intercepts EC2 Spot Interruption notices 2 minutes prior to termination, triggering graceful pod eviction.
3. **Queue Scaler & CPU HPA**:
   - `gateway-api-hpa` & `gateway-web-hpa`: CPU/Memory autoscaling via Kubernetes HPA.
   - `keda-queue-scaler`: ScaledObject driving application replica count based on Redis waiting room queue depth.
4. **Outbox Pattern Guarantee**: If downstream notification/event services crash, no messages are lost; events remain in `booking.outbox_events` with `published_at = NULL` and are retried indefinitely by `outbox-relay`.
5. **Sweeper Auto-Reconciliation**: If a user abandons checkout or the browser crashes after locking seats, `booking-sweeper` automatically releases the seats and marks the booking as `FAILED` within 10 minutes.
