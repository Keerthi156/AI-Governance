"""
Compliance report HTTP routes.
"""

import json

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.user import User
from app.schemas.compliance import ComplianceReportResponse
from app.services.audit_service import record_event
from app.services.compliance_service import build_compliance_report

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get("/report", response_model=ComplianceReportResponse)
def get_compliance_report(
    organization_slug: str = Query(default="default"),
    days: int = Query(default=30, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("compliance:read")),
) -> ComplianceReportResponse:
    """Return an in-browser compliance posture report for an organization."""
    return build_compliance_report(
        db,
        actor=current_user,
        organization_slug=organization_slug,
        days=days,
    )


@router.get("/report/export")
def export_compliance_report(
    request: Request,
    organization_slug: str = Query(default="default"),
    days: int = Query(default=30, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("compliance:read")),
) -> Response:
    """Download the compliance report as a JSON file."""
    report = build_compliance_report(
        db,
        actor=current_user,
        organization_slug=organization_slug,
        days=days,
    )
    body = json.dumps(report.model_dump(mode="json"), indent=2, default=str)
    record_event(
        action="compliance.report_export",
        status="success",
        actor=current_user,
        organization_id=report.organization_id,
        resource_type="compliance_report",
        request_id=getattr(request.state, "request_id", None),
        summary=f"Exported compliance report for {report.organization_slug}",
        details={"days": days, "organization_slug": report.organization_slug},
    )
    filename = f"compliance-{report.organization_slug}-{days}d.json"
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
