# Project Rules
- Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0 async.
- STRICT Controller-Service-Repository (CSR) architecture.
  - Routers (Controllers) handle HTTP, call Services.
  - Services handle business logic, call Repositories.
  - Repositories handle DB queries using SQLAlchemy 2.0 ORM (NO RAW SQL).
- Postgres schemas: `identity` and `booking`. Cross-schema FKs enforced.
- All money/state mutations must occur inside a single `async with session.begin():` block.
- Redis failures must NEVER break post-commit API responses.
- Cite FR-x / NFR-x in docstrings of the code that implements them.
- Source of truth: docs/PHASES.md (build order) and docs/REQUIREMENTS.md (contract).

# Phase 7: EKS Infrastructure Rules
## Terraform
- All infra code in `infra/terraform/`. Flat files (no nested modules).
- Every resource must have `tags = merge(var.tags, {Name = ...})`.
- EKS cluster named `event-ticketing`, version 1.30.
- Two node groups: `on-demand` (t3.small for infra pods) and `spot` (t3.medium/t4g for app pods).
- RDS: db.t4g.micro, single-AZ, `skip_final_snapshot = true` for dev.
- WAF: `waf_action` variable controls count/block — default `count`.
- DB password auto-generated via `random_password`, stored in SSM `/event-ticketing/DB_PASSWORD`.
- NAT Gateway: single (cost-optimized). Upgrade to 3 for HA later.

## Security (Mandatory)
- JWT keys NEVER baked into Docker image. Injected at runtime via JWT_PRIVATE_KEY/JWT_PUBLIC_KEY env vars. `entrypoint.sh` writes them to disk before app starts.
- Redis requires auth (`auth.enabled=true`). Password stored in SSM `/event-ticketing/REDIS_PASSWORD`. REDIS_URL includes `:password@`.
- Security headers (CSP, HSTS, X-Frame-Options, X-Content-Type-Options, X-XSS-Protection, Referrer-Policy, Permissions-Policy) set in both nginx.conf and FastAPI middleware.
- WAF starts in Count mode. Switch to `block` only after analyzing traffic in CloudWatch Logs.
- HTTPS: requires a custom domain + ACM cert. HTTP-only by default when `domain_name` is empty.

## Kustomize (k8s/prod/)
- Extends `k8s/base`. Patches out minikube secrets and migration job.
- Adds ALB Ingress with AWS LB Controller annotations. WAF ARN is hardcoded in `ingress.yaml` (no `__WAF_ACL_ARN__` placeholder — it's a stable terraform-managed ARN).
- Ingress uses shared ALB group `alb.ingress.kubernetes.io/group.name: event-ticketing` so cert-manager's ACME HTTP-01 solver ingress joins the SAME ALB (no second ALB spawned for challenges).
- cert-manager ClusterIssuers in `cluster-issuer.yaml`: `letsencrypt-staging` + `letsencrypt-prod` (HTTP-01, class `alb`). Ready without a domain; TLS starts working when an ingress `tls:` host resolves to the ALB.
- Application pods (gateway, sweeper, relay, admitter) get `nodeSelector: node-type: on-demand` (no spot tolerations).
- Secrets fetched via External Secrets Operator from SSM Parameter Store.
- All deployments patched with `imagePullPolicy: Always`.
- Adds a `redis-master-service.yaml` that pins the `redis-master` Service to `redis-node-0` (the Bitnami `redis` service round-robins master+replica, which breaks plain Redis clients).

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
