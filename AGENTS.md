# Project Rules
- Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0 async.
- STRICT Controller-Service-Repository (CSR) architecture.
  - Routers (Controllers) handle HTTP, call Services.
  - Services handle business logic, call Repositories.
  - Repositories handle DB queries using SQLAlchemy 2.0 ORM (NO RAW SQL).
- Postgres schemas: `identity` and `booking`. Cross-schema foreign keys decoupled (`user_id` stored as unconstrained UUID) for microservice database isolation.
- Outbox worker uses PostgreSQL `LISTEN / NOTIFY` (`booking.notify_outbox_inserted()`) with a 5s fallback polling loop.
- Queue supports Server-Sent Events (SSE) streaming via `GET /v1/queue/stream`.
- Catalog responses include CDN Edge headers (`Cache-Control: public, max-age=15, s-maxage=60, stale-while-revalidate=30`).
- All money/state mutations must occur inside a single `async with session.begin():` block.
- Redis failures must NEVER break post-commit API responses.
- Cite FR-x / NFR-x in docstrings of the code that implements them.
- Source of truth: docs/PHASES.md (build order), docs/REQUIREMENTS.md (contract), docs/HLD.md (High-Level Architecture), and docs/LLD.md (Low-Level Design).

# Local Test Environment
- Docker test services: `ci-pg-test` (postgres:16) on **5433**, `ci-redis-test` (redis:7) on **6380**.
- Creds: `testuser` / `testpass`, DB `event_ticketing`.
- Run tests with:
  - `DATABASE_URL=postgresql+asyncpg://testuser:testpass@localhost:5433/event_ticketing`
  - `REDIS_URL=redis://localhost:6380/0`
  - `LOG_FORMAT=console`
- `pytest` conftest creates/drops schemas via `Base.metadata.create_all` (NOT alembic). The host Postgres at 5432 has a wrong `testuser` password — always use 5433.
- To validate migrations on a fresh DB, drop ALL schemas first — the alembic version table lives in the `alembic` schema (`migrations/env.py`), so dropping only `public.alembic_version` is NOT enough and `upgrade head` will no-op:
  - `DROP SCHEMA IF EXISTS identity CASCADE; DROP SCHEMA IF EXISTS booking CASCADE; DROP SCHEMA IF EXISTS alembic CASCADE;`
  - then `alembic upgrade head` (all 8 migrations) and `seed.py` (needs `ADMIN_PASSWORD`).

# Phase 7 & 10: EKS Infrastructure & Hardening Rules
## Terraform
- All infra code in `infra/terraform/`. Flat files (no nested modules).
- Every resource must have `tags = merge(var.tags, {Name = ...})`.
- EKS cluster named `event-ticketing`, version 1.35.
- Two node groups: `on-demand` (t3.small for infra pods) and `spot` (t3.medium/t4g for app pods).
- RDS: db.t4g.micro, single-AZ (cost-optimized to stay within $150/mo budget limit; set `multi_az = true` in `rds.tf` for production HA), `skip_final_snapshot = true` for dev.
- WAF: `waf_action` variable defaults to `block` mode enforcing AWS Managed Rules.
- `metrics-server` is an EKS managed addon (`aws_eks_addon.metrics_server` in `eks.tf`) — required for the CPU HPAs in `k8s/base/hpa.yaml`; KEDA only serves `external.metrics.k8s.io`.
- DB password auto-generated via `random_password`, stored in SSM `/event-ticketing/DB_PASSWORD`.
- NAT Gateway: single (cost-optimized to stay within $150/mo budget limit; set `enable_single_nat_gateway = false` in `vpc.tf` for 3-AZ production HA).

