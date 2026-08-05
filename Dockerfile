# ─────────────────────────────────────────────────────────────────────────────
# Multi-stage build for the event-ticketing platform.
#   --target api   → FastAPI backend image (gateway-api / workers / migrations)
#   --target web   → nginx + React SPA image (gateway-web)
#
# The same two images are used everywhere — docker-compose for local dev and
# Kubernetes for deployment — so local behaviour mirrors production exactly.
# There is intentionally NO monolith/supervisord stage.
#
# Pod runtime contract (k8s/base):
#   * api runs as unprivileged user `app` (uid 10001) — set via USER, no root.
#   * DB migrations run in an initContainer / Job — set RUN_DB_INIT=false to
#     stop the entrypoint from re-running alembic + seed on every pod boot.
#   * JWT keys are injected via env and written to disk by entrypoint.sh.
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Build React SPA ────────────────────────────────────────────────
FROM node:22-alpine AS frontend-builder

ARG VITE_STRIPE_PUBLISHABLE_KEY
ENV VITE_STRIPE_PUBLISHABLE_KEY=$VITE_STRIPE_PUBLISHABLE_KEY

RUN corepack enable && corepack prepare pnpm@9 --activate
WORKDIR /app

# Install deps first (cached unless the lockfile changes). Strict frozen-lockfile:
# a drift between pnpm-lock.yaml and package.json fails the build instead of
# silently producing a non-reproducible image.
COPY pnpm-workspace.yaml package.json pnpm-lock.yaml .npmrc ./
COPY apps/web/package.json ./apps/web/
RUN pnpm install --frozen-lockfile

COPY apps/web/ ./apps/web/
ENV PATH="/app/node_modules/.bin:$PATH"
WORKDIR /app/apps/web
RUN tsc -b && vite build

# ── Stage 2: Build Python venv (deps, then the app package) ─────────────────
FROM python:3.11-slim AS backend-builder
WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends gcc libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Layer 1: install runtime dependencies only (cached unless pyproject changes).
COPY apps/backend/pyproject.toml ./
RUN mkdir -p core services && touch core/__init__.py services/__init__.py
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

# Layer 2: install the real core/services distribution into the same venv.
COPY apps/backend/core ./core/
COPY apps/backend/services ./services/
RUN pip install --no-cache-dir --no-deps .

# ── Stage 3: API image — non-root, no OS toolchain ──────────────────────────
FROM python:3.11-slim AS api

# python:3.11-slim already ships libssl3; asyncpg/bcrypt/uvloop bundle their
# native deps, so no apt packages are needed at runtime.

RUN groupadd -r -g 10001 app && useradd -r -u 10001 -g app -d /app -s /sbin/nologin app

COPY --from=backend-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app"

WORKDIR /app

COPY apps/backend/core/ ./core/
COPY apps/backend/services/ ./services/
COPY apps/backend/migrations/ ./migrations/
COPY apps/backend/alembic.ini ./
COPY apps/backend/seed.py ./
COPY apps/backend/entrypoint.sh ./
RUN chmod +x entrypoint.sh && sed -i 's/\r$//' entrypoint.sh \
    && mkdir -p certs \
    && chown -R app:app /app

# Writeable location for ephemeral JWT keys (entrypoint.sh), nothing else.
# No VOLUME declaration: pods manage their own writable layers via emptydir.

# Numeric uid so kubelet can verify runAsNonRoot (named users can't be validated).
USER 10001
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)"]

CMD ["/app/entrypoint.sh"]

# ── Stage 4: Web image (nginx + React SPA) ──────────────────────────────────
FROM nginx:alpine AS web

# NGINX_UPSTREAM is the DNS name the nginx proxy forwards /v1 and /ws to.
#   * Kubernetes build (k8s/base): default gateway-api (ClusterIP service).
#   * docker-compose local run:   override with `api` (compose service name).
ARG NGINX_UPSTREAM=gateway-api

COPY --from=frontend-builder /app/apps/web/dist /usr/share/nginx/html
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
RUN sed -i "s|gateway-api|${NGINX_UPSTREAM}|g" /etc/nginx/conf.d/default.conf

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD wget -qO- http://127.0.0.1:8080/health || exit 1
