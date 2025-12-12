"""
Tenant Model Management API for GT 2.0 Admin Control Panel

Provides endpoints for managing which models are available to which tenants,
with tenant-specific permissions and rate limits.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
import logging

from app.core.database import get_db
from app.services.model_management_service import get_model_management_service
from app.models.tenant_model_config import TenantModelConfig

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tenants", tags=["Tenant Model Management"])


# Request/Response Models
class TenantModelAssignRequest(BaseModel):
    model_id: str = Field(..., description="Model ID to assign")
    rate_limits: Optional[Dict[str, Any]] = Field(None, description="Custom rate limits")
    capabilities: Optional[Dict[str, Any]] = Field(None, description="Tenant-specific capabilities")
    usage_constraints: Optional[Dict[str, Any]] = Field(None, description="Usage restrictions")
    priority: int = Field(1, ge=1, le=10, description="Priority level (1-10)")

    model_config = {"protected_namespaces": ()}


class TenantModelUpdateRequest(BaseModel):
    is_enabled: Optional[bool] = Field(None, description="Enable/disable model for tenant")
    rate_limits: Optional[Dict[str, Any]] = Field(None, description="Updated rate limits")
    tenant_capabilities: Optional[Dict[str, Any]] = Field(None, description="Updated capabilities")
    usage_constraints: Optional[Dict[str, Any]] = Field(None, description="Updated usage restrictions")
    priority: Optional[int] = Field(None, ge=1, le=10, description="Updated priority level")


class ModelAccessCheckRequest(BaseModel):
    user_capabilities: Optional[List[str]] = Field(None, description="User capabilities")
    user_id: Optional[str] = Field(None, description="User identifier")


class TenantModelResponse(BaseModel):
    id: int
    tenant_id: int
    model_id: str
    is_enabled: bool
    tenant_capabilities: Dict[str, Any]
    rate_limits: Dict[str, Any]
    usage_constraints: Dict[str, Any]
    priority: int
    created_at: str
    updated_at: str


class ModelWithTenantConfigResponse(BaseModel):
    model_id: str
    name: str
    provider: str
    model_type: str
    endpoint: str
    tenant_config: TenantModelResponse


@router.post("/{tenant_id}/models", response_model=TenantModelResponse)
async def assign_model_to_tenant(
    tenant_id: int,
    request: TenantModelAssignRequest,
    db: AsyncSession = Depends(get_db)
):
    """Assign a model to a tenant with specific configuration"""
    try:
        service = get_model_management_service(db)
        
        tenant_model_config = await service.assign_model_to_tenant(
            tenant_id=tenant_id,
            model_id=request.model_id,
            rate_limits=request.rate_limits,
            capabilities=request.capabilities,
            usage_constraints=request.usage_constraints,
            priority=request.priority
        )
        
        return TenantModelResponse(**tenant_model_config.to_dict())
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error assigning model to tenant: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{tenant_id}/models/{model_id:path}")
async def remove_model_from_tenant(
    tenant_id: int,
    model_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Remove model access from a tenant"""
    try:
        service = get_model_management_service(db)
        
        success = await service.remove_model_from_tenant(tenant_id, model_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Model assignment not found")
        
        return {"message": f"Model {model_id} removed from tenant {tenant_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing model from tenant: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{tenant_id}/models/{model_id:path}", response_model=TenantModelResponse)
async def update_tenant_model_config(
    tenant_id: int,
    model_id: str,
    request: TenantModelUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """Update tenant-specific model configuration"""
    try:
        service = get_model_management_service(db)
        
        # Convert request to dict, excluding None values
        updates = {k: v for k, v in request.dict().items() if v is not None}
        
        tenant_model_config = await service.update_tenant_model_config(
            tenant_id=tenant_id,
            model_id=model_id,
            updates=updates
        )
        
        if not tenant_model_config:
            raise HTTPException(status_code=404, detail="Tenant model configuration not found")
        
        return TenantModelResponse(**tenant_model_config.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating tenant model config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{tenant_id}/models", response_model=List[ModelWithTenantConfigResponse])
async def get_tenant_models(
    tenant_id: int,
    enabled_only: bool = Query(False, description="Only return enabled models"),
    db: AsyncSession = Depends(get_db)
):
    """Get all models available to a tenant"""
    try:
        service = get_model_management_service(db)
        
        models = await service.get_tenant_models(
            tenant_id=tenant_id,
            enabled_only=enabled_only
        )
        
        # Format response
        response_models = []
        for model in models:
            tenant_config = model.pop("tenant_config")
            response_models.append({
                **model,
                "tenant_config": TenantModelResponse(**tenant_config)
            })
        
        return response_models
        
    except Exception as e:
        logger.error(f"Error getting tenant models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{tenant_id}/models/{model_id}/check-access")
async def check_tenant_model_access(
    tenant_id: int,
    model_id: str,
    request: ModelAccessCheckRequest,
    db: AsyncSession = Depends(get_db)
):
    """Check if a tenant/user can access a specific model"""
    try:
        service = get_model_management_service(db)
        
        access_info = await service.check_tenant_model_access(
            tenant_id=tenant_id,
            model_id=model_id,
            user_capabilities=request.user_capabilities,
            user_id=request.user_id
        )
        
        return access_info
        
    except Exception as e:
        logger.error(f"Error checking tenant model access: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{tenant_id}/models/stats")
async def get_tenant_model_stats(
    tenant_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get statistics about models for a tenant"""
    try:
        service = get_model_management_service(db)
        
        stats = await service.get_tenant_model_stats(tenant_id)
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting tenant model stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Additional endpoints for model-centric views
@router.get("/models/{model_id:path}/tenants")
async def get_model_tenants(
    model_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get all tenants that have access to a model"""
    try:
        service = get_model_management_service(db)
        
        tenants = await service.get_model_tenants(model_id)
        
        return {
            "model_id": model_id,
            "tenants": tenants,
            "total_tenants": len(tenants)
        }
        
    except Exception as e:
        logger.error(f"Error getting model tenants: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Global tenant model configuration endpoints
@router.get("/all")
async def get_all_tenant_model_configs(
    db: AsyncSession = Depends(get_db)
):
    """Get all tenant model configurations with joined tenant and model data"""
    try:
        service = get_model_management_service(db)
        
        # This would need to be implemented in the service
        configs = await service.get_all_tenant_model_configs()
        
        return configs
        
    except Exception as e:
        logger.error(f"Error getting all tenant model configs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Bulk operations
@router.post("/{tenant_id}/models/bulk-assign")
async def bulk_assign_models_to_tenant(
    tenant_id: int,
    model_ids: List[str],
    default_config: Optional[TenantModelAssignRequest] = None,
    db: AsyncSession = Depends(get_db)
):
    """Assign multiple models to a tenant with the same configuration"""
    try:
        service = get_model_management_service(db)
        
        results = []
        errors = []
        
        for model_id in model_ids:
            try:
                config = default_config if default_config else TenantModelAssignRequest(model_id=model_id)
                
                tenant_model_config = await service.assign_model_to_tenant(
                    tenant_id=tenant_id,
                    model_id=model_id,
                    rate_limits=config.rate_limits,
                    capabilities=config.capabilities,
                    usage_constraints=config.usage_constraints,
                    priority=config.priority
                )
                
                results.append({
                    "model_id": model_id,
                    "status": "success",
                    "config": tenant_model_config.to_dict()
                })
                
            except Exception as e:
                errors.append({
                    "model_id": model_id,
                    "status": "error",
                    "error": str(e)
                })
        
        return {
            "tenant_id": tenant_id,
            "total_requested": len(model_ids),
            "successful": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors
        }
        
    except Exception as e:
        logger.error(f"Error bulk assigning models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{tenant_id}/models/bulk-remove")
async def bulk_remove_models_from_tenant(
    tenant_id: int,
    model_ids: List[str],
    db: AsyncSession = Depends(get_db)
):
    """Remove multiple models from a tenant"""
    try:
        service = get_model_management_service(db)
        
        results = []
        
        for model_id in model_ids:
            try:
                success = await service.remove_model_from_tenant(tenant_id, model_id)
                results.append({
                    "model_id": model_id,
                    "status": "success" if success else "not_found",
                    "removed": success
                })
                
            except Exception as e:
                results.append({
                    "model_id": model_id,
                    "status": "error",
                    "error": str(e)
                })
        
        successful = sum(1 for r in results if r["status"] == "success")
        
        return {
            "tenant_id": tenant_id,
            "total_requested": len(model_ids),
            "successful": successful,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error bulk removing models: {e}")
        raise HTTPException(status_code=500, detail=str(e))