## Security (Mandatory)
- JWT keys NEVER baked into Docker image. Injected at runtime via JWT_PRIVATE_KEY/JWT_PUBLIC_KEY env vars. `entrypoint.sh` writes them to disk before app starts.
- Redis requires auth (`auth.enabled=true`). Password stored in SSM `/event-ticketing/REDIS_PASSWORD`. REDIS_URL includes `:password@`.
- Security headers (CSP, HSTS, X-Frame-Options, X-Content-Type-Options, X-XSS-Protection, Referrer-Policy, Permissions-Policy) set in both nginx.conf and FastAPI middleware.
- WAF operates in `block` mode enforcing security rulesets.
- HTTPS: requires a custom domain + ACM cert. HTTP-only by default when `domain_name` is empty.

## Kustomize (k8s/prod/)
- Extends `k8s/base`. Patches out minikube secrets and migration job.
- Adds ALB Ingress with AWS LB Controller annotations. WAF ARN is hardcoded in `ingress.yaml` (no `__WAF_ACL_ARN__` placeholder — it's a stable terraform-managed ARN).
- Ingress uses shared ALB group `alb.ingress.kubernetes.io/group.name: event-ticketing` so cert-manager's ACME HTTP-01 solver ingress joins the SAME ALB (no second ALB spawned for challenges).
- cert-manager ClusterIssuers in `cluster-issuer.yaml`: `letsencrypt-staging` + `letsencrypt-prod` (HTTP-01, class `alb`). Ready without a domain; TLS starts working when an ingress `tls:` host resolves to the ALB.
- Application pods (gateway, sweeper, relay, admitter) get `nodeSelector: node-type: on-demand` (no spot tolerations).
- Secrets fetched via External Secrets Operator from SSM Parameter Store.
- All deployments patched with `imagePullPolicy: Always`.
- All deployments patched with `imagePullPolicy: Always`.
- Adds a `redis-master-service.yaml` that pins the `redis-master` Service to `redis-node-1` (the active Bitnami `redis` master pod, preventing reads/writes from hitting the read-only replica).

## GitOps (ArgoCD)
- ArgoCD is the declarative controller of record for `k8s/prod/`. Bootstrap manifests live in `k8s/argocd/` (Repository secret + Application), applied once via `kubectl apply -f k8s/argocd/`.
- Application `event-ticketing` syncs `k8s/prod/` from `https://github.com/nilpc/Event-Ticketing-System.git` (public repo, no credentials) on every push to `main`.
- Sync policy: `automated.sync` ON, `prune: false` (NEVER deletes resources not in git, e.g. helm-managed redis), `selfHeal: false` (manual `kubectl apply`/rollout-restart is not reverted).
- ArgoCD server is `ClusterIP` only — NO public NLB. Access via `kubectl port-forward -n argocd svc/argocd-server 8080:80`; admin password from `argocd-initial-admin-secret`.
- Do NOT enable selfHeal/prune unless helm-managed resources (redis, cert-manager, keda, ESO) are first moved under git control.

## Helm Charts (installed via scripts/init.ps1)
- `aws-load-balancer-controller` in kube-system
- `keda` in keda namespace
- `external-secrets` in external-secrets namespace (with IRSA role)
- `bitnami/redis` (standalone, auth enabled) in event-ticketing namespace
- `eks/node-termination-handler` in kube-system (spot draining)
- `argo-cd` in argocd namespace (server service type: ClusterIP, port-forward only)
- `jetstack/cert-manager` in cert-manager namespace (with `installCRDs=true`; ClusterIssuers applied via k8s/prod overlay)

## Observability
- CloudWatch dashboard in `infra/terraform/cloudwatch.tf` — EKS nodes, ALB, RDS, NAT, billing

## Deployment
- First-time: `terraform apply` → `scripts/init.ps1` → `kubectl apply -f k8s/argocd/` (ArgoCD then syncs `k8s/prod/`)
- Manifest updates: commit + push to `main` → ArgoCD auto-syncs `k8s/prod/`
- Image updates: `scripts/deploy.ps1` (build → push `:main` → `kubectl apply -k k8s/prod/` → rollout restart). selfHeal=off so the restart is not reverted.
- Destroy: `terraform destroy` from `infra/terraform/`
- Budget alarm: $150/month via AWS Budgets
