# AI_GOVERNANCE
## Enterprise AI Governance & Multi-LLM Intelligence Platform

Production-oriented platform for organizations to compare LLMs, route prompts, monitor usage, estimate costs, enforce governance policies, audit AI activity, run enterprise RAG, orchestrate agents, and analyze performance.

**Public repo:** https://github.com/Keerthi156/AI-Governance

---

## Architecture overview

```
AI_GOVERNANCE/
├── frontend/          # Next.js (App Router) + TypeScript + Tailwind
├── backend/           # FastAPI + SQLAlchemy + PostgreSQL
├── infra/aws/         # Terraform (ECS Fargate + RDS + ALB)
├── docs/              # Deployment guides
├── scripts/           # Deploy helpers
├── .github/workflows/ # CI + AWS deploy
├── docker-compose.yml # Local Postgres + API + UI
├── render.yaml        # Render Blueprint (API)
├── .env.example
├── .gitignore
└── README.md
```

**Pattern:** Modular monolith — one FastAPI service with domain modules (`arena`, `governance`, `rag`, `agents`). Easy to split into microservices later without rewriting business logic.

**Communication:** Frontend → REST/JSON → Backend → LLM providers / PostgreSQL / vector store.

---

## Tech stack

| Layer        | Technology                          |
|--------------|-------------------------------------|
| Frontend     | Next.js, React, TypeScript, Tailwind, Recharts |
| Backend      | Python, FastAPI, SQLAlchemy         |
| Database     | PostgreSQL (+ pgvector for RAG ANN) |
| Auth         | JWT + RBAC                          |
| AI Providers | OpenAI, Claude, Gemini, Groq        |
| Deploy       | Docker, Vercel, Render, Neon, AWS   |

---

## Demo accounts (local / seeded API)

After the API starts against a migrated database, these users are created if missing:

| Role   | Email                 | Password     |
|--------|-----------------------|--------------|
| Admin  | `demo@example.com`    | `changeme123` |
| Member | `member@example.com`  | `changeme123` |
| Viewer | `viewer@example.com`  | `changeme123` |

Self-registration joins the default org as **member** (not admin).

---

## Prerequisites

- Node.js 20+
- Python 3.11+ (3.12 recommended for deploy)
- PostgreSQL 15+ with **pgvector** for ANN RAG (Docker: `pgvector/pgvector:pg16`). Without the extension, RAG still works via JSONB + Python cosine fallback.
- API keys for OpenAI / Anthropic / Google / Groq (when integrating LLMs)

---

## Quick start (local)

### Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
# Copy backend/.env.example → backend/.env and set DATABASE_URL + JWT_SECRET_KEY
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Health check: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### Frontend

```bash
cd frontend
npm install
# Copy frontend/.env.example → frontend/.env.local
npm run dev
```

App: [http://localhost:3000](http://localhost:3000)

If the UI ever loads **without styles**, delete `frontend/.next` and restart `npm run dev` (stale build cache).

---

## Docker (local full stack)

Requires Docker Desktop / Docker Engine with Compose v2.

```bash
# From repo root — pass provider keys as needed
set GROQ_API_KEY=your_key   # Windows PowerShell: $env:GROQ_API_KEY="..."
docker compose up --build
```

| Service  | URL |
|----------|-----|
| Frontend | http://localhost:3000 |
| Backend  | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| Postgres | localhost:5432 (`ai_governance` / `ai_governance_dev`) |

The backend container waits for Postgres, runs `alembic upgrade head`, then starts Uvicorn on `${PORT:-8000}`.

Stop:

```bash
docker compose down
```

---

## Deploy (portfolio): Neon + Render + Vercel

Recommended public demo path:

1. **Neon** — managed Postgres (`DATABASE_URL` with `postgresql+psycopg2://` + `sslmode=require`)
2. **Render** — FastAPI via [`render.yaml`](render.yaml) / `backend/scripts/start-prod.sh` (migrates then serves on `$PORT`)
3. **Vercel** — Next.js with Root Directory `frontend` and `NEXT_PUBLIC_API_BASE_URL` pointing at Render

**Full step-by-step:** [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)

Do not commit real `.env` files. Secrets live only in platform dashboards.

---

## CI/CD

GitHub Actions workflow: `.github/workflows/ci.yml`

On push/PR to `main`/`master`:

1. Backend — install deps, `compileall`, import FastAPI app
2. Frontend — `npm ci`, lint, production build
3. Docker — `docker compose config` + build backend/frontend images

AWS deploy (manual): `.github/workflows/deploy-aws.yml` — ECR + ECS via **OIDC** (or legacy access keys).  
Infra docs: [`infra/aws/README.md`](infra/aws/README.md)

---

## Environment variables

Copy `.env.example` to `backend/.env` and `frontend/.env.local` as needed. Never commit real secrets. For Compose, export `GROQ_API_KEY` / `JWT_SECRET_KEY` in the shell or a root `.env` file (Compose auto-loads it for substitution).

| Area | Critical variables |
|------|--------------------|
| Backend | `DATABASE_URL`, `JWT_SECRET_KEY`, `CORS_ORIGINS` |
| Frontend | `NEXT_PUBLIC_API_BASE_URL` |
| LLM (optional) | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `GROQ_API_KEY` |

Rate limiting (optional overrides):

```bash
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=120          # global per identity / 60s
RATE_LIMIT_WINDOW_SECONDS=60
RATE_LIMIT_LLM_REQUESTS=30      # /llm /arena /rag/query /agents/runs
RATE_LIMIT_LLM_WINDOW_SECONDS=60
```

Scheduled retention purge (optional overrides):

```bash
RETENTION_SCHEDULER_ENABLED=true
RETENTION_SCHEDULER_INTERVAL_SECONDS=3600
RETENTION_SCHEDULER_INITIAL_DELAY_SECONDS=30
```

Webhook delivery retries (optional overrides):

```bash
WEBHOOK_MAX_ATTEMPTS=3
WEBHOOK_RETRY_BASE_SECONDS=30
WEBHOOK_RETRY_WORKER_ENABLED=true
WEBHOOK_RETRY_WORKER_INTERVAL_SECONDS=15
```
