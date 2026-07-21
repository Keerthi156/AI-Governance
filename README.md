# AI_GOVERNANCE
## Enterprise AI Governance & Multi-LLM Intelligence Platform

Production-oriented platform for organizations to compare LLMs, route prompts, monitor usage, estimate costs, enforce governance policies, audit AI activity, run enterprise RAG, orchestrate agents, and analyze performance.

---

## Architecture overview

```
AI_GOVERNANCE/
├── frontend/          # Next.js (App Router) + TypeScript + Tailwind
├── backend/           # FastAPI + SQLAlchemy + PostgreSQL
├── infra/aws/         # Terraform (ECS Fargate + RDS + ALB)
├── scripts/           # Deploy helpers (aws-push-and-deploy.sh)
├── .github/workflows/ # CI + AWS deploy
├── docker-compose.yml # Local Postgres + API + UI
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
| Database     | PostgreSQL                          |
| Auth         | JWT (Phase 3)                       |
| AI Providers | OpenAI, Claude, Gemini              |
| Deploy       | Docker, CI/CD, AWS (Phase 6)        |

---

## Development phases

| Phase | Focus |
|-------|--------|
| 1 | Project setup, Arena Mode, cost/token tracking, prompt history |
| 2 | Evaluation engine, task router, analytics |
| 3 | Auth, RBAC, governance, audit logs |
| 4 | Enterprise RAG + vector DB |
| 5 | AI agents + workflow orchestration |
| 6 | Docker, CI/CD, AWS |

---

## Prerequisites

- Node.js 20+
- Python 3.11+
- PostgreSQL 15+ with **pgvector** for ANN RAG (Docker: `pgvector/pgvector:pg16`). Without the extension, RAG still works via JSONB + Python cosine fallback.
- API keys for OpenAI / Anthropic / Google (when integrating LLMs)

---

## Quick start (Step 1 — scaffolding)

### Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Health check: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App: [http://localhost:3000](http://localhost:3000)

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

The backend container waits for Postgres, runs `alembic upgrade head`, then starts Uvicorn.

Stop:

```bash
docker compose down
```

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
