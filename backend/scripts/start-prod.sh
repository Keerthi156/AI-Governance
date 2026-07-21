#!/usr/bin/env sh
# Production start for Render (Native Python) and Docker-adjacent deploys.
# Working directory must be backend/ (alembic.ini + app/ present).
# Always migrate before serving — empty Neon DBs have no tables until this runs.
set -e

PORT="${PORT:-8000}"

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL is not set. Cannot run migrations." >&2
  exit 1
fi

echo "==> AI_GOVERNANCE: alembic upgrade head"
alembic upgrade head
echo "==> Migrations complete."

echo "==> Starting Uvicorn on 0.0.0.0:${PORT}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
