"""
Resource Cluster Client for service-to-service communication.

Used by Control Panel to notify Resource Cluster of configuration changes
that require cache invalidation (e.g., API key changes).
"""
import logging
from typing import Optional
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class ResourceClusterClient:
    """Client for communicating with Resource Cluster internal APIs"""

    def __init__(
        self,
        resource_cluster_url: str,
        service_auth_token: str,
        service_name: str = "control-panel-backend"
    ):
        self.resource_cluster_url = resource_cluster_url.rstrip('/')
        self.service_auth_token = service_auth_token
        self.service_name = service_name

    def _get_headers(self) -> dict:
        """Get headers for service-to-service authentication"""
        return {
            "X-Service-Auth": self.service_auth_token,
            "X-Service-Name": self.service_name,
            "Content-Type": "application/json"
        }

    async def invalidate_api_key_cache(
        self,
        tenant_domain: Optional[str] = None,
        provider: Optional[str] = None
    ) -> bool:
        """
        Notify Resource Cluster to invalidate API key cache.

        Called when API keys are added, updated, disabled, or removed.

        Args:
            tenant_domain: If provided, only invalidate for this tenant
            provider: If provided with tenant_domain, only invalidate this provider

        Returns:
            True if successful, False otherwise
        """
        url = f"{self.resource_cluster_url}/internal/cache/api-keys/invalidate"

        params = {}
        if tenant_domain:
            params["tenant_domain"] = tenant_domain
        if provider:
            params["provider"] = provider

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    url,
                    params=params,
                    headers=self._get_headers()
                )

                if response.status_code == 200:
                    logger.info(
                        f"Cache invalidation successful: tenant={tenant_domain}, provider={provider}"
                    )
                    return True
                else:
                    logger.warning(
                        f"Cache invalidation failed: {response.status_code} - {response.text}"
                    )
                    return False

        except httpx.RequestError as e:
            # Don't fail the API key operation if cache invalidation fails
            # The cache will expire naturally after TTL
            logger.warning(f"Cache invalidation request failed (non-critical): {e}")
            return False
        except Exception as e:
            logger.warning(f"Cache invalidation error (non-critical): {e}")
            return False


# Singleton instance
_resource_cluster_client: Optional[ResourceClusterClient] = None


def get_resource_cluster_client() -> ResourceClusterClient:
    """Get or create the singleton Resource Cluster client"""
    global _resource_cluster_client

    if _resource_cluster_client is None:
        # Use Docker service name for inter-container communication
        resource_cluster_url = getattr(settings, 'RESOURCE_CLUSTER_URL', None) or "http://resource-cluster:8003"
        service_auth_token = getattr(settings, 'SERVICE_AUTH_TOKEN', None) or "internal-service-token"

        _resource_cluster_client = ResourceClusterClient(
            resource_cluster_url=resource_cluster_url,
            service_auth_token=service_auth_token,
            service_name="control-panel-backend"
        )

    return _resource_cluster_client
