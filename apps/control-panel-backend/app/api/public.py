"""
Public API endpoints (no authentication required)

Handles public-facing endpoints like tenant info for branding.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.database import get_db
from app.models.tenant import Tenant

logger = structlog.get_logger()
router = APIRouter(tags=["public"])


# Pydantic models
class TenantInfoResponse(BaseModel):
    name: str
    domain: str


# API endpoints
@router.get("/tenant-info", response_model=TenantInfoResponse)
async def get_tenant_info(
    tenant_domain: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get public tenant information for branding (no authentication required)

    Used by tenant login page to display tenant name.
    Fails fast if tenant name is not configured (no fallbacks).

    Args:
        tenant_domain: Tenant domain identifier (e.g., "test-company")

    Returns:
        Tenant name and domain

    Raises:
        HTTP 404: Tenant not found
        HTTP 500: Tenant name not configured
    """
    try:
        # Query tenant by domain
        stmt = select(Tenant).where(Tenant.domain == tenant_domain)
        result = await db.execute(stmt)
        tenant = result.scalar_one_or_none()

        # Check if tenant exists
        if not tenant:
            logger.warning("Tenant not found", domain=tenant_domain)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant not found: {tenant_domain}"
            )

        # Validate tenant name exists (fail fast - no fallback)
        if not tenant.name or not tenant.name.strip():
            logger.error("Tenant name not configured", tenant_id=tenant.id, domain=tenant_domain)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Tenant configuration error: tenant name not set"
            )

        logger.info("Tenant info retrieved", domain=tenant_domain, name=tenant.name)

        return TenantInfoResponse(
            name=tenant.name,
            domain=tenant.domain
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving tenant info", domain=tenant_domain, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve tenant information"
        )
