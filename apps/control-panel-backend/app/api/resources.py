"""
Resource management API endpoints with HA support
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field, validator
import logging

from app.core.database import get_db
from app.core.auth import get_current_user
from app.services.resource_service import ResourceService
from app.services.groq_service import groq_service
from app.models.ai_resource import AIResource
from app.models.user import User

def require_capability(user: User, resource: str, action: str) -> None:
    """Check if user has required capability for resource and action"""
    # Super admin can do everything
    if user.user_type == "super_admin":
        return
    
    # Check user capabilities
    if not hasattr(user, 'capabilities') or not user.capabilities:
        raise HTTPException(status_code=403, detail="No capabilities assigned")
    
    # Parse capabilities from JSON if needed
    capabilities = user.capabilities
    if isinstance(capabilities, str):
        import json
        try:
            capabilities = json.loads(capabilities)
        except json.JSONDecodeError:
            raise HTTPException(status_code=403, detail="Invalid capabilities format")
    
    # Check for wildcard capability
    for cap in capabilities:
        if isinstance(cap, dict):
            cap_resource = cap.get("resource", "")
            cap_actions = cap.get("actions", [])
            
            # Wildcard resource access
            if cap_resource == "*" or cap_resource == resource:
                if "*" in cap_actions or action in cap_actions:
                    return
            
            # Pattern matching for resource IDs (e.g., "resource:123" matches "resource:*")
            if ":" in resource and ":" in cap_resource:
                cap_prefix = cap_resource.split(":")[0]
                resource_prefix = resource.split(":")[0]
                if cap_prefix == resource_prefix and cap_resource.endswith("*"):
                    if "*" in cap_actions or action in cap_actions:
                        return
    
    raise HTTPException(
        status_code=403, 
        detail=f"Insufficient permissions for {action} on {resource}"
    )

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/resources", tags=["resources"])


# Pydantic models for request/response
class ResourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Resource name")
    description: Optional[str] = Field(None, max_length=500, description="Resource description")
    resource_type: str = Field(..., description="Resource family: ai_ml, rag_engine, agentic_workflow, app_integration, external_service, ai_literacy")
    resource_subtype: Optional[str] = Field(None, description="Resource subtype within family (e.g., llm, vector_database, strategic_game)")
    provider: str = Field(..., description="Provider: groq, openai, anthropic, custom, etc.")
    model_name: Optional[str] = Field(None, description="Model identifier (required for AI/ML resources)")
    personalization_mode: Optional[str] = Field("shared", description="Data separation mode: shared, user_scoped, session_based")
    
    # Connection Configuration
    primary_endpoint: Optional[str] = Field(None, description="Primary API endpoint")
    api_endpoints: Optional[List[str]] = Field(default=[], description="List of API endpoints for HA")
    failover_endpoints: Optional[List[str]] = Field(default=[], description="Failover endpoints")
    health_check_url: Optional[str] = Field(None, description="Health check endpoint")
    iframe_url: Optional[str] = Field(None, description="URL for iframe embedding (external services)")
    
    # Performance and Limits
    max_requests_per_minute: Optional[int] = Field(60, ge=1, le=10000, description="Rate limit")
    max_tokens_per_request: Optional[int] = Field(4000, ge=1, le=100000, description="Token limit per request")
    cost_per_1k_tokens: Optional[float] = Field(0.0, ge=0.0, description="Cost per 1K tokens in dollars")
    latency_sla_ms: Optional[int] = Field(5000, ge=100, le=60000, description="Latency SLA in milliseconds")
    priority: Optional[int] = Field(100, ge=1, le=1000, description="Load balancing priority")
    
    # Configuration
    configuration: Optional[Dict[str, Any]] = Field(default={}, description="Resource-specific configuration")
    sandbox_config: Optional[Dict[str, Any]] = Field(default={}, description="Security sandbox configuration")
    auth_config: Optional[Dict[str, Any]] = Field(default={}, description="Authentication configuration")
    
    @validator('resource_type')
    def validate_resource_type(cls, v):
        allowed_types = ['ai_ml', 'rag_engine', 'agentic_workflow', 'app_integration', 'external_service', 'ai_literacy']
        if v not in allowed_types:
            raise ValueError(f'Resource type must be one of: {allowed_types}')
        return v
    
    @validator('personalization_mode')
    def validate_personalization_mode(cls, v):
        allowed_modes = ['shared', 'user_scoped', 'session_based']
        if v not in allowed_modes:
            raise ValueError(f'Personalization mode must be one of: {allowed_modes}')
        return v
    
    @validator('provider')
    def validate_provider(cls, v):
        allowed_providers = ['groq', 'openai', 'anthropic', 'cohere', 'local', 'canvas', 'ctfd', 'guacamole', 'custom']
        if v not in allowed_providers:
            raise ValueError(f'Provider must be one of: {allowed_providers}')
        return v


class ResourceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    resource_subtype: Optional[str] = None
    personalization_mode: Optional[str] = Field(None, description="Data separation mode: shared, user_scoped, session_based")
    
    # Connection Configuration
    primary_endpoint: Optional[str] = None
    api_endpoints: Optional[List[str]] = None
    failover_endpoints: Optional[List[str]] = None
    health_check_url: Optional[str] = None
    iframe_url: Optional[str] = None
    
    # Performance and Limits
    max_requests_per_minute: Optional[int] = Field(None, ge=1, le=10000)
    max_tokens_per_request: Optional[int] = Field(None, ge=1, le=100000)
    cost_per_1k_tokens: Optional[float] = Field(None, ge=0.0)
    latency_sla_ms: Optional[int] = Field(None, ge=100, le=60000)
    priority: Optional[int] = Field(None, ge=1, le=1000)
    
    # Configuration
    configuration: Optional[Dict[str, Any]] = None
    sandbox_config: Optional[Dict[str, Any]] = None
    auth_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ResourceResponse(BaseModel):
    id: int
    uuid: str
    name: str
    description: Optional[str]
    resource_type: str
    resource_subtype: Optional[str]
    provider: str
    model_name: Optional[str]
    personalization_mode: str
    
    # Connection Configuration
    primary_endpoint: Optional[str]
    health_check_url: Optional[str]
    iframe_url: Optional[str]
    
    # Configuration
    configuration: Dict[str, Any]
    sandbox_config: Dict[str, Any]
    auth_config: Dict[str, Any]
    
    # Performance and Status
    max_requests_per_minute: int
    max_tokens_per_request: int
    cost_per_1k_tokens: float
    latency_sla_ms: int
    health_status: str
    last_health_check: Optional[datetime]
    is_active: bool
    priority: int
    
    # Timestamps
    created_at: datetime
    updated_at: datetime


class TenantAssignment(BaseModel):
    tenant_id: int = Field(..., description="Tenant ID to assign resource to")
    usage_limits: Optional[Dict[str, Any]] = Field(default={}, description="Usage limits for this tenant")


class UsageStatsResponse(BaseModel):
    resource_id: int
    period: Dict[str, str]
    summary: Dict[str, Any]
    daily_stats: Dict[str, Dict[str, Any]]


class HealthCheckResponse(BaseModel):
    total_resources: int
    healthy: int
    unhealthy: int
    unknown: int
    details: List[Dict[str, Any]]


# API Endpoints
@router.post("/", response_model=ResourceResponse, status_code=201)
async def create_resource(
    resource_data: ResourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new AI resource"""
    # Check permissions
    require_capability(current_user, "resource:*", "write")
    
    try:
        service = ResourceService(db)
        resource = await service.create_resource(resource_data.dict(exclude_unset=True))
        return ResourceResponse(**resource.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create resource: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=List[ResourceResponse])
