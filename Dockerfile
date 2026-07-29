# ── Stage 1: Build React SPA ─────────────────────────────────────
FROM node:22-alpine AS frontend-builder
RUN corepack enable && corepack prepare pnpm@9 --activate
WORKDIR /app

COPY pnpm-workspace.yaml package.json pnpm-lock.yaml .npmrc ./
COPY apps/web/package.json ./apps/web/

RUN pnpm install --frozen-lockfile || pnpm install

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

# ── Stage 3: API image (Python-only, no nginx) ──────────────────
FROM python:3.11-slim AS api

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 \
        libssl3 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=backend-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app"

RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app

WORKDIR /app

COPY apps/backend/core/ ./core/
COPY apps/backend/services/ ./services/
COPY apps/backend/migrations/ ./migrations/
COPY apps/backend/alembic.ini ./
COPY apps/backend/seed.py ./
COPY apps/backend/entrypoint.sh ./
RUN chmod +x entrypoint.sh && sed -i 's/\r$//' entrypoint.sh

RUN mkdir -p certs && chown app:app certs && \
    chown -R app:app /app

EXPOSE 8000

CMD ["/app/entrypoint.sh"]

# ── Stage 4: Web image (nginx + React SPA) ──────────────────────
FROM nginx:alpine AS web

COPY --from=frontend-builder /app/apps/web/dist /usr/share/nginx/html
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080

# ── Stage 5: Monolith (legacy — kept for backward compat) ──────
FROM python:3.11-slim AS production

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        nginx \
        supervisor \
        libpq5 \
        libssl3 \
    && rm -rf /var/lib/apt/lists/*

RUN rm -f /etc/nginx/sites-enabled/default

COPY --from=backend-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app"

RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app

WORKDIR /app

COPY apps/backend/core/ ./core/
COPY apps/backend/services/ ./services/
COPY apps/backend/migrations/ ./migrations/
COPY apps/backend/alembic.ini ./
COPY apps/backend/seed.py ./
COPY apps/backend/entrypoint.sh ./
RUN chmod +x entrypoint.sh && sed -i 's/\r$//' entrypoint.sh

RUN mkdir -p certs && chown app:app certs

COPY --from=frontend-builder /app/apps/web/dist /usr/share/nginx/html

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
