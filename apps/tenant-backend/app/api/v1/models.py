"""
Tenant Models API - Interface to Resource Cluster Model Management

Provides tenant-scoped access to available AI models from the Resource Cluster.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, status, Depends
import httpx
import logging

from app.core.security import get_current_user
from app.core.config import get_settings
from app.core.cache import get_cache
from app.services.resource_cluster_client import ResourceClusterClient

logger = logging.getLogger(__name__)
settings = get_settings()
cache = get_cache()

router = APIRouter(prefix="/api/v1/models", tags=["Models"])


@router.get("/", summary="List available models for tenant")
async def list_available_models(
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get list of AI models available to the current tenant"""

    try:
        # Get tenant domain from current user
        tenant_domain = current_user.get("tenant_domain", "default")

        # Check cache first (5-minute TTL)
        cache_key = f"models_list_{tenant_domain}"
        cached_models = cache.get(cache_key, ttl=300)
        if cached_models:
            logger.debug(f"Returning cached model list for tenant {tenant_domain}")
            return {**cached_models, "cached": True}
        
        # Call Resource Cluster models API - use Docker service name if in container
        import os
        if os.path.exists('/.dockerenv'):
            resource_cluster_url = "http://resource-cluster:8000"
        else:
            resource_cluster_url = settings.resource_cluster_url
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{resource_cluster_url}/api/v1/models/",
                headers={
                    "X-Tenant-Domain": tenant_domain
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                models_data = response.json()
                models = models_data.get("models", [])
                
                # Filter models by health and deployment status
                available_models = [
                    {
                        "value": model["id"],  # model_id string for backwards compatibility
                        "uuid": model.get("uuid"),  # Database UUID for unique identification
                        "label": model["name"],
                        "description": model["description"],
                        "provider": model["provider"],
                        "model_type": model["model_type"],
                        "max_tokens": model["performance"]["max_tokens"],
                        "context_window": model["performance"]["context_window"],
                        "cost_per_1k_tokens": model["performance"]["cost_per_1k_tokens"],
                        "latency_p50_ms": model["performance"]["latency_p50_ms"],
                        "health_status": model["status"]["health"],
                        "deployment_status": model["status"]["deployment"]
                    }
                    for model in models
                    if (model["status"]["deployment"] == "available" and
                        model["status"]["health"] in ["healthy", "unknown"] and
                        model["model_type"] != "embedding")
                ]
                
                # Sort by provider preference (NVIDIA first, then Groq) and then by performance
                provider_order = {"nvidia": 0, "groq": 1}
                available_models.sort(key=lambda x: (
                    provider_order.get(x["provider"], 99),  # NVIDIA first, then Groq
                    x["latency_p50_ms"] or 999  # Lower latency first
                ))

                result = {
                    "models": available_models,
                    "total": len(available_models),
                    "tenant_domain": tenant_domain,
                    "last_updated": models_data.get("last_updated"),
                    "cached": False
                }

                # Cache the result for 5 minutes
                cache.set(cache_key, result)
                logger.debug(f"Cached model list for tenant {tenant_domain}")

                return result
            
            else:
                # Resource Cluster unavailable - return empty list
                logger.warning(f"Resource Cluster unavailable (HTTP {response.status_code})")
                return {
                    "models": [],
                    "total": 0,
                    "tenant_domain": tenant_domain,
                    "message": "No models available - resource cluster unavailable"
                }
    
    except Exception as e:
        logger.error(f"Error fetching models from Resource Cluster: {e}")
        # Return empty list in case of error
        return {
            "models": [],
            "total": 0,
            "tenant_domain": current_user.get("tenant_domain", "default"),
            "message": "No models available - service error"
        }



@router.get("/{model_id}", summary="Get model details")
async def get_model_details(
    model_id: str,
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get detailed information about a specific model"""
    
    try:
        tenant_domain = current_user.get("tenant_domain", "default")
        
        # Call Resource Cluster for model details - use Docker service name if in container
        import os
        if os.path.exists('/.dockerenv'):
            resource_cluster_url = "http://resource-cluster:8000"
        else:
            resource_cluster_url = settings.resource_cluster_url
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{resource_cluster_url}/api/v1/models/{model_id}",
                headers={
                    "X-Tenant-Domain": tenant_domain
                },
                timeout=15.0
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Model {model_id} not found"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Resource Cluster unavailable"
                )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching model {model_id} details: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to get model details"
        )