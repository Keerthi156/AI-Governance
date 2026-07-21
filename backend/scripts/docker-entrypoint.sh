#!/bin/sh
set -e

echo "Waiting for database..."
python - <<'PY'
import os
import time
from sqlalchemy import create_engine, text

url = os.environ.get("DATABASE_URL", "")
if not url:
    raise SystemExit("DATABASE_URL is required")

engine = create_engine(url, pool_pre_ping=True)
for attempt in range(60):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Database is ready.")
        break
    except Exception as exc:  # noqa: BLE001
        print(f"DB not ready ({attempt + 1}/60): {exc}")
        time.sleep(2)
else:
    raise SystemExit("Database did not become ready in time")
PY

echo "Running Alembic migrations..."
alembic upgrade head

echo "Starting API..."
exec "$@"
