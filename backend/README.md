# AI_GOVERNANCE — Backend

Python FastAPI service for the Enterprise AI Governance platform.

## Layout

```
backend/
├── app/
│   ├── main.py                 # FastAPI app factory + ASGI entry
│   ├── api/v1/                 # Versioned HTTP routes
│   │   ├── health.py           # GET /health (live) + GET /ready (DB)
│   │   ├── meta.py             # GET /api/v1/meta
│   │   └── router.py           # Aggregates v1 routers
│   ├── core/
│   │   ├── config.py           # Typed settings (pydantic-settings)
│   │   ├── constants.py        # APP_VERSION / API_VERSION
│   │   ├── database.py         # SQLAlchemy engine/session + DB probe
│   │   ├── exceptions.py       # Domain AppException hierarchy
│   │   ├── error_handlers.py   # Unified JSON error responses
│   │   └── logging.py          # Process logging setup
│   ├── middleware/
│   │   └── request_logging.py  # X-Request-ID + duration logs
│   ├── models/                 # SQLAlchemy ORM
│   │   ├── organization.py
│   │   └── prompt_history.py
│   ├── schemas/                # Pydantic request/response models
│   ├── services/               # Business logic (later steps)
│   └── integrations/           # LLM provider clients (later steps)
├── alembic/                    # DB migrations
├── scripts/bootstrap_postgres.py
├── alembic.ini
├── requirements.txt
├── .env.example
└── .env                        # Local secrets (gitignored)
```

## Database setup (Step 3)

PostgreSQL 18 is expected on `127.0.0.1:5433` (local install).

1. Bootstrap role + database (needs your postgres superuser password):

```bash
.\.venv\Scripts\python.exe scripts\bootstrap_postgres.py --admin-password YOUR_POSTGRES_PASSWORD --port 5433
```

2. Apply migrations:

```bash
.\.venv\Scripts\alembic.exe upgrade head
```

3. Verify readiness: http://localhost:8000/api/v1/ready

## OpenAI / Arena (Steps 4–5)

1. Set provider keys in `backend/.env`:
   - `OPENAI_API_KEY`
   - `ANTHROPIC_API_KEY` (optional)
   - `GOOGLE_API_KEY` (optional)
2. Restart the API process
3. Single completion: `POST /api/v1/llm/completions`
4. Arena compare: `POST /api/v1/arena/runs`
5. History: `GET /api/v1/history`, `GET /api/v1/history/{id}`, `GET /api/v1/history/arena/{arena_run_id}`
6. UI: http://localhost:3000

## Run

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Health: http://localhost:8000/api/v1/health
- Docs: http://localhost:8000/docs

## Production start (Render / containers)

```bash
# From backend/ — runs alembic upgrade head, then uvicorn on ${PORT:-8000}
sh scripts/start-prod.sh
```

See [`docs/DEPLOYMENT.md`](../docs/DEPLOYMENT.md) for Neon + Render + Vercel.
