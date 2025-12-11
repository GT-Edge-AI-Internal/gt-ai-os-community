"""
Admin Model Configuration Service for GT 2.0 Resource Cluster

This service fetches model configurations from the Admin Control Panel
and provides them to the Resource Cluster for LLM routing and capabilities.
"""

import asyncio
import logging
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import json

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class AdminModelConfig:
    """Model configuration from admin cluster"""
    uuid: str  # Database UUID - unique identifier for this model config
    model_id: str  # Business identifier - the model name used in API calls
    name: str
    provider: str
    model_type: str
    endpoint: str
    api_key_name: Optional[str]
    context_window: Optional[int]
    max_tokens: Optional[int]
    capabilities: Dict[str, Any]
    cost_per_1k_input: float
    cost_per_1k_output: float
    is_active: bool
    tenant_restrictions: Dict[str, Any]
    required_capabilities: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for LLM Gateway"""
        return {
            "uuid": self.uuid,
            "model_id": self.model_id,
            "name": self.name,
            "provider": self.provider,
            "model_type": self.model_type,
            "endpoint": self.endpoint,
            "api_key_name": self.api_key_name,
            "context_window": self.context_window,
            "max_tokens": self.max_tokens,
            "capabilities": self.capabilities,
            "cost_per_1k_input": self.cost_per_1k_input,
            "cost_per_1k_output": self.cost_per_1k_output,
            "is_active": self.is_active,
            "tenant_restrictions": self.tenant_restrictions,
            "required_capabilities": self.required_capabilities
        }


class AdminModelConfigService:
    """Service for fetching model configurations from Admin Control Panel"""
    
    def __init__(self):
        self.settings = get_settings()
        self._model_cache: Dict[str, AdminModelConfig] = {}  # model_id -> config
        self._uuid_cache: Dict[str, AdminModelConfig] = {}   # uuid -> config (for UUID-based lookups)
        self._tenant_model_cache: Dict[str, List[str]] = {}  # tenant_id -> list of allowed model_ids
        self._last_sync: datetime = datetime.min
        self._sync_interval = timedelta(seconds=self.settings.config_sync_interval)
        self._sync_lock = asyncio.Lock()

    async def get_model_config(self, model_id: str) -> Optional[AdminModelConfig]:
        """Get configuration for a specific model by model_id string"""
        await self._ensure_fresh_cache()
        return self._model_cache.get(model_id)

    async def get_model_by_uuid(self, uuid: str) -> Optional[AdminModelConfig]:
        """Get configuration for a specific model by database UUID"""
        await self._ensure_fresh_cache()
        return self._uuid_cache.get(uuid)
    
    async def get_all_models(self, active_only: bool = True) -> List[AdminModelConfig]:
        """Get all model configurations"""
        await self._ensure_fresh_cache()
        models = list(self._model_cache.values())
        if active_only:
            models = [m for m in models if m.is_active]
        return models
    
    async def get_tenant_models(self, tenant_id: str) -> List[AdminModelConfig]:
        """Get models available to a specific tenant"""
        await self._ensure_fresh_cache()
        
        # Get tenant's allowed model IDs - try multiple formats
        allowed_model_ids = self._get_tenant_model_ids(tenant_id)
        
        # Return model configs for allowed models
        models = []
        for model_id in allowed_model_ids:
            if model_id in self._model_cache and self._model_cache[model_id].is_active:
                models.append(self._model_cache[model_id])
        
        return models
    
    async def check_tenant_access(self, tenant_id: str, model_id: str) -> bool:
        """Check if a tenant has access to a specific model"""
        await self._ensure_fresh_cache()
        
        # Check if model exists and is active
        model_config = self._model_cache.get(model_id)
        if not model_config or not model_config.is_active:
            return False
        
        # Only use tenant-specific access (no global access)
        # This enforces proper tenant model assignments
        allowed_models = self._get_tenant_model_ids(tenant_id)
        return model_id in allowed_models
    
    def _get_tenant_model_ids(self, tenant_id: str) -> List[str]:
        """Get model IDs for tenant, handling multiple tenant ID formats"""
        # Try exact match first (e.g., "test-company")
        allowed_models = self._tenant_model_cache.get(tenant_id, [])
        
        if not allowed_models:
            # Try converting "test-company" to "test" format
            if "-" in tenant_id:
                domain_format = tenant_id.split("-")[0]
                allowed_models = self._tenant_model_cache.get(domain_format, [])
            
            # Try converting "test" to "test-company" format
            elif tenant_id + "-company" in self._tenant_model_cache:
                allowed_models = self._tenant_model_cache.get(tenant_id + "-company", [])
            
            # Also try tenant_id as numeric string
            for key, models in self._tenant_model_cache.items():
                if key.isdigit() and tenant_id in key:
                    allowed_models.extend(models)
                    break
        
        logger.debug(f"Tenant {tenant_id} has access to models: {allowed_models}")
        return allowed_models
    
    async def get_groq_api_key(self, tenant_id: str = None) -> Optional[str]:
        """
        Get Groq API key for a tenant from Control Panel database.

        NO environment variable fallback - per GT 2.0 NO FALLBACKS principle.
        API keys are managed in Control Panel and fetched via internal API.

        Args:
            tenant_id: Tenant domain string (required for tenant requests)

        Returns:
            Decrypted Groq API key

        Raises:
            ValueError: If no API key configured for tenant
        """
        if not tenant_id:
            raise ValueError("tenant_id is required to fetch Groq API key - no fallback to environment variables")

        from app.clients.api_key_client import get_api_key_client, APIKeyNotConfiguredError

        client = get_api_key_client()

        try:
            key_info = await client.get_api_key(tenant_domain=tenant_id, provider="groq")
            return key_info["api_key"]
        except APIKeyNotConfiguredError as e:
            logger.error(f"No Groq API key configured for tenant '{tenant_id}': {e}")
            raise ValueError(f"No Groq API key configured for tenant '{tenant_id}'. Please configure in Control Panel → API Keys.")
        except RuntimeError as e:
            logger.error(f"Control Panel API error when fetching API key: {e}")
            raise ValueError(f"Unable to retrieve API key - Control Panel service unavailable: {e}")
    
    async def _ensure_fresh_cache(self):
        """Ensure model cache is fresh, sync if needed"""
        now = datetime.utcnow()
        if now - self._last_sync > self._sync_interval:
            async with self._sync_lock:
                # Double-check after acquiring lock
                now = datetime.utcnow()
                if now - self._last_sync <= self._sync_interval:
                    return
                    
                await self._sync_from_admin()
    
    async def _sync_from_admin(self):
        """Sync model configurations from admin cluster"""
        try:
            # Use correct URL for containerized environment
            import os
            if os.path.exists('/.dockerenv'):
                admin_url = "http://control-panel-backend:8000"
            else:
                admin_url = self.settings.admin_cluster_url.rstrip('/')
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Fetch all model configurations
                models_response = await client.get(
                    f"{admin_url}/api/v1/models/?active_only=true&include_stats=true"
                )
                
                # Fetch tenant model assignments with proper authentication
                tenant_models_response = await client.get(
                    f"{admin_url}/api/v1/tenant-models/tenants/all",
                    headers={
                        "Authorization": "Bearer admin-dev-token",
                        "Content-Type": "application/json"
                    }
                )
                
                if models_response.status_code == 200:
                    models_data = models_response.json()
                    if models_data and len(models_data) > 0:
                        await self._update_model_cache(models_data)
                        logger.info(f"Successfully synced {len(models_data)} models from admin cluster")
                        
                        # Update tenant model assignments if available
                        if tenant_models_response.status_code == 200:
                            tenant_data = tenant_models_response.json()
                            if tenant_data and len(tenant_data) > 0:
                                await self._update_tenant_cache(tenant_data)
                                logger.info(f"Successfully synced {len(tenant_data)} tenant model assignments")
                            else:
                                logger.warning("No tenant model assignments found")
                        else:
                            logger.error(f"Failed to fetch tenant assignments: {tenant_models_response.status_code}")
                            # Log the actual error for debugging
                            try:
                                error_response = tenant_models_response.json()
                                logger.error(f"Tenant assignments error: {error_response}")
                            except:
                                logger.error(f"Tenant assignments error text: {tenant_models_response.text}")
                        
                        self._last_sync = datetime.utcnow()
                        return
                    else:
                        logger.warning("Admin cluster returned empty model list")
                else:
                    logger.warning(f"Failed to fetch models from admin cluster: {models_response.status_code}")
            
            logger.info("No models configured in admin backend")
            self._last_sync = datetime.utcnow()
            logger.info(f"Loaded {len(self._model_cache)} models successfully")
            
        except Exception as e:
            logger.error(f"Failed to sync from admin cluster: {e}")
            
            # Log final state - no fallback models
            if not self._model_cache:
                logger.warning("No models available - admin backend has no models configured")
    
    async def _update_model_cache(self, models_data: List[Dict[str, Any]]):
        """Update model configuration cache"""
        new_cache = {}
        new_uuid_cache = {}

        for model_data in models_data:
            try:
                specs = model_data.get("specifications", {})
                cost = model_data.get("cost", {})
                status = model_data.get("status", {})

                # Get UUID from 'id' field in API response (Control Panel returns UUID as 'id')
                model_uuid = model_data.get("id", "")

                model_config = AdminModelConfig(
                    uuid=model_uuid,
                    model_id=model_data["model_id"],
                    name=model_data.get("name", model_data["model_id"]),
                    provider=model_data["provider"],
                    model_type=model_data["model_type"],
                    endpoint=model_data.get("endpoint", ""),
                    api_key_name=model_data.get("api_key_name"),
                    context_window=specs.get("context_window"),
                    max_tokens=specs.get("max_tokens"),
                    capabilities=model_data.get("capabilities", {}),
                    cost_per_1k_input=cost.get("per_1k_input", 0.0),
                    cost_per_1k_output=cost.get("per_1k_output", 0.0),
                    is_active=status.get("is_active", False),
                    tenant_restrictions=model_data.get("tenant_restrictions", {"global_access": True}),
                    required_capabilities=model_data.get("required_capabilities", [])
                )

                new_cache[model_config.model_id] = model_config

                # Also index by UUID for UUID-based lookups
                if model_uuid:
                    new_uuid_cache[model_uuid] = model_config

            except Exception as e:
                logger.error(f"Failed to parse model config {model_data.get('model_id', 'unknown')}: {e}")

        self._model_cache = new_cache
        self._uuid_cache = new_uuid_cache
    
    async def _update_tenant_cache(self, tenant_data: List[Dict[str, Any]]):
        """Update tenant model access cache from tenant-models endpoint"""
        new_tenant_cache = {}
        
        for assignment in tenant_data:
            try:
                # The tenant-models endpoint returns different format than the old endpoint
                tenant_domain = assignment.get("tenant_domain", "")
                model_id = assignment["model_id"]
                is_enabled = assignment.get("is_enabled", True)
                
                if is_enabled and tenant_domain:
                    if tenant_domain not in new_tenant_cache:
                        new_tenant_cache[tenant_domain] = []
                    new_tenant_cache[tenant_domain].append(model_id)
                    
                    # Also add by tenant_id for backward compatibility
                    tenant_id = str(assignment.get("tenant_id", ""))
                    if tenant_id and tenant_id not in new_tenant_cache:
                        new_tenant_cache[tenant_id] = []
                    if tenant_id:
                        new_tenant_cache[tenant_id].append(model_id)
                    
            except Exception as e:
                logger.error(f"Failed to parse tenant assignment: {e}")
        
        self._tenant_model_cache = new_tenant_cache
        logger.debug(f"Updated tenant cache: {self._tenant_model_cache}")
    
    async def force_sync(self):
        """Force immediate sync from admin cluster"""
        self._last_sync = datetime.min
        await self._ensure_fresh_cache()


# Global instance
_admin_model_service = None

def get_admin_model_service() -> AdminModelConfigService:
    """Get singleton admin model service"""
    global _admin_model_service
    if _admin_model_service is None:
        _admin_model_service = AdminModelConfigService()
    return _admin_model_service