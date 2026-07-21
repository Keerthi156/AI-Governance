"""
API v1 router aggregator.

Why this exists:
- Single mount point for all v1 routes under /api/v1.
- New domains (arena, auth, governance) register here without touching main.py.
"""

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    agents,
    analytics,
    api_keys,
    arena,
    audit,
    auth,
    compliance,
    credentials,
    evaluation,
    governance,
    health,
    history,
    llm,
    meta,
    organizations,
    prompt_templates,
    rag,
    retention,
    router_api,
    webhooks,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(meta.router)
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(organizations.router)
api_router.include_router(api_keys.router)
api_router.include_router(credentials.router)
api_router.include_router(webhooks.router)
api_router.include_router(retention.router)
api_router.include_router(compliance.router)
api_router.include_router(audit.router)
api_router.include_router(governance.router)
api_router.include_router(rag.router)
api_router.include_router(agents.router)
api_router.include_router(prompt_templates.router)
api_router.include_router(llm.router)
api_router.include_router(arena.router)
api_router.include_router(history.router)
api_router.include_router(evaluation.router)
api_router.include_router(router_api.router)
api_router.include_router(analytics.router)
