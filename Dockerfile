FROM node:22-alpine AS frontend-builder
ARG VITE_STRIPE_PUBLISHABLE_KEY
ENV VITE_STRIPE_PUBLISHABLE_KEY=$VITE_STRIPE_PUBLISHABLE_KEY
RUN corepack enable && corepack prepare pnpm@9 --activate
WORKDIR /app
COPY pnpm-workspace.yaml package.json pnpm-lock.yaml .npmrc ./
COPY apps/web/package.json ./apps/web/
RUN pnpm install --frozen-lockfile
COPY apps/web/ ./apps/web/
ENV PATH="/app/node_modules/.bin:$PATH"
WORKDIR /app/apps/web
RUN tsc -b && vite build
FROM python:3.11-slim AS backend-builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends gcc libffi-dev \
    && rm -rf /var/lib/apt/lists/*
COPY apps/backend/pyproject.toml ./
RUN mkdir -p core services && touch core/__init__.py services/__init__.py
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .
COPY apps/backend/core ./core/
COPY apps/backend/services ./services/
RUN pip install --no-cache-dir --no-deps .
FROM python:3.11-slim AS api
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
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)"]
CMD ["/app/entrypoint.sh"]
FROM nginx:alpine AS web
ARG NGINX_UPSTREAM=gateway-api
COPY --from=frontend-builder /app/apps/web/dist /usr/share/nginx/html
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
RUN sed -i "s|gateway-api|${NGINX_UPSTREAM}|g" /etc/nginx/conf.d/default.conf
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD wget -qO- http://127.0.0.1:8080/health || exit 1
