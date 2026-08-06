set -e
echo "==> Writing JWT keys from environment..."
if [ -n "$JWT_PRIVATE_KEY" ]; then
    echo "$JWT_PRIVATE_KEY" > certs/private.pem
    chmod 600 certs/private.pem
    echo "    Written private key from JWT_PRIVATE_KEY env var"
fi
if [ -n "$JWT_PUBLIC_KEY" ]; then
    echo "$JWT_PUBLIC_KEY" > certs/public.pem
    echo "    Written public key from JWT_PUBLIC_KEY env var"
fi
if [ ! -f certs/private.pem ] || [ ! -f certs/public.pem ]; then
    echo "    WARN: No JWT keys found — generating ephemeral keys (dev mode)"
    openssl genrsa -out certs/private.pem 2048 2>/dev/null
    openssl rsa -in certs/private.pem -pubout -out certs/public.pem 2>/dev/null
fi
if [ "${RUN_DB_INIT:-true}" = "true" ]; then
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
else
    echo "==> RUN_DB_INIT=false — skipping migrations/seed (managed by k8s initContainer/Job)"
fi
echo "==> Starting server..."
exec gunicorn services.gateway.app:create_app --bind 0.0.0.0:8000 --workers 2 --worker-class uvicorn.workers.UvicornWorker "$@"
