#!/usr/bin/env sh
# Production start helper for Render (Native Python) or local prod-like runs.
# Expects working directory = backend/ (alembic.ini + app/ present).
# Does not change application logic — migrate then serve.
set -e

PORT="${PORT:-8000}"

echo "Running Alembic migrations..."
alembic upgrade head

echo "Starting Uvicorn on 0.0.0.0:${PORT}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
