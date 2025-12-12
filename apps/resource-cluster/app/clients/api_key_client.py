"""
API Key Client for fetching tenant-specific API keys from Control Panel.

This client handles:
- Fetching decrypted API keys from Control Panel's internal API
- 5-minute in-memory caching to reduce database calls
- Service-to-service authentication
- NO FALLBACKS - per GT 2.0 principles
"""
import asyncio
import logging
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
import httpx

logger = logging.getLogger(__name__)


@dataclass
class CachedAPIKey:
    """Cached API key entry with expiration tracking"""
    api_key: str
    api_secret: Optional[str]
    metadata: Dict[str, Any]
    fetched_at: float

    def is_expired(self, ttl_seconds: int = 300) -> bool:
        """Check if cache entry has expired (default 5 minutes)"""
        return (time.time() - self.fetched_at) > ttl_seconds


class APIKeyNotConfiguredError(Exception):
    """Raised when no API key is configured for a tenant/provider"""
    pass


class APIKeyClient:
    """
    Client for fetching tenant API keys from Control Panel.

    Features:
    - 5-minute TTL cache for API keys
    - Service-to-service authentication
    - NO fallback to environment variables (per GT 2.0 NO FALLBACKS principle)
    """

    CACHE_TTL_SECONDS = 300  # 5 minutes

    def __init__(
        self,
        control_panel_url: str,
        service_auth_token: str,
        service_name: str = "resource-cluster"
    ):
        self.control_panel_url = control_panel_url.rstrip('/')
        self.service_auth_token = service_auth_token
        self.service_name = service_name

        # In-memory cache: key = "{tenant_domain}:{provider}"
        self._cache: Dict[str, CachedAPIKey] = {}
        self._cache_lock = asyncio.Lock()

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for service-to-service authentication"""
        return {
            "X-Service-Auth": self.service_auth_token,
            "X-Service-Name": self.service_name,
            "Content-Type": "application/json"
        }

    async def get_api_key(
        self,
        tenant_domain: str,
        provider: str
    ) -> Dict[str, Any]:
        """
        Get decrypted API key for a tenant and provider.

        Args:
            tenant_domain: Tenant domain string (e.g., "test-company")
            provider: API provider name (e.g., "groq")

        Returns:
            Dict with 'api_key', 'api_secret' (optional), 'metadata'

        Raises:
            APIKeyNotConfiguredError: If API key not configured or disabled
            RuntimeError: If Control Panel unreachable
        """
        cache_key = f"{tenant_domain}:{provider}"

        # Check cache first
        async with self._cache_lock:
            if cache_key in self._cache:
                cached = self._cache[cache_key]
                if not cached.is_expired(self.CACHE_TTL_SECONDS):
                    logger.debug(f"API key cache hit for {cache_key}")
                    return {
                        "api_key": cached.api_key,
                        "api_secret": cached.api_secret,
                        "metadata": cached.metadata
                    }

        # Fetch from Control Panel
        url = f"{self.control_panel_url}/internal/api-keys/{tenant_domain}/{provider}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=self._get_headers())

                if response.status_code == 404:
                    raise APIKeyNotConfiguredError(
                        f"No API key configured for provider '{provider}' "
                        f"for tenant '{tenant_domain}'. "
                        f"Please configure a {provider.upper()} API key in the Control Panel."
                    )

                if response.status_code == 401:
                    raise RuntimeError("Service authentication failed - check SERVICE_AUTH_TOKEN")

                if response.status_code == 403:
                    raise RuntimeError(f"Service '{self.service_name}' not authorized")

                response.raise_for_status()
                data = response.json()

                # Update cache
                async with self._cache_lock:
                    self._cache[cache_key] = CachedAPIKey(
                        api_key=data["api_key"],
                        api_secret=data.get("api_secret"),
                        metadata=data.get("metadata", {}),
                        fetched_at=time.time()
                    )

                logger.info(f"Fetched API key for tenant '{tenant_domain}' provider '{provider}'")
                return {
                    "api_key": data["api_key"],
                    "api_secret": data.get("api_secret"),
                    "metadata": data.get("metadata", {})
                }

        except httpx.HTTPStatusError as e:
            logger.error(f"Control Panel API error: {e.response.status_code}")
            if e.response.status_code == 404:
                raise APIKeyNotConfiguredError(
                    f"No API key configured for provider '{provider}' "
                    f"for tenant '{tenant_domain}'"
                )
            raise RuntimeError(f"Control Panel API error: HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Control Panel unreachable: {e}")
            raise RuntimeError(f"Control Panel unreachable at {self.control_panel_url}")

    async def invalidate_cache(
        self,
        tenant_domain: Optional[str] = None,
        provider: Optional[str] = None
    ):
        """
        Invalidate cached entries.

        Args:
            tenant_domain: If provided, only invalidate for this tenant
            provider: If provided with tenant_domain, only invalidate this provider
        """
        async with self._cache_lock:
            if tenant_domain is None:
                # Clear all
                self._cache.clear()
                logger.info("Cleared all API key caches")
            elif provider:
                # Clear specific tenant+provider
                cache_key = f"{tenant_domain}:{provider}"
                if cache_key in self._cache:
                    del self._cache[cache_key]
                    logger.info(f"Cleared cache for {cache_key}")
            else:
                # Clear all for tenant
                keys_to_remove = [k for k in self._cache if k.startswith(f"{tenant_domain}:")]
                for key in keys_to_remove:
                    del self._cache[key]
                logger.info(f"Cleared cache for tenant: {tenant_domain}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring"""
        now = time.time()
        valid_count = sum(
            1 for k in self._cache.values()
            if not k.is_expired(self.CACHE_TTL_SECONDS)
        )

        return {
            "total_entries": len(self._cache),
            "valid_entries": valid_count,
            "cache_ttl_seconds": self.CACHE_TTL_SECONDS
        }


# Singleton instance
_api_key_client: Optional[APIKeyClient] = None


def get_api_key_client() -> APIKeyClient:
    """Get or create the singleton API key client"""
    global _api_key_client

    if _api_key_client is None:
        from app.core.config import get_settings
        settings = get_settings()

        _api_key_client = APIKeyClient(
            control_panel_url=settings.control_panel_url,
            service_auth_token=settings.service_auth_token,
            service_name="resource-cluster"
        )

    return _api_key_client
