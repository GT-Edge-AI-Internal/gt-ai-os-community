"""
Model Management API Endpoints - Simplified for Development

Provides REST API for model registry without capability checks for now.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, status, Query, Header
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from app.services.model_service import default_model_service as model_service
from app.services.admin_model_config_service import AdminModelConfigService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/models", tags=["Model Management"])

# Initialize admin model config service
admin_model_service = AdminModelConfigService()


class ModelRegistrationRequest(BaseModel):
    """Request model for registering a new model"""
    model_id: str = Field(..., description="Unique model identifier")
    name: str = Field(..., description="Human-readable model name")
    version: str = Field(..., description="Model version")
    provider: str = Field(..., description="Model provider (groq, openai, local, etc.)")
    model_type: str = Field(..., description="Model type (llm, embedding, image_gen, etc.)")
    description: str = Field("", description="Model description")
    capabilities: Optional[Dict[str, Any]] = Field(None, description="Model capabilities")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Model parameters")
    endpoint_url: Optional[str] = Field(None, description="Model endpoint URL")
    max_tokens: Optional[int] = Field(4000, description="Maximum tokens per request")
    context_window: Optional[int] = Field(4000, description="Context window size")
    cost_per_1k_tokens: Optional[float] = Field(0.0, description="Cost per 1000 tokens")

    model_config = {"protected_namespaces": ()}


class ModelUpdateRequest(BaseModel):
    """Request model for updating model metadata"""
    name: Optional[str] = None
    description: Optional[str] = None
    deployment_status: Optional[str] = None
    health_status: Optional[str] = None
    capabilities: Optional[Dict[str, Any]] = None
    parameters: Optional[Dict[str, Any]] = None


class ModelUsageRequest(BaseModel):
    """Request model for tracking model usage"""
    success: bool = Field(True, description="Whether the request was successful")
    latency_ms: Optional[float] = Field(None, description="Request latency in milliseconds")
    tokens_used: Optional[int] = Field(None, description="Number of tokens used")


@router.get("/", summary="List all models")
async def list_models(
    provider: Optional[str] = Query(None, description="Filter by provider"),
    model_type: Optional[str] = Query(None, description="Filter by model type"),
    deployment_status: Optional[str] = Query(None, description="Filter by deployment status"),
    health_status: Optional[str] = Query(None, description="Filter by health status"),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID", description="Tenant ID for filtering accessible models")
) -> Dict[str, Any]:
    """List all registered models with optional filters"""
    
    try:
        # Get models from admin backend via sync service
        # If tenant ID is provided, filter to only models accessible to that tenant
        if x_tenant_id:
            admin_models = await admin_model_service.get_tenant_models(x_tenant_id)
            logger.info(f"Retrieved {len(admin_models)} tenant-specific models from admin backend for tenant {x_tenant_id}")
        else:
            admin_models = await admin_model_service.get_all_models(active_only=True)
            logger.info(f"Retrieved {len(admin_models)} models from admin backend")
        
        # Convert admin models to resource cluster format
        models = []
        for admin_model in admin_models:
            model_dict = {
                "id": admin_model.model_id,  # model_id string for backwards compatibility
                "uuid": admin_model.uuid,     # Database UUID for unique identification
                "name": admin_model.name,
                "description": f"{admin_model.provider.title()} model with {admin_model.context_window or 'default'} context window",
                "provider": admin_model.provider,
                "model_type": admin_model.model_type,
                "performance": {
                    "max_tokens": admin_model.max_tokens or 4096,
                    "context_window": admin_model.context_window or 4096,
                    "cost_per_1k_tokens": (admin_model.cost_per_1k_input + admin_model.cost_per_1k_output) / 2,
                    "latency_p50_ms": 150  # Default estimate, could be enhanced with real metrics
                },
                "status": {
                    "health": "healthy" if admin_model.is_active else "unhealthy",
                    "deployment": "available" if admin_model.is_active else "unavailable"
                }
            }
            models.append(model_dict)
        
        # If no models from admin, return empty list
        if not models:
            logger.warning("No models configured in admin backend")
            models = []
        
        # Apply filters if provided
        filtered_models = models
        if provider:
            filtered_models = [m for m in filtered_models if m["provider"] == provider]
        if model_type:
            filtered_models = [m for m in filtered_models if m["model_type"] == model_type]
        if deployment_status:
            filtered_models = [m for m in filtered_models if m["status"]["deployment"] == deployment_status]
        if health_status:
            filtered_models = [m for m in filtered_models if m["status"]["health"] == health_status]
        
        return {
            "models": filtered_models,
            "total": len(filtered_models),
            "filters": {
                "provider": provider,
                "model_type": model_type,
                "deployment_status": deployment_status,
                "health_status": health_status
            },
            "last_updated": "2025-09-09T13:00:00Z"
        }
    
    except Exception as e:
        logger.error(f"Error listing models: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list models"
        )


@router.post("/", status_code=status.HTTP_201_CREATED, summary="Register a new model")
async def register_model(
    model_request: ModelRegistrationRequest
) -> Dict[str, Any]:
    """Register a new model in the registry"""
    
    try:
        model = await model_service.register_model(
            model_id=model_request.model_id,
            name=model_request.name,
            version=model_request.version,
            provider=model_request.provider,
            model_type=model_request.model_type,
            description=model_request.description,
            capabilities=model_request.capabilities,
            parameters=model_request.parameters,
            endpoint_url=model_request.endpoint_url,
            max_tokens=model_request.max_tokens,
            context_window=model_request.context_window,
            cost_per_1k_tokens=model_request.cost_per_1k_tokens
        )
        
        return {
            "message": "Model registered successfully",
            "model": model
        }
    
    except Exception as e:
        logger.error(f"Error registering model {model_request.model_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register model"
        )


@router.get("/{model_id}", summary="Get model details")
async def get_model(
    model_id: str,
) -> Dict[str, Any]:
    """Get detailed information about a specific model"""
    
    try:
        model = await model_service.get_model(model_id)
        
        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model {model_id} not found"
            )
        
        return {"model": model}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting model {model_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get model"
        )


@router.put("/{model_id}", summary="Update model metadata")
async def update_model(
    model_id: str,
    update_request: ModelUpdateRequest,
) -> Dict[str, Any]:
    """Update model metadata and status"""
    
    try:
        # Check if model exists
        model = await model_service.get_model(model_id)
        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model {model_id} not found"
            )
        
        # Update status fields
        if update_request.deployment_status or update_request.health_status:
            success = await model_service.update_model_status(
                model_id,
                deployment_status=update_request.deployment_status,
                health_status=update_request.health_status
            )
            
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update model status"
                )
        
        # For other fields, we'd need to extend the model service
        # This is a simplified implementation
        
        updated_model = await model_service.get_model(model_id)
        
        return {
            "message": "Model updated successfully",
            "model": updated_model
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating model {model_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update model"
        )


@router.delete("/{model_id}", summary="Retire a model")
async def retire_model(
    model_id: str,
    reason: str = Query("", description="Reason for retirement"),
) -> Dict[str, Any]:
    """Retire a model (mark as no longer available)"""
    
    try:
        success = await model_service.retire_model(model_id, reason)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model {model_id} not found"
            )
        
        return {
            "message": f"Model {model_id} retired successfully",
            "reason": reason
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retiring model {model_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retire model"
        )


@router.post("/{model_id}/usage", summary="Track model usage")
async def track_model_usage(
    model_id: str,
    usage_request: ModelUsageRequest,
) -> Dict[str, Any]:
    """Track usage and performance metrics for a model"""
    
    try:
        await model_service.track_model_usage(
            model_id,
            success=usage_request.success,
            latency_ms=usage_request.latency_ms
        )
        
        return {
            "message": "Usage tracked successfully",
            "model_id": model_id
        }
    
    except Exception as e:
        logger.error(f"Error tracking usage for model {model_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to track usage"
        )


@router.get("/{model_id}/health", summary="Check model health")
async def check_model_health(
    model_id: str,
) -> Dict[str, Any]:
    """Check the health status of a specific model"""
    
    try:
        health_result = await model_service.check_model_health(model_id)
        
        return {
            "model_id": model_id,
            "health": health_result
        }
    
    except Exception as e:
        logger.error(f"Error checking health for model {model_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check model health"
        )


@router.get("/health/bulk", summary="Bulk health check")
async def bulk_health_check(
) -> Dict[str, Any]:
    """Check health of all registered models"""
    
    try:
        health_results = await model_service.bulk_health_check()
        
        return {
            "health_check": health_results,
            "timestamp": "2024-01-01T00:00:00Z"  # Would use actual timestamp
        }
    
    except Exception as e:
        logger.error(f"Error in bulk health check: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to perform bulk health check"
        )


@router.get("/analytics", summary="Get model analytics")
async def get_model_analytics(
    model_id: Optional[str] = Query(None, description="Specific model ID"),
    timeframe_hours: int = Query(24, description="Analytics timeframe in hours"),
) -> Dict[str, Any]:
    """Get analytics for model usage and performance"""
    
    try:
        analytics = await model_service.get_model_analytics(
            model_id=model_id,
            timeframe_hours=timeframe_hours
        )
        
        return {
            "analytics": analytics,
            "timeframe_hours": timeframe_hours,
            "generated_at": "2024-01-01T00:00:00Z"  # Would use actual timestamp
        }
    
    except Exception as e:
        logger.error(f"Error getting analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get analytics"
        )


@router.post("/initialize", summary="Initialize default models")
async def initialize_default_models(
) -> Dict[str, Any]:
    """Initialize the registry with default models"""
    
    try:
        await model_service.initialize_default_models()
        
        models = await model_service.list_models()
        
        return {
            "message": "Default models initialized successfully",
            "total_models": len(models)
        }
    
    except Exception as e:
        logger.error(f"Error initializing default models: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize default models"
        )


@router.get("/providers/available", summary="Get available providers")
async def get_available_providers(
) -> Dict[str, Any]:
    """Get list of available model providers"""
    
    try:
        models = await model_service.list_models()
        
        providers = {}
        for model in models:
            provider = model["provider"]
            if provider not in providers:
                providers[provider] = {
                    "name": provider,
                    "model_count": 0,
                    "model_types": set(),
                    "status": "available"
                }
            
            providers[provider]["model_count"] += 1
            providers[provider]["model_types"].add(model["model_type"])
        
        # Convert sets to lists for JSON serialization
        for provider_info in providers.values():
            provider_info["model_types"] = list(provider_info["model_types"])
        
        return {
            "providers": list(providers.values()),
            "total_providers": len(providers)
        }
    
    except Exception as e:
        logger.error(f"Error getting available providers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get available providers"
        )


@router.post("/sync", summary="Force sync from admin cluster")
async def force_sync_models() -> Dict[str, Any]:
    """Force immediate sync of models from admin cluster"""
    
    try:
        await admin_model_service.force_sync()
        models = await admin_model_service.get_all_models(active_only=True)
        
        return {
            "message": "Models synced successfully",
            "models_count": len(models),
            "sync_timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error forcing model sync: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync models"
        )