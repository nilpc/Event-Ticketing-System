# Multi-stage Dockerfile for the Python backend.
# Build from monorepo root:
#   docker compose build backend
# Or standalone:
#   docker build -t event-ticketing-backend -f apps/backend/Dockerfile apps/backend/
#
# Dev dependencies (pytest, ruff, mypy, locust, etc.) are excluded
# from the production image to keep it lightweight.

# -- Stage 1: build wheels -----------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libffi-dev && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN mkdir -p core services && touch core/__init__.py services/__init__.py

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# -- Stage 2: production image --------------------------------------------
FROM python:3.11-slim AS production

RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 libssl3 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app"

RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app

WORKDIR /app

COPY core/         ./core/
COPY services/     ./services/
COPY migrations/   ./migrations/
COPY alembic.ini   ./
COPY seed.py       ./

RUN mkdir -p certs && \
    if [ ! -f certs/private.pem ]; then \
        openssl genrsa -out certs/private.pem 2048 2>/dev/null && \
        openssl rsa -in certs/private.pem -pubout -out certs/public.pem 2>/dev/null; \
    fi

RUN chown -R app:app /app

COPY --chmod=755 entrypoint.sh /app/entrypoint.sh
RUN sed -i 's/\r$//' /app/entrypoint.sh

USER app

EXPOSE 8000
CMD ["/app/entrypoint.sh"]
