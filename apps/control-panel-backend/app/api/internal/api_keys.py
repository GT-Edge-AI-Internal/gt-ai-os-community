"""
Internal API for service-to-service API key retrieval
"""
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.services.api_key_service import APIKeyService
from app.core.config import settings

router = APIRouter(prefix="/internal/api-keys", tags=["Internal API Keys"])


async def verify_service_auth(
    x_service_auth: str = Header(None),
    x_service_name: str = Header(None)
) -> bool:
    """Verify service-to-service authentication"""
    
    if not x_service_auth or not x_service_name:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Service authentication required"
        )
    
    # Verify service token (in production, use proper service mesh auth)
    expected_token = settings.SERVICE_AUTH_TOKEN or "internal-service-token"
    if x_service_auth != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service authentication"
        )
    
    # Verify service is allowed
    allowed_services = ["resource-cluster", "tenant-backend"]
    if x_service_name not in allowed_services:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Service {x_service_name} not authorized"
        )
    
    return True


@router.get("/{tenant_identifier}/{provider}")
async def get_tenant_api_key(
    tenant_identifier: str,
    provider: str,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_service_auth)
):
    """
    Internal endpoint for services to get decrypted tenant API keys.

    tenant_identifier can be:
    - Integer tenant_id (e.g., "1")
    - Tenant domain (e.g., "test-company")
    """
    from sqlalchemy import select
    from app.models.tenant import Tenant

    # Resolve tenant - check if it's numeric or domain
    if tenant_identifier.isdigit():
        tenant_id = int(tenant_identifier)
    else:
        # Look up by domain
        result = await db.execute(
            select(Tenant).where(Tenant.domain == tenant_identifier)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant '{tenant_identifier}' not found"
            )
        tenant_id = tenant.id

    service = APIKeyService(db)

    try:
        key_info = await service.get_decrypted_key(tenant_id, provider, require_enabled=True)

        return {
            "api_key": key_info["api_key"],
            "api_secret": key_info.get("api_secret"),
            "metadata": key_info.get("metadata", {})
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve API key: {str(e)}"
        )