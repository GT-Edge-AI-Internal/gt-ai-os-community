"""
GT 2.0 Configuration Sync Service

Syncs model configurations from admin cluster to resource cluster.
Enables admin control panel to control AI model routing.
"""

import asyncio
import httpx
import json
import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path

from app.core.config import get_settings
from app.services.model_service import default_model_service
from app.providers.external_provider import get_external_provider

logger = logging.getLogger(__name__)
settings = get_settings()


class ConfigSyncService:
    """Syncs model configurations from admin cluster"""
    
    def __init__(self):
        # Force Docker service name for admin cluster communication in containerized environment
        if hasattr(settings, 'admin_cluster_url') and settings.admin_cluster_url:
            # Check if we're running in Docker (container environment)
            import os
            if os.path.exists('/.dockerenv'):
                self.admin_cluster_url = "http://control-panel-backend:8000"
            else:
                self.admin_cluster_url = settings.admin_cluster_url
        else:
            self.admin_cluster_url = "http://control-panel-backend:8000"
        self.sync_interval = settings.config_sync_interval or 60  # seconds
        # Use the default singleton model service instance
        self.model_service = default_model_service
        self.last_sync = 0
        self.sync_running = False
        
    async def start_sync_loop(self):
        """Start the configuration sync loop"""
        logger.info("Starting configuration sync loop")
        
        while True:
            try:
                if not self.sync_running:
                    await self.sync_configurations()
                await asyncio.sleep(self.sync_interval)
            except Exception as e:
                logger.error(f"Config sync loop error: {e}")
                await asyncio.sleep(30)  # Wait 30s on error
    
    async def sync_configurations(self):
        """Sync model configurations from admin cluster"""
        if self.sync_running:
            return
            
        self.sync_running = True
        
        try:
            logger.debug("Syncing model configurations from admin cluster")

            # Fetch all model configurations from admin cluster
            configs = await self._fetch_admin_configs()

            if configs:
                # Update local model registry
                await self._update_local_registry(configs)

                # Update provider configurations
                await self._update_provider_configs(configs)

                self.last_sync = time.time()
                logger.info(f"Successfully synced {len(configs)} model configurations")
            else:
                logger.warning("No configurations received from admin cluster")
                
        except Exception as e:
            logger.error(f"Configuration sync failed: {e}")
        finally:
            self.sync_running = False
    
    async def _fetch_admin_configs(self) -> Optional[List[Dict[str, Any]]]:
        """Fetch model configurations from admin cluster"""
        try:
            logger.debug(f"Attempting to fetch configs from: {self.admin_cluster_url}/api/v1/models/configs/all")

            async with httpx.AsyncClient(timeout=30.0) as client:
                # Add authentication for admin cluster access
                headers = {
                    "Authorization": "Bearer admin-cluster-sync-token",
                    "Content-Type": "application/json"
                }

                response = await client.get(
                    f"{self.admin_cluster_url}/api/v1/models/configs/all",
                    headers=headers
                )

                logger.debug(f"Admin cluster response: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    configs = data.get("configs", [])
                    logger.debug(f"Successfully fetched {len(configs)} model configurations")
                    return configs
                else:
                    logger.warning(f"Admin cluster returned {response.status_code}: {response.text}")
                    return None
                    
        except httpx.RequestError as e:
            logger.error(f"Failed to connect to admin cluster: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching admin configs: {e}")
            return None
    
    async def _update_local_registry(self, configs: List[Dict[str, Any]]):
        """Update local model registry with admin configurations"""
        try:
            for config in configs:
                await self.model_service.register_or_update_model(
                    model_id=config["model_id"],
                    name=config["name"],
                    version=config["version"],
                    provider=config["provider"],
                    model_type=config["model_type"],
                    endpoint=config["endpoint"],
                    api_key_name=config.get("api_key_name"),
                    specifications=config.get("specifications", {}),
                    capabilities=config.get("capabilities", {}),
                    cost=config.get("cost", {}),
                    description=config.get("description"),
                    config=config.get("config", {}),
                    status=config.get("status", {}),
                    sync_timestamp=config.get("sync_timestamp")
                )

                # Log BGE-M3 configuration details for debugging persistence
                if "bge-m3" in config["model_id"].lower():
                    model_config = config.get("config", {})
                    logger.info(
                        f"Synced BGE-M3 configuration from database: "
                        f"endpoint={config['endpoint']}, "
                        f"is_local_mode={model_config.get('is_local_mode', True)}, "
                        f"external_endpoint={model_config.get('external_endpoint', 'None')}"
                    )

        except Exception as e:
            logger.error(f"Failed to update local registry: {e}")
            raise
    
    async def _update_provider_configs(self, configs: List[Dict[str, Any]]):
        """Update provider configurations based on admin settings"""
        try:
            # Group configs by provider
            provider_configs = {}
            for config in configs:
                provider = config["provider"]
                if provider not in provider_configs:
                    provider_configs[provider] = []
                provider_configs[provider].append(config)
            
            # Update each provider
            for provider, provider_models in provider_configs.items():
                await self._update_provider(provider, provider_models)
                
        except Exception as e:
            logger.error(f"Failed to update provider configs: {e}")
            raise
    
    async def _update_provider(self, provider: str, models: List[Dict[str, Any]]):
        """Update specific provider configuration"""
        try:
            # Generic provider update - all providers are now supported automatically
            provider_models = [m for m in models if m["provider"] == provider]
            logger.debug(f"Updated {provider} provider with {len(provider_models)} models")

            # Keep legacy support for specific providers if needed
            if provider == "groq":
                await self._update_groq_provider(models)
            elif provider == "external":
                await self._update_external_provider(models)
            elif provider == "openai":
                await self._update_openai_provider(models)
            elif provider == "anthropic":
                await self._update_anthropic_provider(models)
            elif provider == "vllm":
                await self._update_vllm_provider(models)
                
        except Exception as e:
            logger.error(f"Failed to update {provider} provider: {e}")
            raise
    
    async def _update_groq_provider(self, models: List[Dict[str, Any]]):
        """Update Groq provider configuration"""
        # Update available Groq models
        groq_models = [m for m in models if m["provider"] == "groq"]
        logger.debug(f"Updated Groq provider with {len(groq_models)} models")
    
    async def _update_external_provider(self, models: List[Dict[str, Any]]):
        """Update external provider configuration (BGE-M3, etc.)"""
        external_models = [m for m in models if m["provider"] == "external"]

        if external_models:
            external_provider = await get_external_provider()

            for model in external_models:
                if "bge-m3" in model["model_id"].lower():
                    # Update BGE-M3 endpoint configuration
                    external_provider.update_model_endpoint(
                        model["model_id"],
                        model["endpoint"]
                    )
                    logger.debug(f"Updated BGE-M3 endpoint: {model['endpoint']}")

                    # Also refresh the embedding backend instance
                    try:
                        from app.core.backends import get_embedding_backend
                        embedding_backend = get_embedding_backend()
                        embedding_backend.refresh_endpoint_from_registry()
                        logger.info(f"Refreshed embedding backend with new BGE-M3 endpoint from database")
                    except Exception as e:
                        logger.error(f"Failed to refresh embedding backend: {e}")

        logger.debug(f"Updated external provider with {len(external_models)} models")
    
    async def _update_openai_provider(self, models: List[Dict[str, Any]]):
        """Update OpenAI provider configuration"""
        openai_models = [m for m in models if m["provider"] == "openai"]
        logger.debug(f"Updated OpenAI provider with {len(openai_models)} models")

    async def _update_anthropic_provider(self, models: List[Dict[str, Any]]):
        """Update Anthropic provider configuration"""
        anthropic_models = [m for m in models if m["provider"] == "anthropic"]
        logger.debug(f"Updated Anthropic provider with {len(anthropic_models)} models")

    async def _update_vllm_provider(self, models: List[Dict[str, Any]]):
        """Update vLLM provider configuration (BGE-M3 embeddings, etc.)"""
        vllm_models = [m for m in models if m["provider"] == "vllm"]

        for model in vllm_models:
            if model["model_type"] == "embedding":
                # This is an embedding model like BGE-M3
                logger.debug(f"Updated vLLM embedding model: {model['model_id']} -> {model['endpoint']}")
            else:
                logger.debug(f"Updated vLLM model: {model['model_id']} -> {model['endpoint']}")

        logger.debug(f"Updated vLLM provider with {len(vllm_models)} models")
    
    async def force_sync(self):
        """Force immediate configuration sync"""
        logger.info("Force syncing configurations")
        await self.sync_configurations()
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync status"""
        return {
            "last_sync": datetime.fromtimestamp(self.last_sync).isoformat() if self.last_sync else None,
            "sync_running": self.sync_running,
            "admin_cluster_url": self.admin_cluster_url,
            "sync_interval": self.sync_interval,
            "next_sync": datetime.fromtimestamp(self.last_sync + self.sync_interval).isoformat() if self.last_sync else None
        }


# Global config sync service instance
_config_sync_service = None

def get_config_sync_service() -> ConfigSyncService:
    """Get configuration sync service instance"""
    global _config_sync_service
    if _config_sync_service is None:
        _config_sync_service = ConfigSyncService()
    return _config_sync_service