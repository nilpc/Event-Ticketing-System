#!/bin/sh
set -e

echo "Running migrations..."
alembic upgrade head

echo "Starting server..."
exec gunicorn services.gateway.app:create_app \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers 2 \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile -
