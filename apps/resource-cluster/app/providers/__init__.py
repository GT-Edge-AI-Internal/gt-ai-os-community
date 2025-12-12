"""
GT 2.0 Resource Cluster Providers

External AI model providers for the resource cluster.
"""

from typing import Dict, Any, Optional
import logging

from .external_provider import ExternalProvider

logger = logging.getLogger(__name__)


class ProviderFactory:
    """Factory for creating provider instances dynamically"""
    
    def __init__(self):
        self.providers = {}
        self.initialized = False
    
    async def initialize(self):
        """Initialize all providers"""
        if self.initialized:
            return
            
        try:
            # Initialize external provider (BGE-M3)
            external_provider = ExternalProvider()
            await external_provider.initialize()
            self.providers["external"] = external_provider
            
            logger.info("Provider factory initialized successfully")
            self.initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize provider factory: {e}")
            raise
    
    def get_provider(self, provider_name: str) -> Optional[Any]:
        """Get provider instance by name"""
        return self.providers.get(provider_name)
    
    def list_providers(self) -> Dict[str, Any]:
        """List all available providers"""
        return {
            name: {
                "name": provider.name if hasattr(provider, "name") else name,
                "status": "initialized" if provider else "error"
            }
            for name, provider in self.providers.items()
        }


# Global provider factory instance
_provider_factory = None


async def get_provider_factory() -> ProviderFactory:
    """Get initialized provider factory"""
    global _provider_factory
    if _provider_factory is None:
        _provider_factory = ProviderFactory()
        await _provider_factory.initialize()
    return _provider_factory


def get_external_provider():
    """Get external provider instance (synchronous)"""
    global _provider_factory
    if _provider_factory and "external" in _provider_factory.providers:
        return _provider_factory.providers["external"]
    return None


__all__ = ["ExternalProvider", "ProviderFactory", "get_provider_factory", "get_external_provider"]