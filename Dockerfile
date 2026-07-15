# Phase 5.1: Lightweight multi-stage Dockerfile for all services.
# Build context: project root.  Run via:
#   docker build -t event-ticketing .
#   docker run --rm event-ticketing                          # gateway
#   docker run --rm event-ticketing python -m services.workers sweeper
#   docker run --rm event-ticketing python -m services.workers relay
#   docker run --rm event-ticketing python -m services.workers admitter
#   docker run --rm event-ticketing alembic upgrade head     # migration job
#
# Dev dependencies (pytest, ruff, mypy, locust, etc.) are excluded
# from the production image to keep it lightweight.

# ── Stage 1: build wheels ─────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build-time system deps (needed for bcrypt wheel)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libffi-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy only dependency specs first for layer caching
COPY pyproject.toml ./
# Create a minimal package layout so pip can resolve the project
RUN mkdir -p core services && touch core/__init__.py services/__init__.py

# Install runtime deps only (no [dev] extras) into a virtual-env
# so we can copy the entire venv cleanly.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# ── Stage 2: production image ─────────────────────────────────────────
FROM python:3.11-slim AS production

# Runtime-only system libs (asyncpg needs libpq; bcrypt needs libssl)
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 libssl3 && \
    rm -rf /var/lib/apt/lists/*

# Copy the pre-built virtual-env from the builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app"

# Create a non-root user
RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app

WORKDIR /app

# Copy application source (core + services + migrations + alembic.ini)
COPY core/         ./core/
COPY services/     ./services/
COPY migrations/   ./migrations/
COPY alembic.ini   ./

# FR-13, JWT: Generate self-signed RSA keys if not mounted as a secret.
# In production, mount certs/private.pem + certs/public.pem via K8s Secret.
RUN mkdir -p certs && \
    if [ ! -f certs/private.pem ]; then \
        openssl genrsa -out certs/private.pem 2048 2>/dev/null && \
        openssl rsa -in certs/private.pem -pubout -out certs/public.pem 2>/dev/null; \
    fi

# Ensure the non-root user owns everything
RUN chown -R app:app /app

USER app

# FR-12: Default to the gateway entrypoint
EXPOSE 8000
COPY entrypoint.sh /app/entrypoint.sh
CMD ["/app/entrypoint.sh"]
