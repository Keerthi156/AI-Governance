#!/usr/bin/env sh
# Convenience wrapper from repo root for production-like backend start.
# Usage (from repo root):
#   export DATABASE_URL=...
#   export JWT_SECRET_KEY=...
#   ./scripts/start-backend-prod.sh
set -e

ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"

if [ ! -f "scripts/start-prod.sh" ]; then
  echo "Missing backend/scripts/start-prod.sh" >&2
  exit 1
fi

exec sh scripts/start-prod.sh
