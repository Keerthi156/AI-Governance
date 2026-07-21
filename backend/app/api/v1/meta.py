"""
Platform metadata endpoint.

Why this exists:
- Lets the frontend discover API version and enabled features without hardcoding.
- Useful for support screens and future feature-flag gating.
"""

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.constants import API_VERSION, APP_VERSION
from app.schemas.meta import MetaResponse

router = APIRouter(tags=["meta"])


@router.get("/meta", response_model=MetaResponse)
def get_meta() -> MetaResponse:
    """Return public platform metadata."""
    settings = get_settings()
    return MetaResponse(
        name=settings.app_name,
        version=APP_VERSION,
        environment=settings.app_env,
        api_version=API_VERSION,
        docs_url="/docs",
        health_url=f"{settings.api_v1_prefix}/health",
        features=[
            "health_check",
            "readiness_check",
            "structured_errors",
            "request_logging",
            "postgresql",
            "alembic_migrations",
            "openai_completions",
            "openai_completions_stream",
            "claude_completions",
            "gemini_completions",
            "groq_completions",
            "arena_mode",
            "prompt_history",
            "evaluation_engine",
            "enhanced_evaluation",
            "intelligent_task_router",
            "analytics_dashboard",
            "jwt_authentication",
            "rbac",
            "governance_policies",
            "audit_logs",
            "audit_log_export",
            "prompt_templates",
            "api_rate_limiting",
            "enterprise_rag",
            "enterprise_rag_pgvector",
            "enterprise_rag_file_upload",
            "enterprise_rag_docx_upload",
            "ai_agents",
            "ai_agents_freeform_planner",
            "ai_agents_llm_planner",
            "docker_compose",
            "github_actions_ci",
            "aws_ecs_fargate",
            "aws_alb_https_acm",
            "aws_rds_multi_az",
            "aws_alb_waf",
            "aws_terraform_remote_state",
            "aws_github_actions_oidc",
            "aws_alb_ingress_cidr_allowlist",
            "aws_cloudwatch_alarms",
            "aws_budgets",
            "organization_switcher",
            "governance_spend_budgets",
            "organization_memberships",
            "platform_api_keys",
            "governance_pii_scanning",
            "byok_provider_credentials",
            "audit_webhooks",
            "data_retention",
            "compliance_report",
            "retention_scheduled_purge",
            "webhook_delivery_retries",
            "organization_invites",
            "governance_spend_soft_warn",
            "refresh_tokens",
        ],
    )
