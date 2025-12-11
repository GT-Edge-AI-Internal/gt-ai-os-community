"""
Internal API endpoints for service-to-service communication.

These endpoints are used by Control Panel to notify Resource Cluster
of configuration changes that require cache invalidation.
"""
from fastapi import APIRouter, Header, HTTPException, status
from typing import Optional
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/internal", tags=["Internal"])

settings = get_settings()


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

    expected_token = settings.service_auth_token or "internal-service-token"
    if x_service_auth != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service authentication"
        )

    allowed_services = ["control-panel-backend", "control-panel"]
    if x_service_name not in allowed_services:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Service {x_service_name} not authorized"
        )

    return True


@router.post("/cache/api-keys/invalidate")
async def invalidate_api_key_cache(
    tenant_domain: Optional[str] = None,
    provider: Optional[str] = None,
    x_service_auth: str = Header(None),
    x_service_name: str = Header(None)
):
    """
    Invalidate cached API keys.

    Called by Control Panel when API keys are added, updated, or removed.

    Args:
        tenant_domain: If provided, only invalidate for this tenant
        provider: If provided with tenant_domain, only invalidate this provider
    """
    await verify_service_auth(x_service_auth, x_service_name)

    from app.clients.api_key_client import get_api_key_client

    client = get_api_key_client()
    await client.invalidate_cache(tenant_domain=tenant_domain, provider=provider)

    logger.info(
        f"Cache invalidated: tenant={tenant_domain or 'all'}, provider={provider or 'all'}"
    )

    return {
        "success": True,
        "message": f"Cache invalidated for tenant={tenant_domain or 'all'}, provider={provider or 'all'}"
    }


@router.get("/cache/api-keys/stats")
async def get_api_key_cache_stats(
    x_service_auth: str = Header(None),
    x_service_name: str = Header(None)
):
    """Get API key cache statistics for monitoring"""
    await verify_service_auth(x_service_auth, x_service_name)

    from app.clients.api_key_client import get_api_key_client

    client = get_api_key_client()
    return client.get_cache_stats()
