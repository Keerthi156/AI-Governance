"""Platform metadata response schema."""

from pydantic import BaseModel, Field


class MetaResponse(BaseModel):
    """Public platform metadata for clients and ops dashboards."""

    name: str = Field(..., examples=["AI_GOVERNANCE"])
    version: str = Field(..., examples=["0.1.0"])
    environment: str = Field(..., examples=["development"])
    api_version: str = Field(..., examples=["v1"])
    docs_url: str = Field(..., examples=["/docs"])
    health_url: str = Field(..., examples=["/api/v1/health"])
    features: list[str] = Field(
        default_factory=list,
        description="Enabled capability flags (grows as phases ship)",
    )
