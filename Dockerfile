# ── Stage 1: Build React SPA ─────────────────────────────────────
FROM node:22-alpine AS frontend-builder
RUN corepack enable && corepack prepare pnpm@9 --activate
WORKDIR /app

COPY pnpm-workspace.yaml package.json pnpm-lock.yaml .npmrc ./
COPY packages/shared/package.json ./packages/shared/
COPY apps/web/package.json ./apps/web/

# Stub excluded workspace packages so pnpm install resolves
RUN mkdir -p packages/sdk packages/ui && \
    echo '{"name":"@event-ticketing/sdk","private":true,"version":"0.0.0"}' > packages/sdk/package.json && \
    echo '{"name":"@event-ticketing/ui","private":true,"version":"0.0.0"}' > packages/ui/package.json

RUN pnpm install --frozen-lockfile || pnpm install

COPY packages/shared/ ./packages/shared/
COPY apps/web/ ./apps/web/

ENV PATH="/app/node_modules/.bin:$PATH"
WORKDIR /app/apps/web
RUN tsc -b && vite build

# ── Stage 2: Build Python wheels ────────────────────────────────
FROM python:3.11-slim AS backend-builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends gcc libffi-dev && rm -rf /var/lib/apt/lists/*

COPY apps/backend/pyproject.toml ./
RUN mkdir -p core services && touch core/__init__.py services/__init__.py
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

# ── Stage 3: Production image ───────────────────────────────────
FROM python:3.11-slim AS production

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        nginx \
        supervisor \
        libpq5 \
        libssl3 \
    && rm -rf /var/lib/apt/lists/*

# Remove Debian default site (conflicts with our conf.d/default.conf)
RUN rm -f /etc/nginx/sites-enabled/default

# Python venv from builder
COPY --from=backend-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app"

# Non-root user
RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app

WORKDIR /app

# Backend code
COPY apps/backend/core/ ./core/
COPY apps/backend/services/ ./services/
COPY apps/backend/migrations/ ./migrations/
COPY apps/backend/alembic.ini ./
COPY apps/backend/seed.py ./
COPY apps/backend/entrypoint.sh ./
RUN chmod +x entrypoint.sh && sed -i 's/\r$//' entrypoint.sh

# RSA certs (auto-generate if missing)
RUN mkdir -p certs && \
    if [ ! -f certs/private.pem ]; then \
        openssl genrsa -out certs/private.pem 2048 2>/dev/null && \
        openssl rsa -in certs/private.pem -pubout -out certs/public.pem 2>/dev/null; \
    fi

# Frontend static files
COPY --from=frontend-builder /app/apps/web/dist /usr/share/nginx/html

# Config files
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

RUN mkdir -p /var/cache/nginx /var/run && \
    chown -R app:app /app && \
    chown -R app:app /usr/share/nginx/html && \
    chown -R app:app /var/log/nginx && \
    chown -R app:app /var/lib/nginx && \
    chown -R app:app /var/cache/nginx && \
    chown -R app:app /var/run

EXPOSE 8080

CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
