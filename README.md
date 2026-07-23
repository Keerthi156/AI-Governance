# AI_GOVERNANCE

## Enterprise AI Governance & Multi-LLM Intelligence Platform

AI_GOVERNANCE is a production-ready enterprise platform that helps organizations compare multiple Large Language Models (LLMs), manage AI governance, route prompts, monitor usage, estimate costs, run enterprise RAG, and orchestrate AI agents.

---

## 🌐 Live Demo

**Application:**  
https://ai-governance-ohiiers11-keerthi156s-projects.vercel.app

**Backend API:**  
https://ai-governance-1gix.onrender.com

**API Documentation (Swagger):**  
https://ai-governance-1gix.onrender.com/docs

---

## ✨ Features

- Multi-LLM Comparison (OpenAI, Claude, Gemini, Groq)
- AI Prompt Routing
- AI Governance Policies
- Enterprise RAG
- AI Agent Orchestration
- JWT Authentication & RBAC
- Audit Logs
- Usage & Cost Analytics
- REST API with Swagger Documentation

---

## 🛠 Tech Stack

| Layer | Technology |
|--------|------------|
| Frontend | Next.js, React, TypeScript, Tailwind CSS |
| Backend | FastAPI, Python, SQLAlchemy |
| Database | PostgreSQL (Neon), pgvector |
| Authentication | JWT, RBAC |
| Deployment | Vercel, Render |
| DevOps | Docker, GitHub Actions, Terraform |

---

## 📂 Project Structure

```
AI_GOVERNANCE/
├── frontend/
├── backend/
├── docs/
├── infra/
├── scripts/
├── .github/workflows/
├── docker-compose.yml
├── render.yaml
└── README.md
```

---

## 🚀 Local Setup

### Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt

alembic upgrade head

uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend

npm install

npm run dev
```

---

## 🐳 Docker

```bash
docker compose up --build
```

---

## 🔑 Demo Credentials

| Role | Email | Password |
|------|-------|----------|
| Admin | demo@example.com | changeme123 |
| Member | member@example.com | changeme123 |
| Viewer | viewer@example.com | changeme123 |

---

## 🔧 Environment Variables

### Backend

- DATABASE_URL
- JWT_SECRET_KEY
- CORS_ORIGINS

### Frontend

- NEXT_PUBLIC_API_BASE_URL

### Optional AI Keys

- OPENAI_API_KEY
- ANTHROPIC_API_KEY
- GOOGLE_API_KEY
- GROQ_API_KEY

---

## 🚀 Deployment

- **Frontend:** Vercel
- **Backend:** Render
- **Database:** Neon PostgreSQL

---

## 🤝 Contributing

Contributions and suggestions are welcome.

---

## 👩‍💻 Author

**Keerthi**

GitHub: https://github.com/Keerthi156

Repository: https://github.com/Keerthi156/AI-Governance
