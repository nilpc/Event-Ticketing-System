#!/bin/sh
set -e

echo "==> Checking database..."
python -c "
import os, asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check():
    engine = create_async_engine(os.getenv('DATABASE_URL'))
    async with engine.begin() as conn:
        r = await conn.execute(text(
            \"SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name='booking')\"
        ))
        if not r.scalar():
            print('    Schema missing — stamping alembic to base')
            await conn.execute(text('DROP SCHEMA IF EXISTS alembic CASCADE'))
        else:
            r2 = await conn.execute(text(
                \"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='outbox_events' AND table_schema='booking')\"
            ))
            if not r2.scalar():
                print('    Tables missing — stamping alembic to base')
                await conn.execute(text('DROP SCHEMA IF EXISTS alembic CASCADE'))
            else:
                print('    Database OK')
    await engine.dispose()

asyncio.run(check())
"

echo "==> Running migrations..."
alembic upgrade head

echo "==> Seeding database..."
python seed.py

echo "==> Starting server..."
exec gunicorn services.gateway.app:create_app \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers 2 \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile -
