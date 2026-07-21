# Portfolio deployment: Neon + Render + Vercel

This guide deploys **AI Governance** as a public demo without changing application logic.

| Piece | Platform |
|-------|----------|
| Frontend (Next.js) | [Vercel](https://vercel.com) |
| Backend (FastAPI) | [Render](https://render.com) |
| Database (PostgreSQL + pgvector) | [Neon](https://neon.tech) |

Repo: https://github.com/Keerthi156/AI-Governance

Do **not** commit secrets. Configure them only in Neon / Render / Vercel dashboards.

---

## Prerequisites

- GitHub repo connected to your Vercel and Render accounts
- At least one LLM API key (optional for login-only demos; required for Playground/Arena)
- Ability to create a Neon project with the **pgvector** extension

---

## 1. Neon (PostgreSQL)

1. Create a project (pick a region near your Render region).
2. Open **Connection details** → copy the **direct** connection string (prefer non-pooler for a long-lived Render web service).
3. Convert the URL for this app’s SQLAlchemy driver:

   ```text
   # From Neon (example):
   postgresql://USER:PASSWORD@ep-xxx.REGION.aws.neon.tech/neondb?sslmode=require

   # Use on Render as DATABASE_URL:
   postgresql+psycopg2://USER:PASSWORD@ep-xxx.REGION.aws.neon.tech/neondb?sslmode=require
   ```

4. In the Neon SQL Editor, confirm pgvector works:

   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

   Migration `0010_pgvector` also runs this; if the extension is blocked, deploy will fail at migrate time.

---

## 2. Render (FastAPI)

### Option A — Blueprint (recommended)

1. Render Dashboard → **New** → **Blueprint**.
2. Select this repository; Render reads [`render.yaml`](../render.yaml).
3. Fill **secret** env vars (`sync: false` keys) in the UI:

   | Key | Value |
   |-----|--------|
   | `DATABASE_URL` | Neon URL with `postgresql+psycopg2://` + `sslmode=require` |
   | `JWT_SECRET_KEY` | Long random string (32+ characters) |
   | `CORS_ORIGINS` | Your Vercel origin(s), comma-separated (set after Vercel exists; you can use a placeholder then update) |
   | `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` / `GROQ_API_KEY` | Optional provider keys |
   | `CREDENTIAL_ENCRYPTION_KEY` | Optional; defaults to JWT secret if empty |

4. Deploy. The Start Command **must** run migrations before Uvicorn:

   ```bash
   alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

   Equivalent helper: [`backend/scripts/start-prod.sh`](../backend/scripts/start-prod.sh).

   Without this step, Neon has no tables and you will see  
   `relation "organizations" does not exist`.

### Option B — Manual Web Service

| Setting | Value |
|---------|--------|
| Root Directory | `backend` |
| Runtime | Python **3.12** (pinned via `backend/.python-version`, `backend/runtime.txt`, and `PYTHON_VERSION`) |
| Build Command | `pip install -r requirements.txt` |
| Start Command | **`alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`** |
| Health Check Path | `/api/v1/health` |

> **If you already created the service** with a uvicorn-only Start Command, Neon will have **no tables** (`relation "organizations" does not exist`). Update **Settings → Start Command** to the value above (or `sh scripts/start-prod.sh`), then **Manual Deploy**.

Same env vars as above. Also set:

```text
APP_ENV=production
DEBUG=false
```

### Verify backend

```text
https://<your-service>.onrender.com/api/v1/health
https://<your-service>.onrender.com/api/v1/ready
https://<your-service>.onrender.com/docs
```

`/ready` must show database `ok`.

**Cold starts:** Free Render instances sleep; the first request after idle can take 30–60s.

### Docker on Render (optional)

If you deploy the [`backend/Dockerfile`](../backend/Dockerfile) instead of Native Python:

- Entrypoint waits for DB and runs Alembic.
- Process listens on `${PORT:-8000}` (Render injects `PORT`).

---

## 3. Vercel (Next.js)

1. **Add New Project** → import this GitHub repo.
2. **Root Directory:** `frontend` (required for this monorepo).
3. Framework preset: Next.js.
4. Environment variable (Production + Preview as needed):

   | Name | Value |
   |------|--------|
   | `NEXT_PUBLIC_API_BASE_URL` | `https://<your-service>.onrender.com/api/v1` |

   This must be set **before** (or rebuild after) production build — it is inlined at build time.

5. Deploy. Note the URL: `https://<project>.vercel.app`.

[`frontend/vercel.json`](../frontend/vercel.json) only sets install/build hints; root directory is still configured in the Vercel UI.

---

## 4. Wire CORS

On Render, set:

```text
CORS_ORIGINS=https://<project>.vercel.app
```

Multiple origins (production + a custom domain):

```text
CORS_ORIGINS=https://<project>.vercel.app,https://www.example.com
```

Redeploy/restart the Render service after changing CORS. Exact origins only (no trailing slash); `allow_credentials` is enabled in the API.

---

## 5. Smoke test

1. Open the Vercel URL → `/login`.
2. Use a demo account (seeded on API startup when DB is reachable):

   | Role | Email | Password |
   |------|--------|----------|
   | Admin | `demo@example.com` | `changeme123` |
   | Member | `member@example.com` | `changeme123` |
   | Viewer | `viewer@example.com` | `changeme123` |

3. Confirm dashboard loads.
4. (Optional) Playground with a configured provider key.

---

## Environment reference

### Backend (Render)

| Variable | Required | Notes |
|----------|----------|--------|
| `DATABASE_URL` | Yes | `postgresql+psycopg2://…?sslmode=require` |
| `JWT_SECRET_KEY` | Yes | Strong random secret |
| `CORS_ORIGINS` | Yes (for browser UI) | Vercel origin(s) |
| `APP_ENV` | Recommended | `production` |
| `DEBUG` | Recommended | `false` |
| `OPENAI_API_KEY` | Optional | |
| `ANTHROPIC_API_KEY` | Optional | |
| `GOOGLE_API_KEY` | Optional | |
| `GROQ_API_KEY` | Optional | |
| `CREDENTIAL_ENCRYPTION_KEY` | Optional | BYOK encryption material |

### Frontend (Vercel)

| Variable | Required | Notes |
|----------|----------|--------|
| `NEXT_PUBLIC_API_BASE_URL` | Yes | Render API base including `/api/v1` |

See also root [`.env.example`](../.env.example).

---

## Local production-like backend

From repo root (Unix / Git Bash):

```bash
export DATABASE_URL='postgresql+psycopg2://...'
export JWT_SECRET_KEY='...'
export PORT=8000
./scripts/start-backend-prod.sh
```

Or from `backend/`:

```bash
sh scripts/start-prod.sh
```

---

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| Vercel UI loads but API fails / CORS errors | `CORS_ORIGINS` missing Vercel origin, or wrong URL |
| UI calls `localhost:8000` | `NEXT_PUBLIC_API_BASE_URL` not set at **build** time — set and redeploy |
| `/ready` DB error | Bad `DATABASE_URL`, missing `sslmode=require`, or Neon paused |
| `relation "organizations" does not exist` | Migrations never ran — set Start Command to `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT` and redeploy |
| Migrate fails on `vector` | Enable pgvector / `CREATE EXTENSION vector` on Neon |
| First request timeout | Render free-tier cold start — retry once |
| Unstyled local UI | Delete `frontend/.next` and restart `npm run dev` |

---

## AWS (alternative)

For ECS/Fargate + RDS, see [`infra/aws/README.md`](../infra/aws/README.md). That path is separate from Neon/Render/Vercel.
