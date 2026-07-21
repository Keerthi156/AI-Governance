"""
Analytics HTTP routes.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.user import User
from app.schemas.analytics import AnalyticsOverviewResponse
from app.services.analytics_service import get_analytics_overview

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=AnalyticsOverviewResponse)
def analytics_overview(
    organization_slug: str = Query(default="default"),
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("analytics:read")),
) -> AnalyticsOverviewResponse:
    """Return usage, cost, reliability, and routing analytics for the dashboard."""
    return get_analytics_overview(
        db,
        organization_slug=organization_slug,
        days=days,
    )