async def list_resources(
    provider: Optional[str] = Query(None, description="Filter by provider"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    health_status: Optional[str] = Query(None, description="Filter by health status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all AI resources with optional filtering"""
    # Check permissions
    require_capability(current_user, "resource:*", "read")
    
    try:
        service = ResourceService(db)
        resources = await service.list_resources(
            provider=provider,
            resource_type=resource_type,
            is_active=is_active,
            health_status=health_status
        )
        return [ResourceResponse(**resource.to_dict()) for resource in resources]
    except Exception as e:
        logger.error(f"Failed to list resources: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{resource_id}", response_model=ResourceResponse)
async def get_resource(
    resource_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific AI resource by ID"""
    # Check permissions
    require_capability(current_user, f"resource:{resource_id}", "read")
    
    try:
        service = ResourceService(db)
        resource = await service.get_resource(resource_id)
        if not resource:
            raise HTTPException(status_code=404, detail="Resource not found")
        return ResourceResponse(**resource.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get resource {resource_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{resource_id}", response_model=ResourceResponse)
async def update_resource(
    resource_id: int,
    updates: ResourceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an AI resource"""
    # Check permissions
    require_capability(current_user, f"resource:{resource_id}", "write")
    
    try:
        service = ResourceService(db)
        resource = await service.update_resource(resource_id, updates.dict(exclude_unset=True))
        if not resource:
            raise HTTPException(status_code=404, detail="Resource not found")
        return ResourceResponse(**resource.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update resource {resource_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{resource_id}", status_code=204)
async def delete_resource(
    resource_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an AI resource (soft delete)"""
    # Check permissions
    require_capability(current_user, f"resource:{resource_id}", "admin")
    
    try:
        service = ResourceService(db)
        success = await service.delete_resource(resource_id)
        if not success:
            raise HTTPException(status_code=404, detail="Resource not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete resource {resource_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{resource_id}/assign", status_code=201)
async def assign_resource_to_tenant(
    resource_id: int,
    assignment: TenantAssignment,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Assign a resource to a tenant"""
    # Check permissions
    require_capability(current_user, f"resource:{resource_id}", "admin")
    require_capability(current_user, f"tenant:{assignment.tenant_id}", "write")
    
    try:
        service = ResourceService(db)
        tenant_resource = await service.assign_resource_to_tenant(
            resource_id, assignment.tenant_id, assignment.usage_limits
        )
        return {"message": "Resource assigned successfully", "assignment_id": tenant_resource.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to assign resource {resource_id} to tenant {assignment.tenant_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{resource_id}/assign/{tenant_id}", status_code=204)
async def unassign_resource_from_tenant(
    resource_id: int,
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove resource assignment from tenant"""
    # Check permissions
    require_capability(current_user, f"resource:{resource_id}", "admin")
    require_capability(current_user, f"tenant:{tenant_id}", "write")
    
    try:
        service = ResourceService(db)
        success = await service.unassign_resource_from_tenant(resource_id, tenant_id)
        if not success:
            raise HTTPException(status_code=404, detail="Assignment not found")
    except Exception as e:
        logger.error(f"Failed to unassign resource {resource_id} from tenant {tenant_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{resource_id}/usage", response_model=UsageStatsResponse)
async def get_resource_usage_stats(
    resource_id: int,
    start_date: Optional[datetime] = Query(None, description="Start date for statistics"),
    end_date: Optional[datetime] = Query(None, description="End date for statistics"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get usage statistics for a resource"""
    # Check permissions
    require_capability(current_user, f"resource:{resource_id}", "read")
    
    try:
        service = ResourceService(db)
        stats = await service.get_resource_usage_stats(resource_id, start_date, end_date)
        return UsageStatsResponse(**stats)
    except Exception as e:
        logger.error(f"Failed to get usage stats for resource {resource_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/health-check", response_model=HealthCheckResponse)
async def health_check_all_resources(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Perform health checks on all active resources"""
    # Check permissions
    require_capability(current_user, "resource:*", "read")
    
    try:
        service = ResourceService(db)
        # Run health checks in background for better performance
        results = await service.health_check_all_resources()
        return HealthCheckResponse(**results)
    except Exception as e:
        logger.error(f"Failed to perform health checks: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{resource_id}/health", status_code=200)
async def health_check_resource(
    resource_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Perform health check on a specific resource"""
    # Check permissions
    require_capability(current_user, f"resource:{resource_id}", "read")
    
    try:
        service = ResourceService(db)
        resource = await service.get_resource(resource_id)
        if not resource:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        # Decrypt API key for health check
        api_key = await service._decrypt_api_key(resource.api_key_encrypted, resource.tenant_id)
        is_healthy = await service._health_check_resource(resource, api_key)
        
        return {
            "resource_id": resource_id,
            "health_status": resource.health_status,
            "is_healthy": is_healthy,
            "last_check": resource.last_health_check.isoformat() if resource.last_health_check else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to health check resource {resource_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/tenant/{tenant_id}", response_model=List[ResourceResponse])
async def get_tenant_resources(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all resources assigned to a specific tenant"""
    # Check permissions
    require_capability(current_user, f"tenant:{tenant_id}", "read")
    
    try:
        service = ResourceService(db)
        resources = await service.get_tenant_resources(tenant_id)
        return [ResourceResponse(**resource.to_dict()) for resource in resources]
    except Exception as e:
        logger.error(f"Failed to get resources for tenant {tenant_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/tenant/{tenant_id}/usage", response_model=Dict[str, Any])
async def get_tenant_usage_stats(
    tenant_id: int,
    start_date: Optional[datetime] = Query(None, description="Start date for statistics"),
    end_date: Optional[datetime] = Query(None, description="End date for statistics"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get usage statistics for all resources used by a tenant"""
    # Check permissions
    require_capability(current_user, f"tenant:{tenant_id}", "read")
    
    try:
        service = ResourceService(db)
        stats = await service.get_tenant_usage_stats(tenant_id, start_date, end_date)
        return stats
    except Exception as e:
        logger.error(f"Failed to get usage stats for tenant {tenant_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# New comprehensive resource management endpoints
@router.get("/families/summary", response_model=Dict[str, Any])
async def get_resource_families_summary(
    tenant_id: Optional[int] = Query(None, description="Filter by tenant ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get summary of all resource families with counts and health status"""
    # Check permissions
    if tenant_id:
        require_capability(current_user, f"tenant:{tenant_id}", "read")
    else:
        require_capability(current_user, "resource:*", "read")
    
    try:
        service = ResourceService(db)
        summary = await service.get_resource_families_summary(tenant_id)
        return summary
    except Exception as e:
        logger.error(f"Failed to get resource families summary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/family/{resource_type}", response_model=List[ResourceResponse])
async def list_resources_by_family(
    resource_type: str,
    resource_subtype: Optional[str] = Query(None, description="Filter by resource subtype"),
    tenant_id: Optional[int] = Query(None, description="Filter by tenant ID"),
    include_inactive: Optional[bool] = Query(False, description="Include inactive resources"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List resources by resource family with optional filtering"""
    # Check permissions
    if tenant_id:
        require_capability(current_user, f"tenant:{tenant_id}", "read")
    else:
        require_capability(current_user, "resource:*", "read")
    
    try:
        service = ResourceService(db)
        resources = await service.list_resources_by_family(
            resource_type=resource_type,
            resource_subtype=resource_subtype,
            tenant_id=tenant_id,
            include_inactive=include_inactive
        )
        return [ResourceResponse(**resource.to_dict()) for resource in resources]
    except Exception as e:
        logger.error(f"Failed to list resources for family {resource_type}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/user/{user_id}/data/{resource_id}", response_model=Dict[str, Any])
async def get_user_resource_data(
    user_id: int,
    resource_id: int,
    data_type: str = Query(..., description="Type of data to retrieve"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get user-specific data for a resource"""
    # Check permissions - user can access their own data or admin can access any user's data
    if current_user.id != user_id:
        require_capability(current_user, f"user:{user_id}", "read")
    
    try:
        service = ResourceService(db)
        user_data = await service.get_user_resource_data(user_id, resource_id, data_type)
        
        if not user_data:
            raise HTTPException(status_code=404, detail="User resource data not found")
        
        return user_data.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user resource data: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/user/{user_id}/data/{resource_id}", status_code=201)
async def set_user_resource_data(
    user_id: int,
    resource_id: int,
    data_type: str = Query(..., description="Type of data to store"),
    data_key: str = Query(..., description="Key identifier for the data"),
    data_value: Dict[str, Any] = ...,
    expires_minutes: Optional[int] = Query(None, description="Expiry time in minutes for session data"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Set user-specific data for a resource"""
    # Check permissions - user can set their own data or admin can set any user's data
    if current_user.id != user_id:
        require_capability(current_user, f"user:{user_id}", "write")
    
    try:
        service = ResourceService(db)
        user_data = await service.set_user_resource_data(
            user_id=user_id,
            tenant_id=current_user.tenant_id,
            resource_id=resource_id,
            data_type=data_type,
            data_key=data_key,
            data_value=data_value,
            expires_minutes=expires_minutes
        )
        
        return {"message": "User resource data saved", "data_id": user_data.id}
    except Exception as e:
        logger.error(f"Failed to set user resource data: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/user/{user_id}/progress/{resource_id}", response_model=Dict[str, Any])
async def get_user_progress(
    user_id: int,
    resource_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get user progress for AI literacy and learning resources"""
    # Check permissions
    if current_user.id != user_id:
        require_capability(current_user, f"user:{user_id}", "read")
    
    try:
        service = ResourceService(db)
        progress = await service.get_user_progress(user_id, resource_id)
        
        if not progress:
            raise HTTPException(status_code=404, detail="User progress not found")
        
        return progress.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user progress: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/user/{user_id}/progress/{resource_id}", status_code=201)
async def update_user_progress(
    user_id: int,
    resource_id: int,
    skill_area: str = Query(..., description="Skill area being tracked"),
    progress_data: Dict[str, Any] = ...,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update user progress for learning resources"""
    # Check permissions
    if current_user.id != user_id:
        require_capability(current_user, f"user:{user_id}", "write")
    
    try:
        service = ResourceService(db)
        progress = await service.update_user_progress(
            user_id=user_id,
            tenant_id=current_user.tenant_id,
            resource_id=resource_id,
            skill_area=skill_area,
            progress_data=progress_data
        )
        
        return {"message": "User progress updated", "progress_id": progress.id}
    except Exception as e:
        logger.error(f"Failed to update user progress: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/subtypes", response_model=Dict[str, List[str]])
async def get_resource_subtypes(
    current_user: User = Depends(get_current_user)
):
    """Get available subtypes for each resource family"""
    require_capability(current_user, "resource:*", "read")
    
    subtypes = {
        "ai_ml": ["llm", "embedding", "image_generation", "function_calling"],
        "rag_engine": ["vector_database", "document_processor", "retrieval_system"],
        "agentic_workflow": ["workflow", "agent_framework", "multi_agent"],
        "app_integration": ["api", "webhook", "oauth_app", "custom"],
        "external_service": ["lms", "cyber_range", "iframe", "custom"],
        "ai_literacy": ["strategic_game", "logic_puzzle", "philosophical_dilemma", "educational_content"]
    }
    
    return subtypes


@router.get("/config-schema", response_model=Dict[str, Any])
async def get_resource_config_schema(
    resource_type: str = Query(..., description="Resource family type"),
    resource_subtype: str = Query(..., description="Resource subtype"),
    current_user: User = Depends(get_current_user)
):
    """Get configuration schema for a specific resource type and subtype"""
    require_capability(current_user, "resource:*", "read")
    
    try:
        from app.models.resource_schemas import get_config_schema
        schema = get_config_schema(resource_type, resource_subtype)
        return schema.schema()
    except Exception as e:
        logger.error(f"Failed to get config schema: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid resource type or subtype: {e}")


@router.post("/validate-config", response_model=Dict[str, Any])
async def validate_resource_config(
    resource_type: str = Query(..., description="Resource family type"),
    resource_subtype: str = Query(..., description="Resource subtype"),
    config_data: Dict[str, Any] = ...,
    current_user: User = Depends(get_current_user)
):
    """Validate resource configuration against schema"""
    require_capability(current_user, "resource:*", "write")
    
    try:
        from app.models.resource_schemas import validate_resource_config
        validated_config = validate_resource_config(resource_type, resource_subtype, config_data)
        return {
            "valid": True,
            "validated_config": validated_config,
            "message": "Configuration is valid"
        }
    except Exception as e:
        logger.error(f"Failed to validate resource config: {e}")
        return {
            "valid": False,
            "errors": "Configuration validation failed",
            "message": "Configuration validation failed"
        }